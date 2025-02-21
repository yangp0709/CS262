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

def handle_exit():
    print("[INFO] Shutting down server gracefully...")
    users.clear()
    with subscribers_lock:
        subscribers.clear()
    print("[INFO] Cleanup complete.")

atexit.register(handle_exit)

class ChatService(chat_pb2_grpc.ChatServiceServicer):
    def Register(self, request, context):
        username, password = request.username, request.password
        if username in users:
            return chat_pb2.RegisterResponse(message="error: This username is unavailable")
        users[username] = {"password": password, "messages": []}
        return chat_pb2.RegisterResponse(message="success: Account created")

    def Login(self, request, context):
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
        user_list = [u for u, data in users.items() if not data.get("deleted", False)]
        return chat_pb2.ListUsersResponse(users=user_list)

    def SendMessage(self, request, context):
        sender, recipient, message_text = request.sender, request.recipient, request.message
        if recipient not in users or users[recipient].get("deleted", False):
            context.set_details("error: Recipient not found or deleted")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return chat_pb2.SendMessageResponse(message_id="")
        msg = {
            "id": str(uuid.uuid4()),
            "from": sender,
            "recipient": recipient,
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
        return chat_pb2.SendMessageResponse(message_id=msg["id"])

    def Subscribe(self, request, context):
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
                recipient=msg["recipient"],
                message=msg["message"],
                status=msg["status"]
            )

    def MarkRead(self, request, context):
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
        sender, recipient, message_id = request.sender, request.recipient, request.message_id
        if recipient not in users:
            context.set_details("Recipient not found")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return chat_pb2.DeleteUnreadMessageResponse(message="")
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
                                "recipient": recipient,
                                "message": "",
                                "status": "deleted"
                            })
                            sub["cond"].notify()
                break
        if not found:
            context.set_details("Message not found or already read")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return chat_pb2.DeleteUnreadMessageResponse(message="")
        return chat_pb2.DeleteUnreadMessageResponse(message="Message deleted.")

    def ReceiveMessages(self, request, context):
        username = request.username
        if username not in users:
            context.set_details("User not found")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return chat_pb2.ReceiveMessagesResponse(messages=[])
        msgs = []
        for m in users[username]["messages"]:
            msgs.append(chat_pb2.Message(
                id=m["id"],
                sender=m["from"],
                recipient=m.get("recipient", ""),
                message=m["message"],
                status=m["status"]
            ))
        return chat_pb2.ReceiveMessagesResponse(messages=msgs)

    def DeleteAccount(self, request, context):
        username = request.username
        if username in users and not users[username].get("deleted", False):
            users[username]["deleted"] = True
            with subscribers_lock:
                if username in subscribers:
                    del subscribers[username]
            return chat_pb2.DeleteAccountResponse(message=f"Your account '{username}' was deleted.")
        context.set_details("User not found or already deleted")
        context.set_code(grpc.StatusCode.NOT_FOUND)
        return chat_pb2.DeleteAccountResponse(message="")

    def Logout(self, request, context):
        username = request.username
        with active_users_lock:
            if username in active_users:
                active_users.remove(username)
                return chat_pb2.LogoutResponse(message="Logged out.")
            context.set_details("Failed to log out. User not active.")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return chat_pb2.LogoutResponse(message="")

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    chat_pb2_grpc.add_ChatServiceServicer_to_server(ChatService(), server)
    server.add_insecure_port(f"{HOST}:{SERVER_PORT}")
    server.start()
    print(f"[SERVER STARTED] Listening on {HOST}:{SERVER_PORT}...")
    server.wait_for_termination()

if __name__ == '__main__':
    serve()



# import grpc
# from concurrent import futures
# import threading
# import uuid
# import atexit
# import sys
# import chat_pb2
# import chat_pb2_grpc

# # Get HOST and SERVER_PORT from CLI if running in a terminal; otherwise use defaults.
# if sys.stdin.isatty():
#     while True:
#         HOST = input("Enter server host: ").strip()
#         if HOST:
#             break
#     while True:
#         try:
#             SERVER_PORT = int(input("Enter server port: ").strip())
#             break
#         except ValueError:
#             print("Invalid port. Please enter a valid integer.")
# else:
#     HOST = "0.0.0.0"
#     SERVER_PORT = 5001

# # Global storage for users, active sessions, and subscribers.
# users = {}  # {username: {"password": ..., "messages": [...], "deleted": bool}}
# active_users = set()
# active_users_lock = threading.Lock()
# subscribers = {}  # {username: {"cond": threading.Condition(), "queue": []}}
# subscribers_lock = threading.Lock()

# def handle_exit():
#     print("[INFO] Shutting down server gracefully...")
#     users.clear()
#     with subscribers_lock:
#         subscribers.clear()
#     with active_users_lock:
#         active_users.clear()
#     print("[INFO] Cleanup complete.")

# atexit.register(handle_exit)

# class ChatService(chat_pb2_grpc.ChatServiceServicer):
#     def Register(self, request, context):
#         username, password = request.username, request.password
#         if username in users:
#             return chat_pb2.RegisterResponse(message="error: This username is unavailable")
#         users[username] = {"password": password, "messages": []}
#         return chat_pb2.RegisterResponse(message="success: Account created")

#     def Login(self, request, context):
#         username, password = request.username, request.password
#         if username in users and users[username]["password"] == password and not users[username].get("deleted", False):
#             with active_users_lock:
#                 if username in active_users:
#                     return chat_pb2.LoginResponse(message="error: User already logged in", unread_messages=0)
#                 active_users.add(username)
#             unread = sum(1 for m in users[username]["messages"] if m["status"] == "unread")
#             return chat_pb2.LoginResponse(message=f"success: Logged in. Unread messages: {unread}", unread_messages=unread)
#         return chat_pb2.LoginResponse(message="error: Invalid username or password", unread_messages=0)

#     def ListUsers(self, request, context):
#         active_users_list = [u for u, data in users.items() if not data.get("deleted", False)]
#         return chat_pb2.ListUsersResponse(users=active_users_list)

#     def SendMessage(self, request, context):
#         sender, recipient, message_text = request.sender, request.recipient, request.message
#         if recipient not in users or users[recipient].get("deleted", False):
#             context.set_details("error: Recipient not found or deleted")
#             context.set_code(grpc.StatusCode.NOT_FOUND)
#             return chat_pb2.SendMessageResponse(message_id="")
#         msg = {
#             "id": str(uuid.uuid4()),
#             "from": sender,
#             # "recipient": recipient,
#             "message": message_text,
#             "status": "unread"
#         }
#         users[recipient]["messages"].append(msg)
#         with subscribers_lock:
#             if recipient in subscribers:
#                 sub = subscribers[recipient]
#                 with sub["cond"]:
#                     sub["queue"].append(msg)
#                     sub["cond"].notify()
#         return chat_pb2.SendMessageResponse(message_id=f"success:{str(msg['id'])}")

#     def Subscribe(self, request, context):
#         username = request.username
#         if username not in users:
#             context.set_details("User not found")
#             context.set_code(grpc.StatusCode.NOT_FOUND)
#             return

#         # Register the subscriber
#         with subscribers_lock:
#             if username not in subscribers:
#                 subscribers[username] = {"cond": threading.Condition(), "queue": []}
#             sub = subscribers[username]

#         # Wait for messages and send them to the user
#         try:
#             while context.is_active():
#                 with sub["cond"]:
#                     while not sub["queue"]:
#                         sub["cond"].wait()
#                     msg = sub["queue"].pop(0)

#                 yield chat_pb2.Message(
#                     id=msg["id"],
#                     sender=msg["from"],
#                     message=f"success:{str(msg['message'])}",
#                     status=msg["status"]
#                 )
#         except Exception as e:
#             print(f"[ERROR] Error sending data to {username}: {e}")

#         # Clean up the subscriber when the loop exits
#         with subscribers_lock:
#             if username in subscribers:
#                 del subscribers[username]


#     def MarkRead(self, request, context):
#         username, contact, read_batch_num = request.username, request.contact, request.batch_num
#         if username not in users:
#             context.set_details("User not found")
#             context.set_code(grpc.StatusCode.NOT_FOUND)
#             return chat_pb2.MarkReadResponse(message="")
#         count = 0
#         for msg in users[username]["messages"]:
#             if msg["from"] == contact and msg["status"] == "unread" and (read_batch_num == 0 or count < read_batch_num):
#                 msg["status"] = "read"
#                 count += 1
#                 if read_batch_num != 0 and count == read_batch_num:
#                     break
#         return chat_pb2.MarkReadResponse(message=f"Marked {count} messages as read.")

#     def DeleteUnreadMessage(self, request, context):
#         sender, recipient, msg_id = request.sender, request.recipient, request.message_id
#         if recipient not in users:
#             context.set_details("error: Recipient not found")
#             context.set_code(grpc.StatusCode.NOT_FOUND)
#             return chat_pb2.DeleteUnreadMessageResponse(message="")
#         found = False
#         for msg in users[recipient]["messages"]:
#             if msg["id"] == msg_id and msg["from"] == sender and msg["status"] == "unread":
#                 msg["status"] = "deleted"
#                 found = True
#                 with subscribers_lock:
#                     if recipient in subscribers:
#                         sub = subscribers[recipient]
#                         with sub["cond"]:
#                             sub["queue"].append({
#                                 "id": msg_id,
#                                 "from": sender,
#                                 # "recipient": recipient,
#                                 "message": "",
#                                 "status": "deleted"
#                             })
#                             sub["cond"].notify()
#                 break
#         if not found:
#             context.set_details("error: Message not found or already read")
#             context.set_code(grpc.StatusCode.NOT_FOUND)
#             return chat_pb2.DeleteUnreadMessageResponse(message="")
#         return chat_pb2.DeleteUnreadMessageResponse(message="success: Message deleted.")

#     def ReceiveMessages(self, request, context):
#         username = request.username
#         if username not in users:
#             context.set_details("error: User not found")
#             context.set_code(grpc.StatusCode.NOT_FOUND)
#             return chat_pb2.ReceiveMessagesResponse(messages=[])
#         return chat_pb2.ReceiveMessagesResponse(messages=f"success:{str(users[username]['messages'])}")

#         # msgs = []
#         # for m in users[username]["messages"]:
#         #     msgs.append(chat_pb2.Message(
#         #         id=m["id"],
#         #         sender=m["from"],
#         #         # recipient=m.get("recipient", ""),
#         #         message=m["message"],
#         #         status=m["status"]
#         #     ))
#         # return chat_pb2.ReceiveMessagesResponse(messages=msgs)

#     def DeleteAccount(self, request, context):
#         username = request.username
#         if username in users and not users[username].get("deleted", False):
#             users[username]["deleted"] = True
#             with subscribers_lock:
#                 if username in subscribers:
#                     del subscribers[username]
#             return chat_pb2.DeleteAccountResponse(message=f"success: Your account '{username}' was deleted.")
#         context.set_details("error: User not found or already deleted")
#         context.set_code(grpc.StatusCode.NOT_FOUND)
#         return chat_pb2.DeleteAccountResponse(message="")

#     def Logout(self, request, context):
#         username = request.username
#         with active_users_lock:
#             if username in active_users:
#                 active_users.remove(username)
#                 return chat_pb2.LogoutResponse(message="success: Logged out.")
#             context.set_details("error: Failed to log out. User not active.")
#             context.set_code(grpc.StatusCode.NOT_FOUND)
#             return chat_pb2.LogoutResponse(message="")

# def serve():
#     server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
#     chat_pb2_grpc.add_ChatServiceServicer_to_server(ChatService(), server)
#     server.add_insecure_port(f"{HOST}:{SERVER_PORT}")
#     server.start()
#     print(f"[SERVER STARTED] Listening on {HOST}:{SERVER_PORT}...")
#     server.wait_for_termination()

# if __name__ == '__main__':
#     serve()
