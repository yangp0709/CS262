import socket
import tkinter as tk
from tkinter import messagebox, scrolledtext
import threading
import struct
import ast

SERVER_HOST = "localhost"
SERVER_PORT = 5001

current_user = None
# conversations: key=contact, value=list of message dicts {id, from, message, status}
conversations = {}
chat_windows = {}   # open chat windows
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

def send_request(request_type, data):
    """Send a request to the server using a custom binary protocol."""
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((SERVER_HOST, SERVER_PORT))
        
        # Pack data using struct
        message = struct.pack("!I", request_type) + data.encode()
        client.send(message)
        
        # Receive response
        response = client.recv(4096)
        client.close()
        return response.decode()
    except Exception as e:
        messagebox.showerror("Error", f"Connection failed: {e}")
        return None

def update_username_suggestions(event=None):
    text = username_entry.get().strip()
    if text == "":
        suggestions_listbox.delete(0, tk.END)
        return
    prefix = text
    response = send_request(3, prefix) 
    if response and response.startswith("success"):
        suggestions_listbox.delete(0, tk.END)
        users_list = response.split(':')[1].split('\n')
        for user in users_list:
            suggestions_listbox.insert(tk.END, user)
    else:
        suggestions_listbox.delete(0, tk.END)

def on_suggestion_select(event):
    selection = suggestions_listbox.curselection()
    if selection:
        username_entry.delete(0, tk.END)
        username_entry.insert(0, suggestions_listbox.get(selection[0]))
        suggestions_listbox.delete(0, tk.END)

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
        subscription_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        subscription_socket.connect((SERVER_HOST, SERVER_PORT))
        request_type = 5
        data = current_user
        message = struct.pack("!I", request_type) + data.encode()
        subscription_socket.send(message)

        while current_user:
            response = subscription_socket.recv(4096)
            response = response.decode()

            if response and response.startswith("success"):
                message_data = ast.literal_eval(response.split(':', 1)[1])
                print("MESSAGE_DATA:", message_data, type(message_data))
                sender = message_data["from"]
                if add_message(sender, message_data):
                    update_conversation_list()
                    if sender in chat_windows and chat_windows[sender].winfo_exists():
                        update_chat_window(sender)
            else:
                messagebox.showerror("Error", response)
        subscription_socket.close()
    except Exception as e:
        print("Subscription error:", e)

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
    if contact in chat_windows:
        if chat_windows[contact].winfo_exists():
            chat_windows[contact].lift()
            return
        else:
            del chat_windows[contact]
    chat_win = tk.Toplevel(root)
    chat_win.title(f"Chat with {contact}")
    chat_windows[contact] = chat_win

    # Mark incoming messages as read when opening chat.
    if any(m["from"]==contact and m["status"]=="unread" for m in conversations.get(contact, [])):
        send_request(6, f"{current_user}|{contact}")
        for m in conversations.get(contact, []):
            if m["from"]==contact and m["status"]=="unread":
                m["status"] = "read"
        update_conversation_list()

    chat_text = scrolledtext.ScrolledText(chat_win, state=tk.DISABLED, height=15, width=50)
    chat_text.pack()

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
    refresh_chat_text()
    chat_win.refresh_chat_text = refresh_chat_text

    message_entry = tk.Entry(chat_win, width=40)
    message_entry.pack(pady=5)

    def send_message():
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
    send_button = tk.Button(chat_win, text="Send", command=send_message)
    send_button.pack(pady=5)

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
    chat_text.bind("<Double-Button-1>", on_message_double_click)

    chat_win.protocol("WM_DELETE_WINDOW", lambda: (chat_win.destroy(), update_conversation_list()))

def update_chat_window(contact):
    if contact in chat_windows and chat_windows[contact].winfo_exists():
        # Only mark as read messages from this specific contact.
        unread_msgs = [m for m in conversations.get(contact, []) if m["from"] == contact and m["status"] == "unread"]
        if unread_msgs:
            send_request(6, f"{current_user}|{contact}")
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
    if recipient == "*":
        list_users()
        return
    if recipient == current_user:
        messagebox.showwarning("Input Error", "You cannot chat with yourself.")
        return

    # Check if the recipient exists.
    response = send_request(3, recipient)
    if response and response.startswith("success"):
        users_list = response.split(':')[1].split('\n')
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
    response = send_request(3, "*")
    if response and response.startswith("success"):
        users_list = response.split(':')[1]
        messagebox.showinfo("Users", users_list)
    else:
        messagebox.showerror("Error", response if response else "No response from server.")

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
    current_user = None
    if subscription_socket:
        try:
            subscription_socket.close()
        except Exception:
            pass
        subscription_socket = None
    chat_frame.pack_forget()
    login_frame.pack()
    new_conversation_entry.delete(0, tk.END)

root = tk.Tk()
root.title("Chat Application")
root.geometry("400x500")

# Login Frame
login_frame = tk.Frame(root)
tk.Label(login_frame, text="Username:").pack()
username_entry = tk.Entry(login_frame)
username_entry.pack()
# Bind key release to update suggestions
username_entry.bind("<KeyRelease>", update_username_suggestions)
suggestions_listbox = tk.Listbox(login_frame, height=4, width=30)
suggestions_listbox.pack()
suggestions_listbox.bind("<<ListboxSelect>>", on_suggestion_select)

tk.Label(login_frame, text="Password:").pack()
password_entry = tk.Entry(login_frame, show="*")
password_entry.pack()
tk.Button(login_frame, text="Login", command=login).pack(pady=5)
tk.Button(login_frame, text="Register", command=register).pack(pady=5)
login_frame.pack()

# Chat Frame
chat_frame = tk.Frame(root)
chat_label = tk.Label(chat_frame, text="Chat")
chat_label.pack()
new_conversation_entry = tk.Entry(chat_frame, width=30)
new_conversation_entry.pack()
tk.Button(chat_frame, text="Start New Chat", command=start_new_conversation).pack(pady=5)
conversation_list = tk.Listbox(chat_frame, height=10, width=40)
conversation_list.pack()
conversation_list.bind("<Double-Button-1>", lambda _: open_chat())
tk.Button(chat_frame, text="Logout", command=logout).pack(pady=5)
tk.Button(chat_frame, text="Delete Account", command=delete_account).pack(pady=5)

root.mainloop()
