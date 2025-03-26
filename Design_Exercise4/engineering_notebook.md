 # Overview

Codebase: https://github.com/yangp0709/CS262/tree/main/Design_Exercise4

This chat application is built using gRPC for communication between clients and servers. The system is designed to be both persistent and fault tolerant. Persistence is achieved via local JSON files that store user data, messages, and subscription status. The system’s fault tolerance is ensured by a replication mechanism that requires a majority of servers to acknowledge write operations, making it 2‑fault tolerant in a three‑server configuration (which can be extended to as many servers as needed given the proper number of IPs). Leader election is implemented to determine which server is responsible for handling client requests and replicating data to backup nodes.

---

# Architecture and Components

- **Client Application (client.py):**
  - Provides a Tkinter GUI for user login, registration, messaging, and real-time updates.
  - Connects to a leader server by querying the current leader from all available servers.
  - Handles version checking and subscription management for receiving live messages.

- **Server Application (server.py):**
  - **PersistentStore:**  
    Manages local data storage in a JSON file for each server. It maintains:
    - User accounts (including hashed passwords).
    - Message lists (with statuses like “unread,” “read,” or “deleted”).
    - Active users and subscriber queues.
    
  - **LeaderElection:**  
    Implements a simple, fixed-ordering election where each server periodically pings its peers. The server with no lower‑numbered server_id peer alive becomes the leader.
    
  - **ChatService:**  
    Contains the logic for registration, login, sending messages, marking messages as read, and deleting messages. Only the leader is allowed to process write operations (e.g., sending a message) and then replicates these changes to the backup servers.
    
  - **ReplicationService:**  
    Provides methods that backup servers use to replicate data (such as user registration, message sending, marking messages as read, etc.) from the leader.
    
  - **HealthService:**  
    Provides a simple Ping method which all servers use to ping each other to check alive status during leader election. This service allows servers to send heartbeats to each other for verifying alive status.

---

# Fault Tolerance: 2‑Fault Tolerance

- **Replication Quorum:**  
  When a client performs a write operation (e.g., sending a message or registering an account), the leader updates its local store and then replicates the change to the backup servers. With three servers, the operation is considered successful if at least 2 (the leader and one backup) acknowledge the replication. This majority quorum ensures that the system can tolerate the crash of one server while still preserving the data.

- **Permanent Failure Assumption:**  
  The design assumes that once a server dies (due to a crash or fail-stop failure), it does not come back online. This assumption simplifies the replication protocol because there is no need to “catch up” a previously failed node with missing messages. Instead, the system only focuses on the remaining servers for a majority decision.

---

# Persistence

- **Local JSON Files:**  
  Each server maintains a persistent data store by writing its state to a local JSON file (e.g., `users_1.json`, `users_2.json`, `users_3.json`). This file stores:
  - User account details.
  - Message histories (including message statuses).
  - Subscriber information and active user sets.
  
- **Synchronized Replication:**  
  The leader replicates updates (such as new messages, registration events, or subscription changes) to the peers, which in turn update their own JSON files. This ensures that even if a server crashes during operation, the persistent state remains intact and is loaded on restart.

- **Thread-Safe Updates:**  
  The `PersistentStore` class uses reentrant locks (`RLock`) to ensure that updates to the JSON file and in‑memory data structures occur in a thread‑safe manner.

---

# Leader Election

- **Fixed Ordering:**  
  Leader election is managed by the `LeaderElection` class. Each server has a unique ID, and the algorithm uses a fixed ordering:
  - Each server periodically pings its peers, getting a heartbeat back from alive servers.
  - A server becomes the leader if none of the peers with a lower server ID are alive.
  - If any lower‑numbered peer is alive, the server remains a backup and the leader is set to the lowest‑numbered server that is alive.
  
- **Ping Mechanism:**  
  The `ping_peer` method sends a simple health check via the Health service. If a peer fails to respond, its status is permanently marked as down (this fits the assumption that a failed server will not come back).

- **Continuous Election Loop:**  
  The election process runs in its own thread and periodically updates the server’s state (leader or backup) based on the current availability of peers. This design ensures that clients always get updated leader information when connecting.

---

# Design Decisions

1. **Servers Cannot Come Back After Dying:**
   - *Rationale:*  
     By treating failed servers as permanently down, the implementation avoids the complexity of state synchronization for recovering servers. This eliminates the need for catch-up protocols and simplifies the overall replication logic.

2. **Use of Locks:**
   - *Rationale:*  
     Locks are used extensively (for example, in the `PersistentStore` and during replication calls) to ensure that no two operations are trying to update the state concurrently. This ensures that replication and request handling are synchronous, reducing the risk of data inconsistencies.

3. **Local JSON Files for Persistence:**
   - *Rationale:*  
     Each server writes to its own local JSON file to persist data. This file is updated whenever a change occurs, and changes are replicated from the leader. Using a simple JSON file makes the persistence mechanism transparent and easy to debug.

4. **Use of JSON Instead of Protocol Buffers for Persistence:**
   - *Rationale:*  
     Although gRPC uses protocol buffers for network communication, JSON is chosen for local storage because it is easier to read, debug, and manage. This choice simplifies the task of inspecting, debugging, and maintaining the persistent state on each server.

---

# Summary

This implementation of a chat system using gRPC is designed with a focus on persistence, fault tolerance, and simplicity. By employing a leader-based replication strategy with a majority quorum, using local JSON files for state persistence, and adopting a simple fixed-order leader election mechanism, the system achieves both 2‑fault tolerance and ease of maintenance. The deliberate design decisions (such as not allowing failed servers to recover and using locks for synchronous operations) further simplify the overall implementation while ensuring data consistency and robustness.

Feel free to ask if you need further clarification or additional details on any part of the implementation!

