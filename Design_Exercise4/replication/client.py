import grpc
import hashlib
import tkinter as tk
from tkinter import messagebox, scrolledtext
import threading
import chat_pb2
import chat_pb2_grpc
import sys
import argparse

from chat_ui_objects import root, login_frame, username_entry_var, username_entry, password_entry, chat_frame, chat_label, new_conversation_entry_var, new_conversation_entry, conversation_list
from server import ports

# # Get SERVER_HOST and SERVER_PORT from CLI if file ran from terminal. 
# # Otherwise use the default values (so that functions run for tests)
# if sys.stdin.isatty():
#     while True:
#         SERVER_HOST = input("Enter server host: ").strip()
#         if SERVER_HOST:
#             break  # Ensure the user enters a non-empty host

#     while True:
#         try:
#             SERVER_PORT = int(input("Enter server port: ").strip())
#             break  # Ensure the user enters a valid integer port
#         except ValueError:
#             print("Invalid input. Please enter a valid port number.")

# else:
#     SERVER_HOST = "localhost"
#     SERVER_PORT = 5001

CLIENT_VERSION = "1.0.0"

current_user = None
# conversations: key=contact, value=list of message dicts {id, from, message, status}
conversations = {}
chat_windows = {}   # open chat windows
undelivered = {} # saves undelivered message
subscription_active = False
all_host_port_pairs = []

subscription_thread = None
subscription_call = None

SERVER_HOST = ""
SERVER_PORT = ""
stub = None

def connect_to_leader():
    global SERVER_HOST, SERVER_PORT, stub, subscription_thread, subscription_call, subscription_active
    print('checking leader')
    noleader = True
    for server in all_host_port_pairs:
        try:
            temp_channel = grpc.insecure_channel(server)
            temp_stub = chat_pb2_grpc.ChatServiceStub(temp_channel)
            response = temp_stub.GetLeaderInfo(chat_pb2.GetLeaderInfoRequest())
            leader_host, leader_port = response.info.split(':')
            noleader = False

            # update leader if necessary
            if SERVER_HOST != leader_host or SERVER_PORT != leader_port:
                SERVER_HOST = leader_host
                SERVER_PORT = leader_port
                print('NEW LEADER:', SERVER_HOST, SERVER_PORT)
                channel = grpc.insecure_channel(f"{SERVER_HOST}:{SERVER_PORT}")
                stub = chat_pb2_grpc.ChatServiceStub(channel)
                stub.LoadActiveUsersAndSubscribersFromPersistent(chat_pb2.Empty())
                check_new_messages() # restart the check new messages loop

                # If the subscription thread is still active, cancel it.
                subscription_active = False
                if subscription_call is not None:
                    try:
                        subscription_call.cancel()
                        print("Canceled stale subscription call.")
                    except Exception as e:
                        print("Error canceling subscription call:", e)
                # Restart a fresh subscription thread.
                print("Logging globals for subscription",subscription_active, subscription_thread, subscription_call)
                subscription_active = True
                print("Restarting subscription thread.")
                subscription_thread = threading.Thread(target=subscribe_thread, daemon=True)
                subscription_thread.start()
            break
        except:
            print(f"Failed to connect to {server}")
            continue  # Try next server

    if noleader:
        print('No leader found')
        sys.exit(1)
    root.after(5000, connect_to_leader)

def hash_password(password):
    """
        Hash the given password.

        Params:

            password: The password to hash.
        Returns:

            A SHA-256 hash of the password.
    """
    return hashlib.sha256(password.encode()).hexdigest()

def add_message(contact, msg):
    """
        Add a message if its ID isn’t already present, or update it if it exists.

        Params:

            contact: username

            msg: message {id, from, message, status} that you like to add to conversations

        Returns:

            True
    """
    if contact not in conversations:
        conversations[contact] = []
    for i, existing in enumerate(conversations[contact]):
        if existing["id"] == msg["id"]:
            conversations[contact][i] = msg  # update the message (e.g. mark as deleted)
            return True
    conversations[contact].append(msg)
    return True

def check_version_number():
    """
        Checks that version number matches between client and server

        Params:

            None 

        Returns:

            True or None: True if success, None if error
    """
    # Check connection
    try: 
       response = stub.CheckVersion(chat_pb2.Version(version=CLIENT_VERSION))
       if not response.success:
           print(f"Error: {response.message}") 
           return None
       
       print(f"Successfully connected to server at {SERVER_HOST}:{SERVER_PORT} {response.message}")
       return True
    except grpc.RpcError as e:
        print(f"Error: {e.details()}")
        return None

def update_username_suggestions(event, entry, entry_var):
    """
        Update the dropdown options for username based on user input.

        Params:

            event: event object that Tkinter automatically passes

            entry: ttk.Combobox object

            entry_var: tk.StringVar() object

        Returns:

            None
    """
    typed = entry_var.get().lower()
    
    try:
        response = stub.ListUsers(chat_pb2.ListUsersRequest())
        username_options = list(response.users)
    except Exception:
        username_options = []  # Handle bad responses safely

    if typed == "":
        entry["values"] = username_options  # Reset to all options
    else:
        filtered = [item for item in username_options if typed in item.lower()]
        entry["values"] = filtered

def login():
    """
        Login a user with the username and password from user input

        Params:

            None

        Returns:

            None
    """
    global current_user, subscription_active, subscription_thread
    username = username_entry.get().strip()
    password = password_entry.get().strip()
    if not username or not password:
        messagebox.showwarning("Input Error", "Username and password cannot be empty.")
        return
    response = stub.Login(chat_pb2.LoginRequest(username=username, password=hash_password(password))).message
    if response and response.startswith("success"):
        current_user = username
        login_frame.pack_forget()
        chat_frame.pack()
        chat_label.config(text=f"Chat - Logged in as {username}")
        load_conversations()
        check_new_messages()
        subscription_active = True
        subscription_thread = threading.Thread(target=subscribe_thread, daemon=True)
        subscription_thread.start()
        username_entry.delete(0, tk.END)
        password_entry.delete(0, tk.END)
    else:
        messagebox.showerror("Login Failed", response if response else "No response from server.")

def register():
    """
        Register a new user with username and password from user input

        Params:

            None
        
        Returns:

            None

    """
    username = username_entry.get().strip()
    password = password_entry.get().strip()
    if not username or not password:
        messagebox.showwarning("Input Error", "Username and password cannot be empty.")
        return
    response = stub.Register(chat_pb2.RegisterRequest(username=username, password=hash_password(password))).message
    if response and response.startswith("success"):
        messagebox.showinfo("Success", response)
    else:
        messagebox.showerror("Registration Failed", response if response else "No response from server.")

def subscribe_thread():
    """
        Manages a subscription thread for receiving real-time messages.

        Params: 

            None

        Returns:

            None
    """
    global subscription_active, subscription_call, subscription_thread
    thread_id = threading.current_thread().ident
    print(f"[{current_user if current_user else 'Unknown'}] Starting subscribe_thread, Thread ID: {thread_id}")
    if not current_user:
        return
    request = chat_pb2.SubscribeRequest(username=current_user)
    try:
        subscription_call = stub.Subscribe(request)
        for message in subscription_call:
            if not subscription_active:
                print(f"[{current_user}] Subscription thread exiting because subscription_active is False.")
                break
            # Log received message details.
            print(f"[{current_user}] Received live message: id={message.id}, from={message.sender}, text={message.message}, Thread ID: {thread_id}")
            sender = message.sender
            msg_data = {"id": message.id, "from": sender, "message": message.message, "status": message.status}
            if add_message(sender, msg_data):
                print(f"[{current_user}] Message added to conversation with {sender}, Thread ID: {thread_id}.")
                update_conversation_list()
                if sender in chat_windows and chat_windows[sender].winfo_exists():
                    update_chat_window(sender)
    except grpc.RpcError as e:
        print(f"[{current_user}] Subscription error: {e} (Thread ID: {thread_id})")
    finally:
        subscription_call = None
        subscription_thread = None
        print(f"[{current_user}] Subscription thread (ID: {thread_id}) is terminating.")

def load_conversations():
    """
        Load all of the messages stored for current user
        
        Params:

            None 
        
        Returns:

            None
    """
    try:
        response = stub.ReceiveMessages(chat_pb2.ReceiveMessagesRequest(username=current_user))
    except grpc.RpcError as e:
        print("load_conversations error:", e)
        return  # Skip this round and try again later.
    messages = [{'id': m.id, 'from': m.sender, 'message': m.message, 'status': m.status} for m in response.messages]
    if response and response.status == "success":
        if len(messages) != 0:
            for msg in messages:
                sender = msg["from"]
                add_message(sender, msg)
            update_conversation_list()
    else:
        messagebox.showerror("Error", response.status if response.status else "No response from server.")

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
        if visible:
            unread = sum(1 for m in visible if m["status"]=="unread" and m["from"]==contact)
        else:
            unread = 0
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

            save_undelivered(): saves undelivered message in the message entry so that when user closes the chat window and then reopens, the undelivered message is still present

            update_read_batch_num(): updates read_batch_num and sends request to server to mark read messages as unread, triggered by pressing on read_batch_num_button
        
        Params:

            contact: username
        
        Returns:
        
            None
    """

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
                chat_text.see(tk.END) # Keep the view at the bottom
        chat_text.configure(state=tk.DISABLED)

    def send_message():
        if can_send_message:
            message = message_entry.get().strip()
            if not message:
                return
            sender, recipient = current_user, contact
            response = stub.SendMessage(chat_pb2.SendMessageRequest(sender=sender, recipient=recipient, message=message))
            if response and response.status == "success":
                msg_id = response.message_id
                msg_obj = {"id": msg_id, "from": current_user, "message": message, "status": "unread"}
                add_message(contact, msg_obj)
                update_conversation_list()
                update_chat_window(contact)
                message_entry.delete(0, tk.END)
            else:
                messagebox.showerror("Error", response.status if response.status else "No response from server.")
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
                    response = stub.DeleteUnreadMessage(chat_pb2.DeleteUnreadMessageRequest(sender=sender, recipient=recipient, message_id=message_id))
                    if response and response.status == "success":
                        for m in conversations[contact]:
                            if m["id"] == msg["id"]:
                                m["status"] = "deleted"
                                break
                        update_chat_window(contact)
                        update_conversation_list()
                    else:
                        messagebox.showerror("Error", response.message if response.message else "No response from server.")

    def save_undelivered():
        undelivered[contact] = message_entry.get().strip()
        return
    
    def update_read_batch_num():
        nonlocal read_batch_num, unread_counter
        read_batch_num = int(read_batch_num_new.get())
        unread_counter = 0
        stub.MarkRead(chat_pb2.MarkReadRequest(username=current_user, contact=contact, batch_num=read_batch_num))

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
    chat_text.after(100, lambda: chat_text.see(tk.END))
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
    """
        Update chat window by sending request to server to mark as read, and update status
        
        Params:

            contact: username
        
        Returns:

            None
    """
    if contact in chat_windows and chat_windows[contact].winfo_exists():
        # Only mark as read messages from this specific contact.
        if any(m["from"]==contact and m["status"]=="unread" for m in conversations.get(contact, [])):
            stub.MarkRead(chat_pb2.MarkReadRequest(username=current_user, contact=contact, batch_num=0))
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
    recipient = new_conversation_entry.get().strip()
    if not recipient:
        messagebox.showwarning("Input Error", "Recipient cannot be empty.")
        return
    if recipient == current_user:
        messagebox.showwarning("Input Error", "You cannot chat with yourself.")
        return

    # Check if the recipient exists.
    response = stub.ListUsers(chat_pb2.ListUsersRequest())
    users_list = list(response.users)
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
    """
        Delete an account by clearing information for the user and sending request for deleting account to the server

        Params:

            None 

        Returns:

            None
    """
    if messagebox.askyesno("Confirm", "Delete your account?"):
        response = stub.DeleteAccount(chat_pb2.DeleteAccountRequest(username=current_user)).message
        if response and response.startswith("success"):
            messagebox.showinfo("Account Deleted", response)
            conversations.clear()
            chat_windows.clear()
            conversation_list.delete(0, tk.END)
            logout()
        else:
            messagebox.showerror("Error", response if response else "No response from server.")

def logout():
    """
        Logout the current user, clear out certain information for the user, and send request for logging out of account to the server

        Params:

            None 

        Returns:

            None
    
    """
    global current_user, subscription_active, conversations, chat_windows
    if current_user:
        response = stub.Logout(chat_pb2.LogoutRequest(username=current_user)).message
        if response.startswith("success"):
            current_user = None
            subscription_active = False
            # Close all open chat windows
            for win in list(chat_windows.values()):
                if win.winfo_exists():
                    win.destroy()
            chat_windows.clear()
            # Clear conversation data and update UI
            conversations.clear()
            conversation_list.delete(0, tk.END)
            undelivered.clear()
            chat_frame.pack_forget()
            login_frame.pack()
        else:
            messagebox.showerror("Error", response or "No response from server.")


def run_gui():
    """
        Set up the GUI elements

        Params:

            None 

        Returns:

            None
    """

    connect_to_leader()

    if not check_version_number():
        sys.exit(1)

    root.title("Chat Application")
    root.geometry("400x500")

    # Login Frame
    tk.Label(login_frame, text="Username:").pack()

    try:
        response = stub.ListUsers(chat_pb2.ListUsersRequest())
        username_options = list(response.users)
    except Exception as e:
        print(f"Error: {e}")
        return 
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
    parser = argparse.ArgumentParser(description="Start a specific client instance.")
    parser.add_argument("--all_ips", type=str, required=True,
                        help="Comma-separated list of external IP addresses for all servers (order: server1,server2,server3)")
    args = parser.parse_args()
    all_ips = args.all_ips.split(",")
    all_host_port_pairs = [f"{all_ips[i]}:{ports[i+1]}" for i in range(len(all_ips))]
    run_gui()