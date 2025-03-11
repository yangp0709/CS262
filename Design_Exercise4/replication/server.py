import grpc
from concurrent import futures
import threading, time, uuid, json, os, sys
import chat_pb2
import chat_pb2_grpc
import multiprocessing

HEARTBEAT_INTERVAL = 2  # seconds
SERVER_VERSION = "1.0.0"

# -------------------------
# PersistentStore: writes to a JSON file unique per server.
# -------------------------
class PersistentStore:
    def __init__(self, filename):
        self.filename = filename
        self.lock = threading.Lock()
        if os.path.exists(self.filename):
            with open(self.filename, 'r') as f:
                self.users = json.load(f)
        else:
            self.users = {}  # Structure: {username: {password: pwd, messages: [msg, ...]}
    
    def add_message(self, recipient, msg):
        with self.lock:
            # if recipient not in self.users:
            #     self.users[recipient]["messages"] = []
            self.users[recipient]["messages"].append(msg)
            self.save()
    
    def save(self):
        with self.lock:
            with open(self.filename, 'w') as f:
                json.dump(self.users, f, indent=2)
    
    # def get_all_messages(self):
    #     with self.lock:
    #         return self.users

# -------------------------
# Health Service: for simple pinging.
# -------------------------
class HealthService(chat_pb2_grpc.HealthServicer):
    def Ping(self, request, context):
        return chat_pb2.PingResponse(alive=True)

# -------------------------
# LeaderElection: fixed ordering by server_id.
# -------------------------
class LeaderElection:
    def __init__(self, server_id, peers):
        self.server_id = server_id  # e.g., 1,2,3
        self.peers = peers          # List of (peer_id, address)
        self.state = "backup"
        self.leader_id = None
        self.lock = threading.Lock()

    def ping_peer(self, address):
        try:
            channel = grpc.insecure_channel(address)
            stub = chat_pb2_grpc.HealthStub(channel)
            resp = stub.Ping(chat_pb2.PingRequest(), timeout=1)
            return resp.alive
        except Exception:
            return False

    def elect(self):
        with self.lock:
            lower_alive = any(self.ping_peer(addr) for pid, addr in self.peers if pid < self.server_id)
            if not lower_alive:
                self.state = "leader"
                self.leader_id = self.server_id
            else:
                self.state = "backup"
                candidate = self.server_id
                for pid, addr in self.peers:
                    if self.ping_peer(addr):
                        candidate = min(candidate, pid)
                self.leader_id = candidate
            print(f"Server {self.server_id}: state={self.state}, leader={self.leader_id}")

    def start(self):
        while True:
            self.elect()
            time.sleep(HEARTBEAT_INTERVAL)

# -------------------------
# ChatService: Only leader handles SendMessage. If not leader, returns error.
# -------------------------
class ChatService(chat_pb2_grpc.ChatServiceServicer):
    def __init__(self, store, election, peers):
        self.store = store
        self.election = election
        self.peers = peers  # List of (peer_id, address)
        # Track peer health: once marked down, remains down forever.
        self.peer_status = {pid: True for pid, _ in peers}
        self.active_users_lock = threading.Lock()
        self.active_users = set()
        self.subscribers_lock = threading.Lock()
        self.subscribers = {}


    def CheckVersion(self, request, context):
        if request.version != SERVER_VERSION:
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
        if username in self.store.users:
            return chat_pb2.RegisterResponse(message="error: This username is unavailable")
        self.store.users[username] = {
            "password": password,
            "messages": []
        }
        self.store.save()
        return chat_pb2.RegisterResponse(message="success: Account created")
    
    def Login(self, request, context):
        """
            Handle login request
        """
        username, password = request.username, request.password
        user = self.store.users.get(username)
        if user and user["password"] == password and not user.get("deleted", False):
            with self.active_users_lock:
                if username in self.active_users:
                    return chat_pb2.LoginResponse(message="error: User already logged in", unread_messages=0)
                self.active_users.add(username)
            unread = sum(1 for m in user["messages"] if m["status"] == "unread")
            return chat_pb2.LoginResponse(message=f"success: Logged in. Unread messages: {unread}", unread_messages=unread)
        return chat_pb2.LoginResponse(message="error: Invalid username or password", unread_messages=0)
    
    def ListUsers(self, request, context):
        """
            Returns a list of active users
        """
        users = self.store.users
        user_list = [u for u, data in users.items() if not data.get("deleted", False)]
        return chat_pb2.ListUsersResponse(users=user_list)
    
    def SendMessage(self, request, context):
        # If not leader, cannot send
        if self.election.state != "leader":
            return chat_pb2.SendMessageResponse(status="error: Not leader", message_id="")
        
        sender, recipient, message_text = request.sender, request.recipient, request.message
        recipient_info = self.store.users.get(recipient)
        if recipient_info or recipient_info.get("deleted", False):
            return chat_pb2.SendMessageResponse(status="error: Recipient not found or deleted", message_id="")

        # Create message with a unique ID.
        msg = {
            "id": str(uuid.uuid4()),
            "from": sender,
            "message": message_text,
            "status": "unread"
        }
        self.store.add_message(recipient, msg)
        ack_count = 1  # Leader's own write counts.

        for pid, addr in self.peers:
            if not self.peer_status.get(pid, True):
                continue  # Skip replicas already marked as down.
            try:
                channel = grpc.insecure_channel(addr)
                stub = chat_pb2_grpc.ReplicationServiceStub(channel)
                rep_req = chat_pb2.ReplicateMessageRequest(
                    message_id=msg["id"],
                    sender=sender,
                    recipient=recipient,
                    message=message_text,
                    status="unread"
                )
                response = stub.ReplicateMessage(rep_req, timeout=2)
                if response.success:
                    ack_count += 1
                    self.peer_status[pid] = True
            except Exception as e:
                print(f"Replication error to {addr}: {e}")
                # Mark the replica as permanently down.
                self.peer_status[pid] = False

        # With 3 servers, a majority is 2 (leader + one backup).
        if ack_count >= 2:
            return chat_pb2.SendMessageResponse(status="success", message_id=msg["id"])
        else:
            return chat_pb2.SendMessageResponse(status="error: Replication failed", message_id="")
    
    def Subscribe(self, request, context):
        """
            Handles subscription request
        """
        username = request.username
        if not self.store.users.get(username):
            context.set_details("User not found")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return
        
        with self.subscribers_lock:
            if username not in self.subscribers:
                self.subscribers[username] = {"cond": threading.Condition(), "queue": []}
            sub = self.subscribers[username]
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
        users = self.store.users.get(username)
        if not users:
            context.set_details("User not found")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return chat_pb2.MarkReadResponse(message="")
        count = 0
        for msg in users["messages"]:
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
        recipient_info = self.store.users.get(recipient)
        if not recipient_info:
            return chat_pb2.DeleteUnreadMessageResponse(status="error", message="Recipient not found")
        found = False
        for msg in recipient_info["messages"]:
            if msg["id"] == message_id and msg["from"] == sender and msg["status"] == "unread":
                msg["status"] = "deleted"
                found = True
                with self.subscribers_lock:
                    if recipient in self.subscribers:
                        sub = self.subscribers[recipient]
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
        users = self.store.users.get(username)
        if not users:
            return chat_pb2.ReceiveMessagesResponse(status="error: User not found", messages=[])
        msgs = []
        for m in users["messages"]:
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
        users = self.store.users.get(username)
        if users and not users.get("deleted", False):
            users["deleted"] = True
            with self.subscribers_lock:
                if username in self.subscribers:
                    del self.subscribers[username]
            return chat_pb2.DeleteAccountResponse(message=f"success: Your account '{username}' was deleted.")
        return chat_pb2.DeleteAccountResponse(message="error: User not found or already deleted")

    def Logout(self, request, context):
        username = request.username
        with self.active_users_lock:
            if username in self.active_users:
                self.active_users.remove(username)
                return chat_pb2.LogoutResponse(message="success: Logged out.")
            return chat_pb2.LogoutResponse(message="error: Failed to log out. User not active.")
    
# -------------------------
# ReplicationService: Followers use this to replicate messages.
# -------------------------
class ReplicationService(chat_pb2_grpc.ReplicationServiceServicer):
    def __init__(self, store):
        self.store = store

    def ReplicateMessage(self, request, context):
        msg = {
            "id": request.message_id,
            "from": request.sender,
            "message": request.message,
            "status": request.status
        }
        # Create recipient entry if needed.
        # if request.recipient not in self.store.users:
        #     self.store.users[request.recipient] = {}
        self.store.add_message(request.recipient, msg)
        return chat_pb2.ReplicateMessageResponse(success=True)

# -------------------------
# Main server function. Automatically spawn each server with its own JSON file.
# -------------------------
def serve(server_id, host, port, peers):
    store = PersistentStore(f"users_{server_id}.json")
    election = LeaderElection(server_id, peers)
    threading.Thread(target=election.start, daemon=True).start()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    chat_pb2_grpc.add_ChatServiceServicer_to_server(ChatService(store, election, peers), server)
    chat_pb2_grpc.add_ReplicationServiceServicer_to_server(ReplicationService(store), server)
    chat_pb2_grpc.add_HealthServicer_to_server(HealthService(), server)
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    print(f"Server {server_id} started on {host}:{port}")
    server.wait_for_termination()

# -------------------------
# Launcher: automatically spawn all servers using a ports dictionary.
# -------------------------
def launch_servers():
    ports = {1: 8001, 2: 8002, 3: 8003}
    host = "localhost"
    processes = []
    for server_id, port in ports.items():
        # Build peers list: all other servers.
        peers = [(pid, f"{host}:{p}") for pid, p in ports.items() if pid != server_id]
        p = multiprocessing.Process(target=serve, args=(server_id, host, port, peers))
        p.start()
        processes.append(p)
    for p in processes:
        p.join()

if __name__ == "__main__":
    launch_servers()
