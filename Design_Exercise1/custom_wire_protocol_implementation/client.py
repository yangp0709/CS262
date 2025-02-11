import socket
import tkinter as tk
from tkinter import messagebox, scrolledtext
import threading
import struct
import ast
from chat_ui_objects import root, login_frame, username_entry_var, username_entry, password_entry, chat_frame, chat_label, new_conversation_entry_var, new_conversation_entry, conversation_list

SERVER_HOST = "localhost"
SERVER_PORT = 5001
CLIENT_VERSION = "1.0.0"

current_user = None
# conversations: key=contact, value=list of message dicts {id, from, message, status}
conversations = {}
chat_windows = {}   # open chat windows
undelivered = {} # saves undelivered message
subscription_socket = None

# Helper: Add a message if its ID isn’t already present, or update it if it exists.
def add_message(contact, msg):
    if contact not in conversations:
        conversations[contact] = []
    for i, existing in enumerate(conversations[contact]):
        if existing["id"] == msg["id"]:
            conversations[contact][i] = msg  # update the message (e.g. mark as deleted)
            return True
    conversations[contact].append(msg)
    return True

def check_version_number():
    try: 
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn.connect((SERVER_HOST, SERVER_PORT))

        # Send version number first
        conn.send(CLIENT_VERSION.encode().ljust(32))
        # Receive the server's response on verison number match
        response = conn.recv(1023).decode()
        if response.startswith("error:"):
            print(f"Error: {response}")
            conn.close() 
            return None # close client socket and exit due to version mismatch 
        print(f"{response}") # success response for version match.
        return conn
    except Exception as e:
        print(f"Error: {e}")
        return None


def send_request(request_type, data):
    """Send a request to the server using a custom binary protocol."""
    try:
        client = check_version_number()
        if client is not None:
            # Since version matched, continue to pack data using struct
            message = struct.pack("!I", request_type) + data.encode()
            client.send(message)
            
            # Receive response
            response = client.recv(4096)
            client.close()
            return response.decode()
    except Exception as e:
        messagebox.showerror("Error", f"Connection failed: {e}")
        return None

def update_username_suggestions(event, entry, entry_var):
    """Update the dropdown options for username based on user input."""
    typed = entry_var.get().lower()
    
    try:
        username_options = ast.literal_eval(send_request(3, "empty"))  # Ensure valid list
        if not isinstance(username_options, list):  # Extra safety check
            username_options = []
    except (SyntaxError, ValueError):
        username_options = []  # Handle bad responses safely

    if typed == "":
        entry["values"] = username_options  # Reset to all options
    else:
        filtered = [item for item in username_options if typed in item.lower()]
        entry["values"] = filtered

def login():
    global current_user
    username = username_entry.get().strip()
    password = password_entry.get().strip()
    if not username or not password:
        messagebox.showwarning("Input Error", "Username and password cannot be empty.")
        return
    response = send_request(2, f"{username}|{password}")
    if response and response.startswith("success"):
        current_user = username
        login_frame.pack_forget()
        chat_frame.pack()
        chat_label.config(text=f"Chat - Logged in as {username}")
        load_conversations()
        check_new_messages()
        threading.Thread(target=subscribe_thread, daemon=True).start()
        username_entry.delete(0, tk.END)
        password_entry.delete(0, tk.END)
    else:
        messagebox.showerror("Login Failed", response if response else "No response from server.")

def register():
    username = username_entry.get().strip()
    password = password_entry.get().strip()
    if not username or not password:
        messagebox.showwarning("Input Error", "Username and password cannot be empty.")
        return
    response = send_request(1, f"{username}|{password}")
    if response and response.startswith("success"):
        messagebox.showinfo("Success", response)
    else:
        messagebox.showerror("Registration Failed", response if response else "No response from server.")


def subscribe_thread():
    global current_user, subscription_socket
    try:
        subscription_socket = check_version_number()
        if subscription_socket is not None:
            request_type = 5
            data = current_user
            message = struct.pack("!I", request_type) + data.encode()
            subscription_socket.send(message)
            while current_user:
                response = subscription_socket.recv(4096)
                if not response:
                    break
                response = response.decode()

                if response and response.startswith("success"):
                    message_data = ast.literal_eval(response.split(':', 1)[1])
                    sender = message_data["from"]
                    if add_message(sender, message_data):
                        update_conversation_list()
                        if sender in chat_windows and chat_windows[sender].winfo_exists():
                            update_chat_window(sender)
                else:
                    messagebox.showerror("Error", response)
    except Exception as e:
        print("Subscription error:", e)
    finally:
        if subscription_socket is not None:
            subscription_socket.close()

def load_conversations():
    response = send_request(8, current_user)
    if response and response.startswith("success"):
        messages = ast.literal_eval(response.split(":", 1)[1]) #list of dict of messages
        if len(messages) != 0:
          for msg in messages:
            sender = msg["from"]
            add_message(sender, msg)
          update_conversation_list()
    else:
        messagebox.showerror("Error", response if response else "No response from server.")

# Update conversation list by skipping deleted messages entirely.
def update_conversation_list():
    conversation_list.delete(0, tk.END)
    for contact, msgs in conversations.items():
        visible = [m for m in msgs if m.get("status") != "deleted"]
        if visible:
            unread = sum(1 for m in visible if m["status"]=="unread" and m["from"]==contact)
        else:
            unread = 0
        unread_indicator = f" 🔴({unread} unread)" if unread > 0 else ""
        display = f"{contact}{unread_indicator}"
        conversation_list.insert(tk.END, display)

def open_chat():
    selection = conversation_list.curselection()
    if not selection:
        return
    contact = conversation_list.get(selection[0]).split()[0]
    chat_window(contact)

def chat_window(contact):
    # helper functions
    def refresh_chat_text():
        chat_text.configure(state=tk.NORMAL)
        chat_text.delete(1.0, tk.END)
        if contact in conversations:
            for m in conversations[contact]:
                if m.get("status") == "deleted":
                    continue
                sender_disp = "You" if m["from"]==current_user else m["from"]
                text = f"{sender_disp}: {m['message']}\n"
                chat_text.insert(tk.END, text)
        chat_text.configure(state=tk.DISABLED)

    def send_message():
        if can_send_message:
            message = message_entry.get().strip()
            if not message:
                return
            sender, recipient = current_user, contact
            response = send_request(4, f"{sender}|{recipient}|{message}")
            if response and response.startswith("success"):
                msg_obj = ast.literal_eval(response.split(':', 1)[1]) # msg_id, from, message, status
                add_message(contact, msg_obj)
                update_conversation_list()
                update_chat_window(contact)
                message_entry.delete(0, tk.END)

            else:
                messagebox.showerror("Error", response if response else "No response from server.")
        else:
            messagebox.showerror("Error", "Cannot send a new message until all unread messages are read")

    def on_message_double_click(event):
        index = chat_text.index(f"@{event.x},{event.y}")
        line_number = int(index.split(".")[0])
        visible_msgs = [m for m in conversations.get(contact, []) if m.get("status") != "deleted"]
        if line_number-1 < len(visible_msgs):
            msg = visible_msgs[line_number-1]
            if msg["from"]==current_user and msg["status"]=="unread":
                if messagebox.askyesno("Delete", "Unsend this message? \n\n" + f"{msg['message']}"):
                    sender, recipient, message_id = current_user, contact, msg["id"]
                    response = send_request(7, f"{sender}|{recipient}|{message_id}")
                    if response and response.startswith("success"):
                        for m in conversations[contact]:
                            if m["id"] == msg["id"]:
                                m["status"] = "deleted"
                                break
                        update_chat_window(contact)
                        update_conversation_list()
                    else:
                        messagebox.showerror("Error", response if response else "No response from server.")

    def save_undelivered():
        """
            Saves undelivered message in the message entry so that when user closes the chat window and then reopens, the undelivered message is still present
        """
        undelivered[contact] = message_entry.get().strip()
        return
    
    def update_read_batch_num():
        nonlocal read_batch_num, unread_counter
        read_batch_num = int(read_batch_num_new.get())
        unread_counter = 0
        send_request(6, f"{current_user}|{contact}|{read_batch_num}")
    
    # Chat_window setup
    if contact in chat_windows:
        if chat_windows[contact].winfo_exists():
            chat_windows[contact].lift()
            return
        else:
            del chat_windows[contact]
    chat_win = tk.Toplevel(root)
    chat_win.title(f"Chat with {contact}")
    chat_windows[contact] = chat_win
    chat_win.refresh_chat_text = refresh_chat_text
    chat_win.protocol("WM_DELETE_WINDOW", lambda: (save_undelivered(), chat_win.destroy(), update_conversation_list()))

    chat_text = scrolledtext.ScrolledText(chat_win, state=tk.DISABLED, height=15, width=50)
    chat_text.pack()
    chat_text.bind("<Double-Button-1>", on_message_double_click)

    message_entry = tk.Entry(chat_win, width=40)
    message_entry.insert(0, undelivered.get(contact, "")) # prints out the saved undelivered message
    message_entry.pack(pady=5)

    send_button = tk.Button(chat_win, text="Send", command=send_message)
    send_button.pack(pady=5)

    tk.Label(chat_win, text="Read the next")
    # number of messages to read at once selected by option menu
    DEFAULT_READ_BATCH_NUM = 5
    read_batch_num = 0
    read_batch_num_new = tk.StringVar()
    read_batch_num_new.set(DEFAULT_READ_BATCH_NUM) # default
    read_batch_num_dropdown = tk.OptionMenu(chat_win, read_batch_num_new, *range(1,31), command=lambda value: 
    read_batch_num_button.config(text=f"Read the next {value} messages"))
    read_batch_num_dropdown.pack(pady=10)
    read_batch_num_button = tk.Button(chat_win, text=f"Read the next {DEFAULT_READ_BATCH_NUM} messages", command=update_read_batch_num)
    read_batch_num_button.pack(pady=5)
    
    chat_text.configure(state=tk.NORMAL)
    chat_text.delete(1.0, tk.END)
    unread_counter = 0
    can_send_message = False # cannot send a message until all unreads are read
    for m_contact in conversations.get(contact, []):
        # if deleted, don't display
        if m_contact["status"] == "deleted":
            continue
        # if you sent the message or the message was read by the recipient, display the message
        elif m_contact["from"] == current_user or m_contact["status"] == "read": 
            # display message
            sender_disp = "You" if m_contact["from"]==current_user else m_contact["from"]
            text = f"{sender_disp}: {m_contact['message']}\n"
            chat_text.insert(tk.END, text)
        # if unread, wait for next batch of unread to read. If next bratch is released, mark them as read and display
        else: # if unread
            while unread_counter == read_batch_num:
                # Update tkinter's event loop to listen for events
                # because button that triggers update_read_batch_num is the only way 
                # to reset unread_counter
                chat_win.update()
            if m_contact["from"]==contact and m_contact["status"]=="unread" and unread_counter < read_batch_num:
                # mark as read
                m_contact["status"] = "read"
                unread_counter += 1
                # display message
                sender_disp = "You" if m_contact["from"]==current_user else m_contact["from"]
                text = f"{sender_disp}: {m_contact['message']}\n"
                chat_text.insert(tk.END, text)
    can_send_message = True
    update_conversation_list()
    chat_text.configure(state=tk.DISABLED)


def update_chat_window(contact):
    if contact in chat_windows and chat_windows[contact].winfo_exists():
        # Only mark as read messages from this specific contact.
        if any(m["from"]==contact and m["status"]=="unread" for m in conversations.get(contact, [])):
            send_request(6, f"{current_user}|{contact}|0")
            for m in conversations.get(contact, []):
                if m["from"] == contact and m["status"] == "unread":
                    m["status"] = "read"
            update_conversation_list()
        chat_windows[contact].refresh_chat_text()

def check_new_messages():
    if current_user:
        load_conversations()
        root.after(5000, check_new_messages)

def start_new_conversation():
    recipient = new_conversation_entry.get().strip()
    if not recipient:
        messagebox.showwarning("Input Error", "Recipient cannot be empty.")
        return
    if recipient == current_user:
        messagebox.showwarning("Input Error", "You cannot chat with yourself.")
        return

    # Check if the recipient exists.
    users_list = ast.literal_eval(send_request(3, "empty"))
    if recipient not in users_list:
        messagebox.showwarning("Input Error", f"User '{recipient}' does not exist.")
        return

    if recipient in conversations:
        chat_window(recipient)
    else:
        conversations[recipient] = []
        update_conversation_list()
        chat_window(recipient)

def delete_account(): 
    if messagebox.askyesno("Confirm", "Delete your account?"):
        response = send_request(9, current_user)
        if response and response.startswith("success"):
            messagebox.showinfo("Account Deleted", response)
            conversations.clear()
            chat_windows.clear()
            conversation_list.delete(0, tk.END)
            logout()
        else:
            messagebox.showerror("Error", response if response else "No response from server.")

def logout():
    global current_user, subscription_socket
    if current_user:
        response = send_request(10, current_user)
        if response is None: # send_request failed, stop logout
            return 
        if response.startswith("success"):
            current_user = None
            if subscription_socket:
                try:
                    subscription_socket.close()
                except Exception as e:
                    print(f"[ERROR] Failed to close subscription socket: {e}")
                    # Log the failure, but don't block the UI update
                    print("Warning: Unable to disconnect from the server properly.")
                    pass
                subscription_socket = None
            chat_frame.pack_forget()
            login_frame.pack()
            new_conversation_entry.delete(0, tk.END)
            undelivered.clear()
        else:
            messagebox.showerror("Error", response if response else "No response from server.")

def run_gui():
    root.title("Chat Application")
    root.geometry("400x500")

    # Login Frame
    tk.Label(login_frame, text="Username:").pack()

    username_options = ast.literal_eval(send_request(3, "empty"))
    username_entry["values"] = username_options
    username_entry.config(postcommand=lambda: update_username_suggestions(None, username_entry, username_entry_var))
    username_entry.pack()
    # Bind the KeyRelease event to update suggestions when typing
    username_entry.bind("<KeyRelease>", lambda event: update_username_suggestions(event, username_entry, username_entry_var))
    # Bind the FocusIn event to trigger suggestions when the combobox is clicked or gains focus
    username_entry.bind("<FocusIn>", lambda event: update_username_suggestions(event, username_entry, username_entry_var))

    tk.Label(login_frame, text="Password:").pack()
    password_entry.pack()
    tk.Button(login_frame, text="Login", command=login).pack(pady=5)
    tk.Button(login_frame, text="Register", command=register).pack(pady=5)
    login_frame.pack()

    # Chat Frame
    chat_label.pack()
    tk.Label(chat_frame, text="Enter New Recipient:").pack()

    new_conversation_entry["values"] = username_options
    new_conversation_entry.config(postcommand=lambda: update_username_suggestions(None, new_conversation_entry, new_conversation_entry_var))
    new_conversation_entry.pack()
    # Bind the KeyRelease event to update suggestions when typing
    new_conversation_entry.bind("<KeyRelease>", lambda event: update_username_suggestions(event, new_conversation_entry, new_conversation_entry_var))
    # Bind the FocusIn event to trigger suggestions when the combobox is clicked or gains focus
    new_conversation_entry.bind("<FocusIn>", lambda event: update_username_suggestions(event, new_conversation_entry, new_conversation_entry_var))
    tk.Button(chat_frame, text="Start New Chat", command=start_new_conversation).pack(pady=5)
    conversation_list.pack()
    conversation_list.bind("<Double-Button-1>", lambda _: open_chat())
    tk.Button(chat_frame, text="Logout", command=logout).pack(pady=5)
    tk.Button(chat_frame, text="Delete Account", command=delete_account).pack(pady=5)

    root.mainloop()

if __name__ == "__main__":
    run_gui()