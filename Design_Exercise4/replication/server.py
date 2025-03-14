import grpc
from concurrent import futures
import threading, time, uuid, json, os, sys
import chat_pb2
import chat_pb2_grpc
import multiprocessing
import argparse

HEARTBEAT_INTERVAL = 2  # seconds
SERVER_VERSION = "1.0.0"
ports = {1: 8001, 2: 8002, 3: 8003}
all_host_port_pairs = []

# -------------------------
# PersistentStore: writes to a JSON file unique per server.
# -------------------------
class PersistentStore:
    def __init__(self, filename):
        self.filename = filename
        self.lock = threading.RLock()  
        self.users = {}  # {username: {"password": ..., "messages": [...], "subscribed": bool}}
        self.subscribers_set = set()
        self.active_users_set = set()
        if os.path.exists(self.filename):
            with open(self.filename, 'r') as f:
                data = json.load(f)
            self.users = data.get("users", {})
            self.subscribers_set = set(data.get("subscribers", []))
            self.active_users_set = set(data.get("active_users", []))
        else:
            # Initialize empty structures.
            self.users = {}
            self.subscribers_set = set()
            self.active_users_set = set()
    
    def add_message(self, recipient, msg):
        with self.lock:
            if recipient not in self.users:
                return False
            self.users[recipient]["messages"].append(msg)
            self.save()
            return True
    
    def register(self, username, password):
        with self.lock:
            # Initialize subscription flag to False
            self.users[username] = {
                "password": password,
                "messages": [],
                "subscribed": False
            }
            self.save()

    def mark_read(self, username, contact, batch_num):
        with self.lock:
            users = self.users.get(username)
            count = 0
            for msg in users["messages"]:
                if msg["from"] == contact and msg["status"] == "unread" and (batch_num == 0 or count < batch_num):
                    msg["status"] = "read"
                    count += 1
                    if batch_num != 0 and count == batch_num:
                        break
            self.save()
            return count
        
    def delete_message(self, sender, recipient, message_id):
        print('filename', self.filename)
        with self.lock:
            recipient_info = self.users.get(recipient)
            print('RECIPIENT INFO', recipient_info)
            for msg in recipient_info["messages"]:
                if msg["id"] == message_id and msg["from"] == sender and msg["status"] == "unread":
                    msg["status"] = "deleted"
            self.save()
        
    def set_subscription(self, username, subscribed):
        with self.lock:
            if username in self.users:
                self.users[username]["subscribed"] = subscribed
                if subscribed:
                    self.subscribers_set.add(username)
                else:
                    self.subscribers_set.discard(username)
                self.save()

    def add_active_user(self, username):
        with self.lock:
            self.active_users_set.add(username)
            self.save()

    def remove_active_user(self, username):
        with self.lock:
            self.active_users_set.discard(username)
            self.save()

    def get_active_users(self):
        with self.lock:
            return self.active_users_set.copy()

    def get_subscribers(self):
        with self.lock:
            return self.subscribers_set.copy()
    
    def save(self):
        with self.lock:
            data = {
                "users": self.users,
                "subscribers": list(self.subscribers_set),
                "active_users": list(self.active_users_set)
            }
            with open(self.filename, 'w') as f:
                json.dump(data, f, indent=2)
    
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
        self.peer_status = {pid: True for pid, _ in peers}

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
            # Compute peer_status first
            self.peer_status = {pid: self.ping_peer(addr) for pid, addr in self.peers}
            print(self.peer_status)

            # Derive lower_alive from peer_status
            lower_alive = any(self.peer_status[pid] for pid in self.peer_status if pid < self.server_id)

            # lower_alive = any(self.ping_peer(addr) for pid, addr in self.peers if pid < self.server_id)
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
            return all_host_port_pairs[self.leader_id - 1] # return host:port of leader

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
        self.active_users_lock = threading.Lock()
        self.active_users = set()
        # In-memory subscribers for active gRPC streams.
        self.subscribers_lock = threading.Lock()
        self.subscribers = {}  # {username: {"cond": threading.Condition(), "queue": []}}

    def replicate_to_peers(self, method, rep_req):
        """
        Generic helper to send replication requests to peers.
        
        Parameters:
            method (str): The method to call on peers (e.g., "ReplicateMessage", "ReplicateUser").
            request (protobuf object): The request object to send.
        
        Returns:
            int: Number of successful acknowledgments from peers.
        """
        ack_count = 1  # Leader's own write counts.
        for pid, addr in self.peers:
            if not self.election.peer_status.get(pid, True):
                print(f"[REPL] Skipping peer {pid} at {addr} (marked down).")
                continue
            try:
                print(f"[REPL] Attempting replication to peer {pid} at {addr} using method {method}.")
                channel = grpc.insecure_channel(addr)
                stub = chat_pb2_grpc.ReplicationServiceStub(channel)
                response = getattr(stub, method)(rep_req, timeout=2)
                if response.success:
                    print(f"[REPL] Peer {pid} at {addr} acknowledged replication.")
                    ack_count += 1
                else:
                    print(f"[REPL] Peer {pid} at {addr} did NOT acknowledge replication.")
            except Exception as e:
                print(f"[REPL] Replication error to peer {pid} at {addr}: {e}")
        return ack_count
    
    def GetLeaderInfo(self, request, context):
        """
            Allows client to access the host and port information of the leader
        """
        return chat_pb2.GetLeaderInfoResponse(info=self.election.elect())
    
    def LoadActiveUsersAndSubscribersFromPersistent(self, request, context):
        """
            Called when the client connects to the new leader server, and the 
            new server needs to load the acive_users and subscribers from the persistent
        """
        self.active_users = self.store.active_users_set
        for username in self.store.subscribers_set:
            self.subscribers[username] = {"cond": threading.Condition(), "queue": []}
        return chat_pb2.Empty()

    def CheckVersion(self, request, context):
        if request.version != SERVER_VERSION:
            return chat_pb2.VersionResponse(
                success=False, 
                message=f"Version mismatch. Server: {SERVER_VERSION}, Client: {request.version}"
            )
        return chat_pb2.VersionResponse(success=True, message="success: Version matched")
    
    def Register(self, request, context):
        username, password = request.username, request.password
        print(f"[REGISTER] Attempting to register user: {username}")
        if username in self.store.users:
            print(f"[REGISTER] Username {username} already exists.")
            return chat_pb2.RegisterResponse(message="error: This username is unavailable")
        
        self.store.register(username, password)
        print(f"[REGISTER] User {username} registered in local store.")

        rep_req = chat_pb2.ReplicateRegisterRequest(username=username, password=password)
        ack_count = self.replicate_to_peers("ReplicateRegister", rep_req)
        
        if ack_count >= 2:
            print(f"[REGISTER] Registration successful for {username}.")
        else:
            print(f"[REGISTER] Registration replication failed for {username}.")
            
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

            # Update persistent active users and replicate the login event.
            self.store.add_active_user(username)
            rep_req = chat_pb2.ReplicateActiveUserRequest(username=username)
            ack_count = self.replicate_to_peers("ReplicateActiveUserLogin", rep_req)
            if ack_count >= 2:
                print(f"[LOGIN] Login successful for {username}.")
            else:
                print(f"[LOGIN] Login replication failed for {username}.")

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
            print("[SEND] Not leader, cannot send message.")
            return chat_pb2.SendMessageResponse(status="error: Not leader", message_id="")
        
        sender, recipient, message_text = request.sender, request.recipient, request.message
        recipient_info = self.store.users.get(recipient)
        if not recipient_info or recipient_info.get("deleted", False):
            return chat_pb2.SendMessageResponse(status="error: Recipient not found or deleted", message_id="")

        # Create message with a unique ID.
        msg = {
            "id": str(uuid.uuid4()),
            "from": sender,
            "message": message_text,
            "status": "unread"
        }

        sent_message = self.store.add_message(recipient, msg)

        if sent_message:
            rep_req = chat_pb2.ReplicateMessageRequest(
                message_id=msg["id"],
                sender=sender,
                recipient=recipient,
                message=message_text,
                status="unread"
            )
            ack_count = self.replicate_to_peers("ReplicateMessage", rep_req)

            # With 3 servers, a majority is 2 (leader + one backup).
            if ack_count >= 2:
                print(f"[SEND] Message replication successful, ack count: {ack_count}")
            else:
                print(f"[SEND] Message replication failed, ack count: {ack_count}")
            
            return chat_pb2.SendMessageResponse(status="success", message_id=msg["id"])
        
        print(f"[SEND] Failed to add message to recipient {recipient}'s store.")
        return chat_pb2.SendMessageResponse(status="error: Failed to store message", message_id="")
    
    def Subscribe(self, request, context): # STILL NEED TO REPLICATE SUBSCRIBERS
        """
            Handles subscription request
        """
        username = request.username
        if not self.store.users.get(username):
            context.set_details("User not found")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return
        
        self.store.set_subscription(username, True)
        req_rep = chat_pb2.ReplicateSubscribeRequest(username=username, subscribed=True)
        ack_count = self.replicate_to_peers("ReplicateSubscribe", req_rep)

        # With 3 servers, a majority is 2 (leader + one backup).
        if ack_count >= 2:
            print(f"Subscribers replication successful, ack count: {ack_count}")
        else:
            print(f"Subscribers replication failed, ack count: {ack_count}")
        
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
        count = self.store.mark_read(username, contact, batch_num)

        rep_req = chat_pb2.ReplicateMarkReadRequest(
            username=username,
            contact=contact,
            batch_num=batch_num
        )
        ack_count = self.replicate_to_peers("ReplicateMarkRead", rep_req)

        if ack_count >= 2:
            print("[MARKREAD] replication successful")
        else:
            print("[MAKRREAD] replication failed")
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
        self.store.save()
        if not found:
            return chat_pb2.DeleteUnreadMessageResponse(status="error", message="Message not found or already read")
        
        rep_req = chat_pb2.ReplicateDeleteMessageRequest(sender=sender, recipient=recipient, message_id=message_id)
        ack_count = self.replicate_to_peers("ReplicateDeleteMessage", rep_req)
        if ack_count >= 2:
            print("[DELETEUNREADMESSAGE] replication successful")
        else:
            print("[DELETEUNREADMESSAGE] replication failed")
        return chat_pb2.DeleteUnreadMessageResponse(status="success", message="Message deleted.")
    
    def ReceiveMessages(self, request, context): # NO REPLICATION BECAUSE NO EDIT TO PERSISTENT
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
            rep_req = chat_pb2.ReplicateDeleteAccountRequest(username=username)
            ack_count = self.replicate_to_peers("ReplicateDeleteAccount", rep_req)

            if ack_count >= 2:
                print("[DELETEACCOUNT] replication successful")
            else:
                print("[DELETEACCOUNT] replication failed")
            return chat_pb2.DeleteAccountResponse(message=f"success: Your account '{username}' was deleted.")
        return chat_pb2.DeleteAccountResponse(message="error: User not found or already deleted")
    
    def Logout(self, request, context): # STILL NEED TO REPLICATE BACAUSE ACTIVE_USERS
        username = request.username
        with self.active_users_lock:
            if username in self.active_users:
                self.active_users.remove(username)
                # Remove from persistent active users and replicate the logout event.
                self.store.remove_active_user(username)
                rep_req = chat_pb2.ReplicateActiveUserRequest(username=username)
                ack_count = self.replicate_to_peers("ReplicateActiveUserLogout", rep_req)

                if ack_count >= 2:
                    print("[LOGOUT] replication successful")
                else:
                    print("[LOGOUT] replication failed")
                return chat_pb2.LogoutResponse(message="success: Logged out.")
            return chat_pb2.LogoutResponse(message="error: Failed to log out. User not active.")
# -------------------------
# ReplicationService: Followers use this to replicate messages.
# -------------------------
class ReplicationService(chat_pb2_grpc.ReplicationServiceServicer):
    def __init__(self, store):
        self.store = store

    def ReplicateRegister(self, request, context):
        print(f"[REPL_REGISTER] Replicating registration for user: {request.username}")
        self.store.register(request.username, request.password)
        print(f"[REPL_REGISTER] Registration replicated for user: {request.username}")
        return chat_pb2.ReplicateRegisterResponse(success=True)

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
    
    def ReplicateMarkRead(self, request, context):
        self.store.mark_read(request.username, request.contact, request.batch_num)
        return chat_pb2.ReplicateMarkReadResponse(success=True)
    
    def ReplicateDeleteMessage(self, request, context):
        self.store.delete_message(request.sender, request.recipient, request.message_id)
        return chat_pb2.ReplicateDeleteMessageResponse(success=True)

    def ReplicateDeleteAccount(self, request, context):
        username = request.username
        user = self.store.users.get(username)
        if user and not user.get("deleted", False):
            user["deleted"] = True
            self.store.save()
            return chat_pb2.ReplicateDeleteAccountResponse(success=True)
        return chat_pb2.ReplicateDeleteAccountResponse(success=False)

    def ReplicateSubscribe(self, request, context):
        # Set the subscription flag per persistent store
        if request.username in self.store.users:
            self.store.set_subscription(request.username, request.subscribed)
            return chat_pb2.ReplicateSubscribeResponse(success=True)
        return chat_pb2.ReplicateSubscribeResponse(success=False)
    
    def ReplicateActiveUserLogin(self, request, context):
        # Add active user persistently.
        print(f"[REPL_ACTIVE] Adding active user: {request.username}")
        self.store.add_active_user(request.username)
        return chat_pb2.ReplicateActiveUserResponse(success=True)

    def ReplicateActiveUserLogout(self, request, context):
        # Remove active user persistently.
        print(f"[REPL_ACTIVE] Removing active user: {request.username}")
        self.store.remove_active_user(request.username)
        return chat_pb2.ReplicateActiveUserResponse(success=True)

def clear(ports):
    for server_id in ports.keys():
        filename = f"users_{server_id}.json"
        if os.path.exists(filename):
            os.remove(filename)
            print(f"Cleared {filename}")
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
    # Bind on all interfaces so that external peers can connect:
    server.add_insecure_port(f"0.0.0.0:{port}")
    server.start()
    print(f"Server {server_id} started on {host}:{port}")
    server.wait_for_termination()

# -------------------------
# Launcher: automatically spawn all servers using a ports dictionary.
# -------------------------
def launch_servers():
    global ports
    clear(ports)
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

# if __name__ == "__main__":
#     launch_servers()

# run each server separately
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start a specific server instance.")
    parser.add_argument("--id", type=int, required=True, help="Server ID (1, 2, or 3)")
    parser.add_argument("--all_ips", type=str, required=True,
                        help="Comma-separated list of external IP addresses for all servers (order: server1,server2,server3)")
    
    args = parser.parse_args()
    # Parse the IPs:
    all_ips = args.all_ips.split(",")
    host = all_ips[args.id - 1]  # External IP of this server
    # Build peers list and for all servers: each peer is a tuple (peer_id, "peer_ip:peer_port")
    peers = []
    for i in range(len(all_ips)):
        if (i+1) != args.id:
            peers.append((i+1, f"{all_ips[i]}:{ports[i+1]}"))
        all_host_port_pairs.append(f"{all_ips[i]}:{ports[i+1]}")
    
    if args.id not in ports:
        print(f"Invalid server ID {args.id}. Choose from {list(ports.keys())}.")
    else:
        server_id = args.id
        port = ports[server_id]
        serve(server_id, host, port, peers)

