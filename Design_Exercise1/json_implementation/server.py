import socket
import json
import threading
import uuid
import atexit
import sys

SERVER_VERSION = "1.0.0"
class UserStore:
    def __init__(self, filename="users.json"):
        """
            Initialize the UserStore.

        Params:
        
            filename: The file to store the user data in. Defaults to users.json.

        Returns: 

            None
        """
        self.filename = filename
        self.users = {}
        self.save()

    def save(self):
        """
            Save the user data to a file.

        Params:

            None

        Returns:

            None
        """
        with open(self.filename, "w") as f:
            json.dump(self.users, f, indent=4)

    def clear(self):
        """
            Clear the user store of all users and messages.

        Params:

            None

        Returns:

            None  
        """
        self.users = {}
        self.save()

class ChatServer:

    def __init__(self, host=None, port=None, store=None):
        """
            Initialize the ChatServer.

        Params:

            host: The host to bind the server to. Defaults to 0.0.0.0.
            port: The port to bind the server to. Defaults to 5001.
            store: The UserStore to use. If not provided, a new UserStore will be created.

        Returns:

            None
        """
        self.host = host
        self.port = port
        self.store = store if store else UserStore()
        self.active_users = set()
        self.active_users_lock = threading.Lock()
        self.subscribers = {}
        self.subscribers_lock = threading.Lock()
        atexit.register(self.store.clear)
        self.handlers = {
            "register": self.handle_register,
            "login": self.handle_login,
            "logout": self.handle_logout,
            "list_users": self.handle_list_users,
            "subscribe": self.handle_subscribe,
            "send": self.handle_send,
            "mark_read": self.handle_mark_read,
            "delete_account": self.handle_delete_account,
            "delete": self.handle_delete,
            "receive": self.handle_receive,
        }


    def process_request(self, request, conn):
        """
            Process the given request and return a response.

        Params:

            request: The request to process, a JSON-decoded dict.
            conn: The connection to send the response on.
        
        Returns:

            A tuple containing the response and a boolean indicating whether the client should stop.
        """
        req_type = request.get("type")
        handler = self.handlers.get(req_type, self.handle_unknown)
        return handler(request, conn)

    def handle_register(self, request, conn):
        """
            Handle a registration request.

        Params:

            request: The request to process, a JSON-decoded dict.
            conn: The connection to send the response on.
        
        Returns: 
        
            A tuple containing the response and a boolean indicating whether the client should stop.
        """
        username = request["username"]
        password = request["password"]
        if username in self.store.users:
            return {"status": "error", "message": "Username already exists."}, False
        self.store.users[username] = {
            "password": password,
            "messages": []
        }
        self.store.save()
        return {"status": "success", "message": "Account created."}, False

    def handle_login(self, request, conn):
        """
            Handle a login request.

        Params:

            request: The request to process, a JSON-decoded dict.
            conn: The connection to send the response on.
        
        Returns: 

            A tuple containing the response and a boolean indicating whether the client should stop.
        """
        username = request["username"]
        password = request["password"]
        user = self.store.users.get(username)
        if user and user["password"] == password and not user.get("deleted", False):
            with self.active_users_lock:
                if username in self.active_users:
                    return {"status": "error", "message": "User already logged in."}, False
                self.active_users.add(username)
            unread = sum(1 for m in user["messages"] if m["status"] == "unread")
            return {"status": "success", "message": f"Logged in. {unread} unread messages."}, False
        return {"status": "error", "message": "Invalid credentials or account deleted."}, False
    
    def handle_logout(self, request, conn):
        """
            Handle a logout request.

        Params:

            request: The request to process, a JSON-decoded dict.
            conn: The connection to send the response on.
        
        Returns: 

            A tuple containing the response and a boolean indicating whether the client should stop.
        """
        username = request["username"]
        with self.active_users_lock:
            self.active_users.discard(username)
        return {"status": "success", "message": "Logged out."}, False

    def handle_list_users(self, request, conn):
        """
            Handle a list users request.

        Params:

            request: The request to process, a JSON-decoded dict.
            conn: The connection to send the response on.
        
        Returns: 
            A tuple containing the response and a boolean indicating whether the client should stop.
        """
        
        prefix = request.get("prefix", "")
        users = self.store.users
        if prefix == "*":
            matched = [u for u, data in users.items() if not data.get("deleted", False)]
        else:
            matched = [u for u, data in users.items() if u.startswith(prefix) and not data.get("deleted", False)]
        return {"status": "success", "users": matched}, False

    def handle_subscribe(self, request, conn):
        """
            Handle a subscribe request.

        Params:
            
            request: The request to process, a JSON-decoded dict.
            conn: The connection to send the response on.
        
        Returns: 
            
            A tuple containing the response and a boolean indicating whether the client should stop.
        """
        username = request["username"]
        if username not in self.store.users:
            return {"status": "error", "message": "User not found."}, True
        with self.subscribers_lock:
            self.subscribers[username] = {
                "conn": conn,
                "cond": threading.Condition(),
                "queue": []
            }
        self.handle_subscription(username)
        return None, True

    def handle_subscription(self, username):
        """
            Handle the subscription for a given user.

        Params:
            
            username: The username to handle the subscription for.

        Returns:

            None
        """
        sub = self.subscribers[username]
        conn = sub["conn"]
        while True:
            with sub["cond"]:
                while not sub["queue"]:
                    sub["cond"].wait()
                msg = sub["queue"].pop(0)
            try:
                conn.send(json.dumps({"type": "message", "data": msg}).encode())
            except Exception:
                break
        with self.subscribers_lock:
            self.subscribers.pop(username, None)

    def handle_send(self, request, conn):
        """
            Handle a send request.

        Params:
            
            request: The request to process, a JSON-decoded dict.
            conn: The connection to send the response on.
        Returns:
            
            A tuple containing the response and a boolean indicating whether the client should stop.
        """
        sender = request["sender"]
        recipient = request["recipient"]
        message = request["message"]
        users = self.store.users
        if recipient not in users:
            return {"status": "error", "message": "Recipient not found."}, False
        if users[recipient].get("deleted", False):
            return {"status": "error", "message": "User no longer exists."}, False
        msg = {
            "id": str(uuid.uuid4()),
            "from": sender,
            "message": message,
            "status": "unread"
        }
        users[recipient]["messages"].append(msg)
        self.store.save()
        with self.subscribers_lock:
            if recipient in self.subscribers:
                sub = self.subscribers[recipient]
                with sub["cond"]:
                    sub["queue"].append(msg)
                    sub["cond"].notify()
        return {"status": "success", "message": f"Message sent to {recipient}.", "message_id": msg["id"]}, False

    def handle_mark_read(self, request, conn):
        """
            Handle a mark read request.

        Params:
        
            request: The request to process, a JSON-decoded dict.
            conn: The connection to send the response on.
        
        Returns: 
            
            A tuple containing the response and a boolean indicating whether the client should stop.
        """
        DEFAULT_READ_BATCH_NUM = 5
        username = request["username"]
        contact = request["contact"]
        read_batch_num = request.get("read_batch_num", DEFAULT_READ_BATCH_NUM)

        if username not in self.store.users:
            return {"status": "error", "message": "User not found."}, False

        # Get all unread messages from this contact
        unread_messages = [
            msg for msg in self.store.users[username]["messages"]
            if msg["from"] == contact and msg["status"] == "unread"
        ]

        if not unread_messages:
            return {"status": "error", "message": "No unread messages."}, False

        # If read_batch_num is 0, mark all unread messages; otherwise mark only the specified batch.
        if read_batch_num == 0:
            batch = unread_messages
        else:
            batch = unread_messages[:read_batch_num]

        for msg in batch:
            msg["status"] = "read"

        self.store.save()
        return {"status": "success", "message": f"{len(batch)} messages marked as read."}, False

    def handle_delete_account(self, request, conn):
        """
            Handle a delete account request.

        Params
            
            request: The request to process, a JSON-decoded dict.
            conn: The connection to send the response on.
        
        Returns:
            
            A tuple containing the response and a boolean indicating whether the client should stop.
        """
        username = request["username"]
        user = self.store.users.get(username)
        if user and not user.get("deleted", False):
            user["deleted"] = True
            self.store.save()
            with self.subscribers_lock:
                self.subscribers.pop(username, None)
            return {"status": "success", "message": "Account deleted."}, False
        return {"status": "error", "message": "User not found or already deleted."}, False

    def handle_delete(self, request, conn):
        """
            Handle a delete message request.

        Params:
        
            request: The request to process, a JSON-decoded dict.
            conn: The connection to send the response on.

        Returns: 
            A tuple containing the response and a boolean indicating whether the client should stop.
        """
        sender = request["sender"]
        recipient = request["recipient"]
        msg_id = request["message_id"]
        users = self.store.users
        if recipient not in users:
            return {"status": "error", "message": "Recipient not found."}, False
        for i, msg in enumerate(users[recipient]["messages"]):
            if msg["id"] == msg_id and msg["from"] == sender and msg["status"] == "unread":
                users[recipient]["messages"][i]["status"] = "deleted"
                self.store.save()
                with self.subscribers_lock:
                    if recipient in self.subscribers:
                        sub = self.subscribers[recipient]
                        with sub["cond"]:
                            sub["queue"].append({"id": msg_id, "from": sender, "message": "", "status": "deleted"})
                            sub["cond"].notify()
                return {"status": "success", "message": "Message deleted."}, False
        return {"status": "error", "message": "Message not found or already read."}, False

    def handle_receive(self, request, conn):
        """
            Handle a receive request.

        Params:
        
            request: The request to process, a JSON-decoded dict.
            conn: The connection to send the response on.
        Returns: 
        
            A tuple containing the response and a boolean indicating whether the client should stop.
        """
        username = request["username"]
        if username in self.store.users:
            return {"status": "success", "messages": self.store.users[username]["messages"]}, False
        return {"status": "error", "message": "User not found."}, False

    def handle_unknown(self, request, conn):
        """
            Handle an unknown request type.

        Params:
            
            request: The request to process, a JSON-decoded dict.
            conn: The connection to send the response on.
            
        Returns: 
            
            A tuple containing the response and a boolean indicating whether the client should stop.
        """
        return {"status": "error", "message": "Unknown request type."}, False

    def client_thread(self, conn, addr):
        """
            Handle a new client connection.

        Params:
            
            conn: The connection to the client.
            addr: The address of the client.
        
        Returns: 
        
            None
        """
        print(f"[NEW CONNECTION] {addr} connected.")
        # Version check block
        try:
            client_version_data = conn.recv(32)
            if not client_version_data:
                conn.close()
                print(f"[DISCONNECTED] {addr} (no version info)")
                return
            client_version = client_version_data.decode("utf-8").strip()
            print(f"Client version: {client_version}")
            if client_version != SERVER_VERSION:
                error_msg = f"error: Version mismatch. Server: {SERVER_VERSION}, Client: {client_version}"
                conn.send(error_msg.encode())
                conn.close()
                print(f"[DISCONNECTED] {addr} due to version mismatch")
                return
            conn.send("success: Version matched".encode())
        except Exception as e:
            print(f"[ERROR] Version check failed for {addr}: {e}")
            conn.close()
            return

        # Normal processing loop
        while True:
            try:
                data = conn.recv(4096).decode()
                if not data:
                    break
                request = json.loads(data)
                result, stop = self.process_request(request, conn)
                if stop:
                    if result:
                        conn.send(json.dumps(result).encode())
                    break
                conn.send(json.dumps(result).encode())
            except (json.JSONDecodeError, KeyError):
                try:
                    conn.send(json.dumps({"status": "error", "message": "Invalid request format"}).encode())
                except Exception:
                    break
        conn.close()
        print(f"[DISCONNECTED] {addr} disconnected.")
    def start(self):
        """
            Start the server and listen for incoming connections.

       Params:

            None

        Returns:

            None
        """
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((self.host, self.port))
        server.listen(5)
        print(f"[SERVER STARTED] Listening on port {self.port}...")
        while True:
            conn, addr = server.accept()
            threading.Thread(target=self.client_thread, args=(conn, addr)).start()
            print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}")

def get_server_config():
    """
        Get the server host and port from the user. Otherwise, use
    the default host and port (0.0.0.0:5001).

    Parmas:

        None

    Return:
    
        A tuple containing the server host and port or default host and port.
    """
    if sys.stdin.isatty():
        while True:
            HOST = input("Enter server host: ").strip()
            if HOST:
                break
        while True:
            try:
                PORT = int(input("Enter server port: ").strip())
                break
            except ValueError:
                print("Invalid input. Please enter a valid port number.")
    else:
        HOST = "0.0.0.0"
        PORT = 5001
    return HOST, PORT


if __name__ == "__main__":
    HOST, PORT = get_server_config()
    chat_server = ChatServer(host=HOST, port=PORT)
    chat_server.start()