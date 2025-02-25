import grpc
from concurrent import futures
import threading
import uuid
import atexit
import sys
import chat_pb2
import chat_pb2_grpc

# Get HOST and SERVER_PORT from CLI if running in a terminal; otherwise use defaults.
if sys.stdin.isatty():
    while True:
        HOST = input("Enter server host: ").strip()
        if HOST:
            break
    while True:
        try:
            SERVER_PORT = int(input("Enter server port: ").strip())
            break
        except ValueError:
            print("Invalid port. Please enter a valid integer.")
else:
    HOST = "0.0.0.0"
    SERVER_PORT = 5001

# Global storage for users, active sessions, and subscribers.
users = {}  # {username: {"password": ..., "messages": [...], "deleted": bool}}
active_users = set()
active_users_lock = threading.Lock()
subscribers = {}  # {username: {"cond": threading.Condition(), "queue": []}}
subscribers_lock = threading.Lock()

SERVER_VERSION = "1.0.0"

def handle_exit():
    print("[INFO] Shutting down server gracefully...")
    users.clear()
    with subscribers_lock:
        subscribers.clear()
    print("[INFO] Cleanup complete.")

atexit.register(handle_exit)

class ChatService(chat_pb2_grpc.ChatServiceServicer):
    def CheckVersion(self, request, context):
        """
            Checks that version number matches between client and server
        """
        print(f"Client version: {request.version}")
        if request.version != SERVER_VERSION:
            print("[DISCONNECTED] due to version mismatch")
            return chat_pb2.VersionResponse(
                success=False,
                message=f"Version mismatch. Server: {SERVER_VERSION}, Client: {request.version}"
            )
        return chat_pb2.VersionResponse(success=True, message="success: Version matched")
    
    def Register(self, request, context):
        """
            Handle registration request
        """
        username, password = request.username, request.password
        if username in users:
            return chat_pb2.RegisterResponse(message="error: This username is unavailable")
        users[username] = {"password": password, "messages": []}
        return chat_pb2.RegisterResponse(message="success: Account created")

    def Login(self, request, context):
        """
            Handle login request
        """
        username, password = request.username, request.password
        if username in users and users[username]["password"] == password and not users[username].get("deleted", False):
            with active_users_lock:
                if username in active_users:
                    return chat_pb2.LoginResponse(message="error: User already logged in", unread_messages=0)
                active_users.add(username)
            unread = sum(1 for m in users[username]["messages"] if m["status"] == "unread")
            return chat_pb2.LoginResponse(message=f"success: Logged in. Unread messages: {unread}", unread_messages=unread)
        return chat_pb2.LoginResponse(message="error: Invalid username or password", unread_messages=0)

    def ListUsers(self, request, context):
        """
            Returns a list of active users
        """
        user_list = [u for u, data in users.items() if not data.get("deleted", False)]
        return chat_pb2.ListUsersResponse(users=user_list)

    def SendMessage(self, request, context):
        """
            Handle sending a message
        """
        sender, recipient, message_text = request.sender, request.recipient, request.message
        if recipient not in users or users[recipient].get("deleted", False):
            return chat_pb2.SendMessageResponse(status="error: Recipient not found or deleted", message_id="")
        msg = {
            "id": str(uuid.uuid4()),
            "from": sender,
            "message": message_text,
            "status": "unread"
        }
        users[recipient]["messages"].append(msg)
        with subscribers_lock:
            if recipient in subscribers:
                sub = subscribers[recipient]
                with sub["cond"]:
                    sub["queue"].append(msg)
                    sub["cond"].notify()
        return chat_pb2.SendMessageResponse(status="success", message_id=msg["id"])

    def Subscribe(self, request, context):
        """
            Handles subscription request
        """
        username = request.username
        if username not in users:
            context.set_details("User not found")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return
        with subscribers_lock:
            if username not in subscribers:
                subscribers[username] = {"cond": threading.Condition(), "queue": []}
            sub = subscribers[username]
        while True:
            with sub["cond"]:
                while not sub["queue"]:
                    sub["cond"].wait()
                msg = sub["queue"].pop(0)
            yield chat_pb2.Message(
                id=msg["id"],
                sender=msg["from"],
                message=msg["message"],
                status=msg["status"]
            )

    def MarkRead(self, request, context):
        """
            Handle a mark read request
        """
        username, contact, batch_num = request.username, request.contact, request.batch_num
        if username not in users:
            context.set_details("User not found")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return chat_pb2.MarkReadResponse(message="")
        count = 0
        for msg in users[username]["messages"]:
            if msg["from"] == contact and msg["status"] == "unread" and (batch_num == 0 or count < batch_num):
                msg["status"] = "read"
                count += 1
                if batch_num != 0 and count == batch_num:
                    break
        return chat_pb2.MarkReadResponse(message=f"Marked {count} messages as read.")

    def DeleteUnreadMessage(self, request, context):
        """
            Handle delete unread message request
        """
        sender, recipient, message_id = request.sender, request.recipient, request.message_id
        if recipient not in users:
            return chat_pb2.DeleteUnreadMessageResponse(status="error", message="Recipient not found")
        found = False
        for msg in users[recipient]["messages"]:
            if msg["id"] == message_id and msg["from"] == sender and msg["status"] == "unread":
                msg["status"] = "deleted"
                found = True
                with subscribers_lock:
                    if recipient in subscribers:
                        sub = subscribers[recipient]
                        with sub["cond"]:
                            sub["queue"].append({
                                "id": msg["id"],
                                "from": msg["from"],
                                "message": "",
                                "status": "deleted"
                            })
                            sub["cond"].notify()
                break
        if not found:
            return chat_pb2.DeleteUnreadMessageResponse(status="error", message="Message not found or already read")
        return chat_pb2.DeleteUnreadMessageResponse(status="success", message="Message deleted.")

    def ReceiveMessages(self, request, context):
        """
            Handle receive message request
        """
        username = request.username
        if username not in users:
            return chat_pb2.ReceiveMessagesResponse(status="error: User not found", messages=[])
        msgs = []
        for m in users[username]["messages"]:
            msgs.append(chat_pb2.Message(
                id=m["id"],
                sender=m["from"],
                message=m["message"],
                status=m["status"]
            ))
        return chat_pb2.ReceiveMessagesResponse(status="success", messages=msgs)

    def DeleteAccount(self, request, context):
        """
            Handle delete account request
        """
        username = request.username
        if username in users and not users[username].get("deleted", False):
            users[username]["deleted"] = True
            with subscribers_lock:
                if username in subscribers:
                    del subscribers[username]
            return chat_pb2.DeleteAccountResponse(message=f"success: Your account '{username}' was deleted.")
        return chat_pb2.DeleteAccountResponse(message="error: User not found or already deleted")

    def Logout(self, request, context):
        username = request.username
        with active_users_lock:
            if username in active_users:
                active_users.remove(username)
                return chat_pb2.LogoutResponse(message="success: Logged out.")
            return chat_pb2.LogoutResponse(message="error: Failed to log out. User not active.")

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    chat_pb2_grpc.add_ChatServiceServicer_to_server(ChatService(), server)
    server.add_insecure_port(f"{HOST}:{SERVER_PORT}")
    server.start()
    print(f"[SERVER STARTED] Listening on {HOST}:{SERVER_PORT}...")
    server.wait_for_termination()

if __name__ == '__main__':
    serve()