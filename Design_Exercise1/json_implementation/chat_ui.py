import socket
import json
import tkinter as tk
from tkinter import messagebox, scrolledtext
from tkinter import ttk
import threading
import sys
import hashlib

CLIENT_VERSION = "1.0.0"

if sys.stdin.isatty():
    while True:
        SERVER_HOST = input("Enter server host: ").strip()
        if SERVER_HOST:
            break
    while True:
        try:
            SERVER_PORT = int(input("Enter server port: ").strip())
            break
        except ValueError:
            print("Invalid input. Please enter a valid port number.")
else:
    SERVER_HOST = "localhost"
    SERVER_PORT = 5001

current_user = None
conversations = {}
chat_windows = {}
subscription_socket = None
options = []
unsent_texts = {}


def hash_password(password):
    """
        Hash the given password.

    Params: 
    
        password: The password to hash.
    
    Return: 
    
        A SHA-256 hash of the password.
    """
    return hashlib.sha256(password.encode()).hexdigest()
def add_message(contact, msg):
    """
        Add a message to the list of messages for a given contact.

    Params:
    
        contact: The contact to add the message for.
        msg: The message to add.
    
    Return: 
        True if the message was added, False otherwise.
    """
    if contact not in conversations:
        conversations[contact] = []
    for i, existing in enumerate(conversations[contact]):
        if existing["id"] == msg["id"]:
            conversations[contact][i] = msg
            return True
    conversations[contact].append(msg)
    return True

def check_version_number():
    """
        Check that the version number matches between client and server

    Params:
    
        None

    Returns:

        conn or None: client socket if success, None if error or Exception
    """
    try: 
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn.connect((SERVER_HOST, SERVER_PORT))
        print(f"Successfully connected to server at {SERVER_HOST}:{SERVER_PORT}")
    except Exception as e:
        print(f"Error: Could not connect to {SERVER_HOST}:{SERVER_PORT}. Please ensure the server is running and reachable.")
        return None
    try:
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

def send_request(request):
    """
        Send a request to the server and return the response.

    Params:
    
        request: The request to send, a JSON-decodable dict.
    
    Returns: 
    
        response.decode() or None: response from the server or None if there is error in connection to server
    """
    client = check_version_number()
    if not client:
        messagebox.showerror("Error", f"Could not connect to {SERVER_HOST}:{SERVER_PORT}. Please ensure the server is running and reachable.")
        return None
    try:
        if hasattr(client.send, "reset_mock"):
            client.send.reset_mock()
        if hasattr(client.recv, "reset_mock"):
            client.recv.reset_mock()
        client.send(json.dumps(request).encode())
        response_data = client.recv(4096).decode()
        response = json.loads(response_data)
        client.close()
        return response
    except Exception as e:
        messagebox.showerror("Error", f"Connection failed: {e}")
        return None


def load_all_usernames():
    """
        Load all usernames from the server into the global options list.

    Params:

        None

    Returns:

        None
    
    """
    update_username_suggestions(None, username_combobox, username_var)
    if current_user:
        update_username_suggestions(None, recipient_combobox, recipient_var, exclude_self=True)

def update_username_suggestions(event, combobox, var, exclude_self=False):
    """
        Update the dropdown options for username based on user input.

    Params:

        event: event object that Tkinter automatically passes

        entry: ttk.Combobox object

        entry_var: tk.StringVar() object'

        exclude_self: bool

    Returns:

        None
    """
    typed = var.get().lower() if var.get() else ""
    response = send_request({"type": "list_users", "prefix": "*"})
    suggestions = response["users"] if response and response.get("status") == "success" else []
    if exclude_self and current_user in suggestions:
        suggestions.remove(current_user)
    if typed:
         suggestions = [s for s in suggestions if typed in s.lower()]
    combobox["values"] = suggestions

def login():
    """
        Login a user with the username and password from user input

        Params:

            None

        Returns:

            None
    """
    global current_user
    username = username_var.get().strip()
    password = password_entry.get().strip()
    if not username or not password:
        messagebox.showwarning("Input Error", "Username and password cannot be empty.")
        return
    response = send_request({"type": "login", "username": username, "password": hash_password(password)})
    if response and response["status"] == "success":
        current_user = username
        login_frame.pack_forget()
        chat_frame.pack()
        chat_label.config(text=f"Chat - Logged in as {username}")
        recipient_combobox["values"] = [u for u in options if u != current_user]
        load_conversations()
        check_new_messages()
        threading.Thread(target=subscribe_thread, daemon=True).start()
    else:
        messagebox.showerror("Login Failed", response["message"] if response else "No response from server.")

def register():
    """
        Register a new user with username and password from user input

        Params:

            None
        
        Returns:

            None

    """
    username = username_var.get().strip()
    password = password_entry.get().strip()
    if not username or not password:
        messagebox.showwarning("Input Error", "Username and password cannot be empty.")
        return
    response = send_request({"type": "register", "username": username, "password": hash_password(password)})
    if response and response["status"] == "success":
        messagebox.showinfo("Success", response["message"])
    else:
        messagebox.showerror("Registration Failed", response["message"] if response else "No response from server.")

def subscribe_thread():
    """
        Manages a subscription thread for receiving real-time messages.

        Params: 

            None

        Returns:

            None
    """
    global current_user, subscription_socket
    try:
        subscription_socket = check_version_number()
        if subscription_socket is not None:
            subscription_socket.send(json.dumps({"type": "subscribe", "username": current_user}).encode())
            while current_user:
                data = subscription_socket.recv(4096)
                if not data:
                    break
                msg = json.loads(data.decode())
                if msg.get("type") == "message":
                    message_data = msg["data"]
                    sender = message_data["from"]
                    if add_message(sender, message_data):
                        update_conversation_list()
                        if sender in chat_windows and chat_windows[sender].winfo_exists():
                            # For a deletion (unsend) event...
                            if message_data.get("status") == "deleted":
                                # Check if there are any unread messages from this sender.
                                unread = [m for m in conversations.get(sender, []) if m["from"] == sender and m["status"] == "unread"]
                                if unread:
                                    # Do not update the chat window; this way the recipient sees no change.
                                    continue
                            # Otherwise, do a normal update.
                            update_chat_window(sender)
            subscription_socket.close()
    except Exception as e:
        print("Subscription error:", e)
    finally:
        if subscription_socket is not None:
            subscription_socket.close()

def load_conversations():
    """
        Load all of the messages stored for current user
        
        Params:

            None 
        
        Returns:

            None
    """
    response = send_request({"type": "receive", "username": current_user})
    if response and response["status"] == "success":
        messages = response["messages"]
        for msg in messages:
            sender = msg["from"]
            add_message(sender, msg)
        update_conversation_list()
    else:
        messagebox.showerror("Error", response["message"] if response else "No response from server.")

def update_conversation_list():
    """
        Update conversation list by skipping deleted messages and showing number of unreads

        Params:

            None

        Returns:

            None
    """
    conversation_list.delete(0, tk.END)
    
    for contact, msgs in conversations.items():
        visible = [m for m in msgs if m.get("status") != "deleted"]
        unread = sum(1 for m in visible if m["status"] == "unread" and m["from"] == contact)
        unread_indicator = f" 🔴({unread} unread)" if unread > 0 else ""
        display = f"{contact}{unread_indicator}"
        conversation_list.insert(tk.END, display)

def open_chat():
    """
        Open chat window triggered by double clicking on conversation_list ListBox
        
        Params:

            None
        
        Returns:

            None
    """
    selection = conversation_list.curselection()
    if not selection:
        return
    contact = conversation_list.get(selection[0]).split()[0]
    chat_window(contact)

def chat_window(contact):
    """
        Display for the chat window, including printing messages to the chat window, send messages, read unread messages, unsend messages.

        Helper functions:

            refresh_chat_text(): refreshes the output of the chat window by rewriting the nondeleted messages

            send_message(): sends a message by sending the message to the server

            on_message_double_click(): unsend a message triggered by double click

            on_close_chat_window(): saves undelivered message in the message entry so that when user closes the chat window and then reopens, the undelivered message is still present

            update_read_batch_num(): updates read_batch_num and sends request to server to mark read messages as unread, triggered by pressing on read_batch_num_button
        
        Params:

            contact: username
        
        Returns:
        
            None
    """
    if contact in chat_windows:
        if chat_windows[contact].winfo_exists():
            chat_windows[contact].lift()
            return
        else:
            del chat_windows[contact]
    chat_win = tk.Toplevel(root)
    chat_win.title(f"Chat with {contact}")
    chat_windows[contact] = chat_win

    chat_text = scrolledtext.ScrolledText(chat_win, state=tk.DISABLED, height=15, width=50)
    chat_text.pack()
    message_entry = tk.Entry(chat_win, width=40)
    message_entry.insert(0, unsent_texts.get(contact, ""))
    message_entry.pack(pady=5)

    # Local variables for batch-read logic
    DEFAULT_READ_BATCH_NUM = 5
    read_batch_num = 0
    unread_counter = 0
    can_send_message = False
    read_batch_num_new = tk.StringVar()
    read_batch_num_new.set(DEFAULT_READ_BATCH_NUM)

    def update_read_batch_num():
        nonlocal read_batch_num, unread_counter
        read_batch_num = int(read_batch_num_new.get())  # Get new batch size
        unread_counter = 0  # Reset unread counter
        send_request({"type": "mark_read", "username": current_user, "contact": contact, "read_batch_num": read_batch_num})
        refresh_chat_text()  # Process batch reading correctly


    def refresh_chat_text():
        nonlocal unread_counter, can_send_message
        chat_text.configure(state=tk.NORMAL)
        chat_text.delete(1.0, tk.END)

        unread_counter = 0  # Reset unread count
        total_unread = sum(1 for m in conversations.get(contact, []) if m["from"] == contact and m["status"] == "unread")
        batch_processed = 0  # Tracks the number of unread messages processed in this batch

        for m in conversations.get(contact, []):
            if m.get("status") == "deleted":
                continue
            elif m["from"] == current_user or m["status"] == "read":
                sender_disp = "You" if m["from"] == current_user else m["from"]
                text = f"{sender_disp}: {m['message']}\n"
                chat_text.insert(tk.END, text)
            else:
                # Stop reading messages when batch limit is reached
                if batch_processed == read_batch_num:
                    break

                # Mark messages as read within the batch limit
                m["status"] = "read"
                batch_processed += 1
                total_unread -= 1  # Correctly decrement total unread count

                sender_disp = "You" if m["from"] == current_user else m["from"]
                text = f"{sender_disp}: {m['message']}\n"
                chat_text.insert(tk.END, text)
        chat_text.see(tk.END) # Keep the view at the bottom

        # Only allow sending messages if all unread messages are processed
        can_send_message = total_unread == 0  
        update_conversation_list()
        chat_text.configure(state=tk.DISABLED)


    def send_message():
        if can_send_message:
            message = message_entry.get().strip()
            if not message:
                return
            
            response = send_request({"type": "send", "sender": current_user, "recipient": contact, "message": message})
            if response and response["status"] == "success":
                msg_id = response.get("message_id", "")
                msg_obj = {"id": msg_id, "from": current_user, "message": message, "status": "unread"}
                add_message(contact, msg_obj)
                update_conversation_list()
                update_chat_window(contact)
                message_entry.delete(0, tk.END)
            else:
                messagebox.showerror("Error", response["message"] if response else "No response from server.")
        else:
            messagebox.showerror("Error", "Cannot send a new message until all unread messages are read.")
            
    send_button = tk.Button(chat_win, text="Send", command=send_message)
    send_button.pack(pady=5)

    read_batch_num_new = tk.StringVar()
    read_batch_num_new.set(DEFAULT_READ_BATCH_NUM)  # Default batch size
    read_batch_num_dropdown = tk.OptionMenu(
        chat_win, read_batch_num_new, *range(1, 31),
        command=lambda value: read_batch_num_button.config(text=f"Read the next {value} messages")
    )
    read_batch_num_dropdown.pack(pady=10)

    # Button to trigger batch reading
    read_batch_num_button = tk.Button(
        chat_win, text="Read the next 5 messages", command=update_read_batch_num
    )
    read_batch_num_button.pack(pady=5)

    refresh_chat_text()
    chat_win.refresh_chat_text = refresh_chat_text

    def on_message_double_click(event):
        index = chat_text.index(f"@{event.x},{event.y}")
        line_number = int(index.split(".")[0])
        visible_msgs = [m for m in conversations.get(contact, []) if m.get("status") != "deleted"]
        if line_number - 1 < len(visible_msgs):
            msg = visible_msgs[line_number - 1]
            if msg["from"] == current_user and msg["status"] == "unread":
                prompt = f"Unsend this message?\n\n\"{msg['message']}\""
                if messagebox.askyesno("Delete", prompt):
                    response = send_request({"type": "delete", "sender": current_user, "recipient": contact, "message_id": msg["id"]})
                    if response and response["status"] == "success":
                        for m in conversations[contact]:
                            if m["id"] == msg["id"]:
                                m["status"] = "deleted"
                                break
                        update_chat_window(contact)
                        update_conversation_list()
                    else:
                        messagebox.showerror("Error", response["message"] if response else "No response from server.")
    chat_text.after(100, lambda: chat_text.see(tk.END))
    chat_text.bind("<Double-Button-1>", on_message_double_click)

    def on_close_chat_window():
        unsent_texts[contact] = message_entry.get().strip()
        chat_win.destroy()
        update_conversation_list()
    chat_win.protocol("WM_DELETE_WINDOW", on_close_chat_window)


def update_chat_window(contact):
    """
        Update chat window by sending request to server to mark as read, and update status
        
        Params:

            contact: username
        
        Returns:

            None
    """
    if contact in chat_windows and chat_windows[contact].winfo_exists():
        unread_msgs = [m for m in conversations.get(contact, []) if m["from"] == contact and m["status"] == "unread"]
        if unread_msgs:
            send_request({"type": "mark_read", "username": current_user, "contact": contact})
            for m in conversations.get(contact, []):
                if m["from"] == contact and m["status"] == "unread":
                    m["status"] = "read"
            update_conversation_list()
        chat_windows[contact].refresh_chat_text()

def check_new_messages():
    """
        Periodically checks for new messages for the current user.

        Params:

            None
        
        Returns:

            None
    """
    if current_user:
        load_conversations()
        root.after(5000, check_new_messages)

def start_new_conversation():
    """
        Start a conversation with a recipient

        Params:

            None
        
        Returns:

            None
    """
    recipient = recipient_var.get().strip()
    if not recipient:
        messagebox.showwarning("Input Error", "Recipient cannot be empty.")
        return
    if recipient == "*":
        list_users()
        return
    if recipient == current_user:
        messagebox.showwarning("Input Error", "You cannot chat with yourself.")
        return

    response = send_request({"type": "list_users", "prefix": recipient})
    if response and response["status"] == "success":
        users_list = response["users"]
        if recipient not in users_list:
            messagebox.showwarning("Input Error", f"User '{recipient}' does not exist.")
            return
    else:
        messagebox.showerror("Error", "Failed to verify recipient.")
        return

    if recipient in conversations:
        chat_window(recipient)
    else:
        conversations[recipient] = []
        update_conversation_list()
        chat_window(recipient)

def list_users():
    """
        List all users in the system.

    Params:

        None

    Returns:

        None
    """
    response = send_request({"type": "list_users", "prefix": "*"})
    if response and response["status"] == "success":
        users_list = response["users"]
        messagebox.showinfo("Users", "\n".join(users_list))
    else:
        messagebox.showerror("Error", response["message"] if response else "No response from server.")

def delete_account():
    """
        Delete an account by clearing information for the user and sending request for deleting account to the server

        Params:

            None 

        Returns:

            None
    """
    if messagebox.askyesno("Confirm", "Delete your account?"):
        response = send_request({"type": "delete_account", "username": current_user})
        if response and response["status"] == "success":
            messagebox.showinfo("Account Deleted", "Your account was deleted.")
            conversations.clear()
            chat_windows.clear()
            conversation_list.delete(0, tk.END)
            logout()
        else:
            messagebox.showerror("Error", response["message"] if response else "No response from server.")

def logout():
    """
        Logout the current user, clear out certain information for the user, and send request for logging out of account to the server

        Params:

            None 

        Returns:

            None
    
    """
    global current_user, subscription_socket
    if current_user:
        send_request({"type": "logout", "username": current_user})
    current_user = None
    if subscription_socket:
        try:
            subscription_socket.close()
        except Exception:
            pass
        subscription_socket = None
    chat_frame.pack_forget()
    login_frame.pack()
    recipient_var.set("")
    load_all_usernames()
    unsent_texts.clear()

root = tk.Tk()
root.title("Chat Application")
root.geometry("400x500")

login_frame = tk.Frame(root)
tk.Label(login_frame, text="Username:").pack()

username_var = tk.StringVar()
username_combobox = ttk.Combobox(login_frame, textvariable=username_var)
username_combobox.config(postcommand=lambda: update_username_suggestions(None, username_combobox, username_var))
username_combobox.pack()
username_combobox.bind("<KeyRelease>", lambda e: update_username_suggestions(e, username_combobox, username_var))
username_combobox.bind("<FocusIn>", lambda e: update_username_suggestions(e, username_combobox, username_var))
tk.Label(login_frame, text="Password:").pack()
password_entry = tk.Entry(login_frame, show="*")
password_entry.pack()
tk.Button(login_frame, text="Login", command=login).pack(pady=5)
tk.Button(login_frame, text="Register", command=register).pack(pady=5)
login_frame.pack()

chat_frame = tk.Frame(root)
chat_label = tk.Label(chat_frame, text="Chat")
chat_label.pack()
tk.Label(chat_frame, text="Enter New Recipient:").pack()

recipient_var = tk.StringVar()
recipient_combobox = ttk.Combobox(chat_frame, textvariable=recipient_var, width=30)
recipient_combobox.config(postcommand=lambda: update_username_suggestions(None, recipient_combobox, recipient_var, exclude_self=True))
recipient_combobox.pack()
recipient_combobox.bind("<KeyRelease>", lambda e: update_username_suggestions(e, recipient_combobox, recipient_var, exclude_self=True))
recipient_combobox.bind("<FocusIn>", lambda e: update_username_suggestions(e, recipient_combobox, recipient_var, exclude_self=True))
tk.Button(chat_frame, text="Start New Chat", command=start_new_conversation).pack(pady=5)

conversation_list = tk.Listbox(chat_frame, height=10, width=40)
conversation_list.pack()
conversation_list.bind("<Double-Button-1>", lambda _: open_chat())
tk.Button(chat_frame, text="Logout", command=logout).pack(pady=5)
tk.Button(chat_frame, text="Delete Account", command=delete_account).pack(pady=5)

if __name__ == '__main__':
    load_all_usernames()
    root.mainloop()