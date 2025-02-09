import socket
import json
import threading
import hashlib
import uuid
import atexit

class UserStore:
    def __init__(self, filename="users.json"):
        """
        Initialize the UserStore.

        :param filename: The file to store the user data in. Defaults to users.json.
        """
        self.filename = filename
        self.users = {}
        self.save()

    def save(self):
        """
        Save the user data to a file.

        The data is written to the file specified by the filename argument to
        the UserStore constructor, or to users.json if no filename was specified.
        """
        with open(self.filename, "w") as f:
            json.dump(self.users, f, indent=4)

    def clear(self):
        """
        Clear the user store of all users and messages.

        This method will also save the cleared user store to disk.
        """
        self.users = {}
        self.save()

class ChatServer:
    def __init__(self, host="0.0.0.0", port=5001, store=None):
        """
        Initialize the ChatServer.

        :param host: The host to bind the server to. Defaults to 0.0.0.0.
        :param port: The port to bind the server to. Defaults to 5001.
        :param store: The UserStore to use. If not provided, a new UserStore will be created.
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

    def hash_password(self, password):
        """
        Hash the given password.

        :param password: The password to hash.
        :return: A SHA-256 hash of the password.
        """
        return hashlib.sha256(password.encode()).hexdigest()

    def process_request(self, request, conn):
        """
        Process the given request and return a response.

        :param request: The request to process, a JSON-decoded dict.
        :param conn: The connection to send the response on.
        :return: A tuple containing the response and a boolean indicating whether the client should stop.
        """
        req_type = request.get("type")
        handler = self.handlers.get(req_type, self.handle_unknown)
        return handler(request, conn)

    def handle_register(self, request, conn):
        """
        Handle a registration request.

        :param request: The request to process, a JSON-decoded dict.
        :param conn: The connection to send the response on.
        :return: A tuple containing the response and a boolean indicating whether the client should stop.
        """
        username = request["username"]
        password = request["password"]
        if username in self.store.users:
            return {"status": "error", "message": "Username already exists."}, False
        self.store.users[username] = {
            "password": self.hash_password(password),
            "messages": []
        }
        self.store.save()
        return {"status": "success", "message": "Account created."}, False

    def handle_login(self, request, conn):
        """
        Handle a login request.

        :param request: The request to process, a JSON-decoded dict.
        :param conn: The connection to send the response on.
        :return: A tuple containing the response and a boolean indicating whether the client should stop.
        """
        username = request["username"]
        password = self.hash_password(request["password"])
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
        username = request["username"]
        with self.active_users_lock:
            self.active_users.discard(username)
        return {"status": "success", "message": "Logged out."}, False

    def handle_list_users(self, request, conn):
        """
        Handle a list users request.

        :param request: The request to process, a JSON-decoded dict.
        :param conn: The connection to send the response on.
        :return: A tuple containing the response and a boolean indicating whether the client should stop.
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

        :param request: The request to process, a JSON-decoded dict.
        :param conn: The connection to send the response on.
        :return: A tuple containing the response and a boolean indicating whether the client should stop.
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

        This method is run in a separate thread and will run indefinitely until
        the user is unsubscribed. It will send all messages from the user's queue
        to the user's connection as they are added to the queue.

        :param username: The username to handle the subscription for.
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

        :param request: The request to process, a JSON-decoded dict.
        :param conn: The connection to send the response on.
        :return: A tuple containing the response and a boolean indicating whether the client should stop.
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

        :param request: The request to process, a JSON-decoded dict.
        :param conn: The connection to send the response on.
        :return: A tuple containing the response and a boolean indicating whether the client should stop.
        """
        
        username = request["username"]
        contact = request["contact"]
        if username not in self.store.users:
            return {"status": "error", "message": "User not found."}, False
        count = 0
        for msg in self.store.users[username]["messages"]:
            if msg["from"] == contact and msg["status"] == "unread":
                msg["status"] = "read"
                count += 1
        self.store.save()
        return {"status": "success", "message": f"Marked {count} messages as read."}, False

    def handle_delete_account(self, request, conn):
        """
        Handle a delete account request.

        :param request: The request to process, a JSON-decoded dict.
        :param conn: The connection to send the response on.
        :return: A tuple containing the response and a boolean indicating whether the client should stop.
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

        :param request: The request to process, a JSON-decoded dict.
        :param conn: The connection to send the response on.
        :return: A tuple containing the response and a boolean indicating whether the client should stop.
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

        :param request: The request to process, a JSON-decoded dict.
        :param conn: The connection to send the response on.
        :return: A tuple containing the response and a boolean indicating whether the client should stop.
        """
        username = request["username"]
        if username in self.store.users:
            return {"status": "success", "messages": self.store.users[username]["messages"]}, False
        return {"status": "error", "message": "User not found."}, False

    def handle_unknown(self, request, conn):
        """
        Handle an unknown request type.

        :param request: The request to process, a JSON-decoded dict.
        :param conn: The connection to send the response on.
        :return: A tuple containing the response and a boolean indicating whether the client should stop.
        """
        return {"status": "error", "message": "Unknown request type."}, False

    def client_thread(self, conn, addr):
        """
        Handle a new client connection.

        :param conn: The connection to the client.
        :param addr: The address of the client.
        :return: None
        """
        print(f"[NEW CONNECTION] {addr} connected.")
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

        This method will block until the server is stopped. It will start a new
        thread for each incoming connection, which will be handled by the
        client_thread method.

        :return: None
        """
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((self.host, self.port))
        server.listen(5)
        print(f"[SERVER STARTED] Listening on port {self.port}...")
        while True:
            conn, addr = server.accept()
            threading.Thread(target=self.client_thread, args=(conn, addr)).start()
            print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}")

if __name__ == "__main__":
    chat_server = ChatServer()
    chat_server.start()
