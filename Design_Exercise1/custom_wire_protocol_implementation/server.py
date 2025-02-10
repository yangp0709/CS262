import socket
import struct
import threading
import hashlib
import uuid
import atexit


HOST = "0.0.0.0"
SERVER_PORT = 5001
VERSION = "1.0.0"

# User data storage
users = {}
# Subscriber tracking for real-time delivery
active_users = set()
active_users_lock = threading.Lock()
subscribers = {}
subscribers_lock = threading.Lock()

def handle_exit():
    """
      Clear stored users, messages, and subscribers

      Params:
        None
      Returns:
        None
    """
    print("[INFO] Shutting down server gracefully...")
    users.clear()
    for conn in subscribers.values():
        try:
            conn.close()  # Ensure all connections are closed properly
        except Exception as e:
            print(f"[ERROR] Failed to close connection: {e}")
    print("[INFO] All connections closed.")


# Clear users automatically when the program terminates.
atexit.register(handle_exit)

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
        with active_users_lock:
            if username in active_users:
                response = "error: User already logged in"
                return response
            else:
                active_users.add(username)
        unread_messages = sum(1 for m in users[username]["messages"] if m["status"] == "unread")
        response = f"success: Logged in. Unread messages: {unread_messages}"
    else:
        response = "error: Invalid username or password"
    return response

def handle_list_users():
    """
      Returns a list of active users

      Params:
        None
      Returns:
        response: string of list of active users
    """
    active_users_list = str([u for u, data in users.items() if not data.get("deleted", False)])
    return active_users_list

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

def handle_subscribe(conn, addr, msg_data):
    """
      Handles a user's subscription request.

      Params:
        conn: Client socket
        addr: Address of client
        msg_data: data from client containing the username of the subscribing client.

      Returns:
        None
    """
    username = msg_data
    if username not in users:
        try:
            conn.send("error: User not found.".encode())
        except Exception as e:
            print(f"[ERROR] Error sending data to {addr}: {e}")
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
            print(f"[ERROR] Error sending data to {addr}: {e}")
            break
    
    # Clean up the subscriber when loop exits
    with subscribers_lock:
        if username in subscribers:
            del subscribers[username]

def handle_mark_read(msg_data):
    """
      Handle a mark read request

      Params:
        msg_data: data from client containing username, contact, and read_batch_num
      Returns:
        response: string for status of marking read
    """
    username, contact, read_batch_num = msg_data.split('|')
    read_batch_num = int(read_batch_num) # if 0, that means mark read for all unreads (no batching)
    if username in users:
        count = 0
        for msg in users[username]["messages"]:
            if msg["from"] == contact and msg["status"] == "unread" and (count < read_batch_num or read_batch_num == 0):
                msg["status"] = "read"
                count += 1
            if read_batch_num != 0 and count == read_batch_num:
                break
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

def handle_logout(msg_data):
    """
      Handle log out account request

      Params:
        msg_data: data from client containing username
      Returns:
        response: string fro status of logging out
    """
    username = msg_data 
    with active_users_lock:
        try:
            active_users.remove(username)
            response = "success: Logged out."
        except Exception:
            response = "error: Failed to log out. Username does not exist in active users."
    return response

def handle_client(conn, addr):
    """
      Handle communication with connected client

      Params:
        conn: The socket object representing the client connection.
        addr: A tuple containing the client's IP address and port number.
      Returns:
        None
    """
    print(f"[NEW CONNECTION] {addr} connected.")
    try:
        # Expect the client to send its version number first
        client_version_data = conn.recv(32)
        if not client_version_data:
            return 
        client_version = client_version_data.decode("utf-8").strip()
        print('client_version', client_version)
        if client_version != VERSION:
            error_msg = f"error: Version mismatch. Server: {VERSION}, Client: {client_version}"
            conn.send(error_msg.encode())
            conn.close()
            print(f"[DISCONNECTED] {addr} due to version mismatch")
            return 
        conn.send("success: Version matched".encode())

        while True:
            try:
                request_type_data = conn.recv(4)
                if not request_type_data:
                    return
                
                try:
                    msg_type = struct.unpack("!I", request_type_data)[0]
                except struct.error as e:
                    # send error message to the client
                    conn.send("error: Invalid message format".encode())
                    continue
                print('MSG_TYPE', msg_type)
                msg_data = conn.recv(4096).decode()

                if msg_type == 1:  # Register
                    response = handle_register(msg_data)
                    
                elif msg_type == 2:  # Login
                    response = handle_login(msg_data)
                
                elif msg_type == 3:  # List Users
                    response = handle_list_users()
                
                elif msg_type == 4:  # Send Message
                    response = handle_send(msg_data)
                
                elif msg_type == 5:  # Subscribe
                    handle_subscribe(conn, addr, msg_data)
                    break # Exit from handling subscription
                
                elif msg_type == 6:  # Mark Read
                    response = handle_mark_read(msg_data)
                
                elif msg_type == 7:  # Delete Unread Message
                    response = handle_delete_unread_message(msg_data)

                elif msg_type == 8:  # Receive Messages
                    response = handle_receive_messages(msg_data)
                    
                elif msg_type == 9: # Delete account
                    response = handle_delete_account(msg_data)

                elif msg_type == 10: # Logout
                    response = handle_logout(msg_data)

                else:
                    response = "Unknown request type"
                
                if msg_type != 5: # not subscribe
                    try:
                        conn.send(response.encode())
                    except Exception as e:
                        print(f"[ERROR] Error sending data to {addr}: {e}")
            except Exception as e:
                print(f"[ERROR] {e} during client {addr} communication.")
                break

    except Exception as e:
        print(f"[ERROR] {e} during initial connection handling")
    conn.close()
    print(f"[DISCONNECTED] {addr} disconnected.")

def start_server():
    """
      Start server
      Params:
        None
      Returns:
        None
    """

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
