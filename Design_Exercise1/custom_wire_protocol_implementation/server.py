import socket
import struct
import threading
import hashlib
import uuid
import atexit


HOST = "0.0.0.0"
SERVER_PORT = 5001

# User data storage
users = {}
# Subscriber tracking for real-time delivery
subscribers = {}
subscribers_lock = threading.Lock()

def clear_users():
    """
      Clear stored users and messages
    """
    users.clear()

# Clear users automatically when the program terminates.
atexit.register(clear_users)

def hash_password(password):
    """
      Hash the given password.

      Params:
        password: The password to hash.
      Returns:
        A SHA-256 hash of the password.
    """
    return hashlib.sha256(password.encode()).hexdigest()

def handle_register(msg_data):
    """
      Handle a registration request

      Params:
        msg_data: data from client containig username and password separated by '|'.
      Returns:
        response: string for status of registration
    """
    username, password = msg_data.split('|')
    if username in users:
        response = "error: This username is unavailable"
    else:
        users[username] = {"password": hash_password(password), "messages": []}
        response = "success: Account created"
    return response

def handle_login(msg_data):
    """
      Handle a login request

      Params:
        msg_data: data from client containing username and password separated by '|'.
      Returns:
        response: string for status of login
    """
    username, password = msg_data.split('|')
    password = hash_password(password)
    if username in users and users[username]["password"] == password and not users[username].get("deleted", False):
        unread_messages = sum(1 for m in users[username]["messages"] if m["status"] == "unread")
        response = f"success: Logged in. Unread messages: {unread_messages}"
    else:
        response = "error: Invalid username or password"
    return response

def handle_list_users(msg_data):
    """
      Handle a list user request

      Params:
        msg_data: data from client containing the prefix you are trying to match with
      Returns:
        response: string for status of matching and list of all of the matched users
    """
    prefix = msg_data
    # matched = [u for u in users.keys() if u.startswith(prefix)] if prefix != "*" else list(users.keys())
    if prefix == "*":
        matched = [u for u, data in users.items() if not data.get("deleted", False)]
    else:
        matched = [u for u, data in users.items() if u.startswith(prefix) and not data.get("deleted", False)]
    response = "success:"+"\n".join(matched)
    return response

def handle_send(msg_data):
    """
      Handle sending a message

      Params:
        msg_data: data from client containing sender, recipient, and message separated by '|'
      Returns:
        response: string for status of sending a message
    """
    sender, recipient, message = msg_data.split('|', 2)
    if recipient in users:
        if users[recipient].get("deleted", False):
          response = f"error: User no longer exists."
        else:
          msg = {"id": str(uuid.uuid4()), "from": sender, "message": message, "status": "unread"}
          users[recipient]["messages"].append(msg)
          with subscribers_lock:
              if recipient in subscribers:
                  sub = subscribers[recipient]
                  with sub["cond"]:
                      sub["queue"].append(msg)
                      sub["cond"].notify()
          response = f"success:{str(msg)}"
    else:
        response = "error: Recipient not found"
    return response

def handle_subscribe(conn, msg_data):
    """
      Handles a user's subscription request.

      Params:
        conn: Client socket
        msg_data: data from client containing the username of the subscribing client.

      Returns:
        None
    """
    username = msg_data
    if username not in users:
        conn.send("error: User not found.".encode())
        return

    # Register the subscriber
    with subscribers_lock:
        subscribers[username] = {"conn": conn, "cond": threading.Condition(), "queue": []}

    # Wait for messages and send them to the user
    while True:
        with subscribers[username]["cond"]:
            while not subscribers[username]["queue"]:
                subscribers[username]["cond"].wait()
            msg = subscribers[username]["queue"].pop(0)

        try:
            conn.send(f"success:{str(msg)}".encode())
        except Exception:
            break
    
    # Clean up the subscriber when loop exits
    with subscribers_lock:
        if username in subscribers:
            del subscribers[username]

def handle_mark_read(msg_data):
    """
      Handle a mark read request

      Params:
        msg_data: data from client containing username and contact
      Returns:
        response: string for status of marking read
    """
    username, contact = msg_data.split('|')
    if username in users:
        count = 0
        for msg in users[username]["messages"]:
            if msg["from"] == contact and msg["status"] == "unread":
                msg["status"] = "read"
                count += 1
        response = f"success: Marked {count} messages as read."
    else:
        response = "error: User not found."
    return response

def handle_delete_unread_message(msg_data):
    """
      Handle a delete unread message request

      Params:
        msg_data: data from client containing sender, recipient, msg_id
      Returns:
        response: string for status of deleting an unread message
    """
    sender, recipient, msg_id = msg_data.split('|')
    if recipient in users:
        found = False
        for msg in users[recipient]["messages"]:
            if msg["id"] == msg_id and msg["from"] == sender and msg["status"] == "unread":
                msg["status"] = "deleted"
                found = True
                response = "success: Message deleted."
                with subscribers_lock:
                    if recipient in subscribers:
                        sub = subscribers[recipient]
                        with sub["cond"]:
                            sub["queue"].append({"id": msg_id, "from": sender, "message": "", "status": "deleted"})
                            sub["cond"].notify()
                break
        if not found:
            response = "error: Message not found or already read."
    else:
        response = "error: Recipient not found."
    return response

def handle_receive_messages(msg_data):
    """
      Handle receive messages request

      Params:
        msg_data: data from client containing username
      Returns:
        response: string for status of receiving messages. If success, it also contains the list of messages
    """
    username = msg_data
    if username in users:
        messages = str(users[username]["messages"])
        response = f"success:{messages}"
    else:
        response = "error: User not found."
    return response

def handle_delete_account(msg_data):
    """
      Handle delete account request

      Params:
        msg_data: data from client containing username
      Returns:
        response: string for status of deleting account
    """
    username = msg_data
    if username in users and not users[username].get("deleted", False):
        users[username]["deleted"] = True
        with subscribers_lock:
            if username in subscribers:
                del subscribers[username]
        response = f"success: Your account '{username}' was deleted."
    else:
        response = f"error: User not found or already deleted."
    return response

def handle_client(conn, addr):
    print(f"[NEW CONNECTION] {addr} connected.")
    while True:
        try:
            request_type_data = conn.recv(4)
            if not request_type_data:
                return
            
            msg_type = struct.unpack("!I", request_type_data)[0]
            print('MSG_TYPE', msg_type)
            msg_data = conn.recv(4096).decode()

            if msg_type == 1:  # Register
                response = handle_register(msg_data)
                
            elif msg_type == 2:  # Login
                response = handle_login(msg_data)
            
            elif msg_type == 3:  # List Users
                response = handle_list_users(msg_data)
            
            elif msg_type == 4:  # Send Message
                response = handle_send(msg_data)
            
            elif msg_type == 5:  # Subscribe
                handle_subscribe(conn, msg_data)
                break # Exit from handling subscription
            
            elif msg_type == 6:  # Mark Read
                response = handle_mark_read(msg_data)
            
            elif msg_type == 7:  # Delete Unread Message
                response = handle_delete_unread_message(msg_data)

            elif msg_type == 8:  # Receive Messages
                response = handle_receive_messages(msg_data)
                
            elif msg_type == 9: # Delete account
                response = handle_delete_account(msg_data)
            else:
                response = "Unknown request type"
            
            if msg_type != 5: # not subscribe
                conn.send(response.encode())
        except Exception as e:
            print(f"[ERROR] {e}")
            break
    conn.close()
    print(f"[DISCONNECTED] {addr} disconnected.")

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, SERVER_PORT))
    server.listen(5)
    print(f"[SERVER STARTED] Listening on port {SERVER_PORT}...")
    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()
        print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}")

if __name__ == "__main__":
    start_server()
