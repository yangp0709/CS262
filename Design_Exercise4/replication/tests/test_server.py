# ----------------------------------------------------------------------------------
# test_server.py
# ----------------------------------------------------------------------------------
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
import threading
import time
import grpc
import subprocess

import chat_pb2
import chat_pb2_grpc
import server

"""
Amended tests to accommodate the revised server code which uses PersistentStore and
no longer stores data in global dictionaries. We spin up a single server instance
(listening on localhost:5001) for all tests. For data isolation, we rely on
unique user-names or repeated Register/Delete steps within each test.
"""

class TestChatService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """
        Start the gRPC server in a separate thread before running any tests.
        We pass server_id=1, host=localhost, port=5001, peers=[] for a single-server scenario.
        """
        # Clear any existing JSON files before starting
        server.clear(server.ports)  # Wipes out users_1.json, users_2.json, etc.

        # For testing with a single server, populate the global host/port list.
        server.all_host_port_pairs = ["localhost:5001"]

        cls.server_thread = threading.Thread(
            target=lambda: server.serve(server_id=1, host='localhost', port=5001, peers=[]),
            daemon=True
        )
        cls.server_thread.start()
        time.sleep(1)  # Give the server a moment to start

        # Create a channel and stub for all tests
        cls.channel = grpc.insecure_channel('localhost:5001')
        cls.stub = chat_pb2_grpc.ChatServiceStub(cls.channel)

    @classmethod
    def tearDownClass(cls):
        """
        Attempt to close the gRPC channel at the end of tests.
        """
        cls.channel.close()
        # The server thread is daemon=True so it will exit when tests finish.

    # -------------------------------------------------------------------------
    # 1. Version Check Tests
    # -------------------------------------------------------------------------
    def test_check_version_success(self):
        response = self.stub.CheckVersion(chat_pb2.Version(version="1.0.0"))
        self.assertTrue(response.success)
        self.assertIn("Version matched", response.message)
    
    def test_check_version_mismatch(self):
        response = self.stub.CheckVersion(chat_pb2.Version(version="999.999.999"))
        self.assertFalse(response.success)
        self.assertIn("Version mismatch", response.message)

    # -------------------------------------------------------------------------
    # 2. Register Tests
    # -------------------------------------------------------------------------
    def test_handle_register_success(self):
        # Ensure a unique username
        uname = "testuser_register_success"
        response = self.stub.Register(
            chat_pb2.RegisterRequest(username=uname, password="password123")
        )
        self.assertIn("success", response.message)

    def test_handle_register_duplicate(self):
        uname = "testuser_dup"
        self.stub.Register(
            chat_pb2.RegisterRequest(username=uname, password="password123")
        )
        response = self.stub.Register(
            chat_pb2.RegisterRequest(username=uname, password="anotherpass")
        )
        self.assertIn("error", response.message)

    # -------------------------------------------------------------------------
    # 3. Login Tests
    # -------------------------------------------------------------------------
    def test_handle_login_success(self):
        uname = "login_success_user"
        pwd = "pass123"
        self.stub.Register(
            chat_pb2.RegisterRequest(username=uname, password=pwd)
        )
        response = self.stub.Login(
            chat_pb2.LoginRequest(username=uname, password=pwd)
        )
        self.assertIn("success: Logged in", response.message)
        self.assertGreaterEqual(response.unread_messages, 0)

    def test_handle_login_already_logged_in(self):
        uname = "already_logged_in_user"
        pwd = "pass123"
        self.stub.Register(chat_pb2.RegisterRequest(username=uname, password=pwd))
        self.stub.Login(chat_pb2.LoginRequest(username=uname, password=pwd))
        # Try logging in again:
        response = self.stub.Login(chat_pb2.LoginRequest(username=uname, password=pwd))
        self.assertIn("error: User already logged in", response.message)

    def test_handle_login_invalid_password(self):
        uname = "login_invalid_pass"
        self.stub.Register(chat_pb2.RegisterRequest(username=uname, password="correct"))
        response = self.stub.Login(chat_pb2.LoginRequest(username=uname, password="WRONGPASS"))
        self.assertIn("error: Invalid username or password", response.message)

    # -------------------------------------------------------------------------
    # 4. List Users Test
    # -------------------------------------------------------------------------
    def test_handle_list_users(self):
        u1 = "list_user1"
        u2 = "list_user2"
        u3 = "list_user3"
        self.stub.Register(chat_pb2.RegisterRequest(username=u1, password="p1"))
        self.stub.Register(chat_pb2.RegisterRequest(username=u2, password="p2"))
        self.stub.Register(chat_pb2.RegisterRequest(username=u3, password="p3"))
        # Delete user3
        self.stub.DeleteAccount(chat_pb2.DeleteAccountRequest(username=u3))
        response = self.stub.ListUsers(chat_pb2.ListUsersRequest())
        # We expect only user1, user2 to be returned
        self.assertIn(u1, response.users)
        self.assertIn(u2, response.users)
        self.assertNotIn(u3, response.users)

    # -------------------------------------------------------------------------
    # 5. Send Message Tests
    # -------------------------------------------------------------------------
    def test_handle_send_success(self):
        sender = "sender_ok"
        recipient = "recipient_ok"
        self.stub.Register(chat_pb2.RegisterRequest(username=sender, password="pass"))
        self.stub.Register(chat_pb2.RegisterRequest(username=recipient, password="pass"))

        send_resp = self.stub.SendMessage(chat_pb2.SendMessageRequest(
            sender=sender, recipient=recipient, message="Hello!"
        ))
        self.assertEqual(send_resp.status, "success")
        self.assertNotEqual(send_resp.message_id, "")

        # Check in recipient's messages:
        rcv_resp = self.stub.ReceiveMessages(chat_pb2.ReceiveMessagesRequest(username=recipient))
        # We should have exactly one message with text "Hello!"
        msgs = [m for m in rcv_resp.messages if m.message == "Hello!"]
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].status, "unread")

    def test_handle_send_nonexistent_recipient(self):
        sender = "sender_nonexistent"
        self.stub.Register(chat_pb2.RegisterRequest(username=sender, password="pass"))
        resp = self.stub.SendMessage(chat_pb2.SendMessageRequest(
            sender=sender, recipient="unknown_user", message="Hello"
        ))
        self.assertIn("error", resp.status)
        self.assertEqual(resp.message_id, "")

    def test_handle_send_deleted_recipient(self):
        sender = "sender_deleted_r"
        recipient = "recipient_deleted"
        self.stub.Register(chat_pb2.RegisterRequest(username=sender, password="pass"))
        self.stub.Register(chat_pb2.RegisterRequest(username=recipient, password="pass"))
        # Delete the recipient
        self.stub.DeleteAccount(chat_pb2.DeleteAccountRequest(username=recipient))

        resp = self.stub.SendMessage(chat_pb2.SendMessageRequest(
            sender=sender, recipient=recipient, message="Hello"
        ))
        self.assertIn("error: Recipient not found or deleted", resp.status)

    # -------------------------------------------------------------------------
    # 6. Mark Read Tests
    # -------------------------------------------------------------------------
    def test_mark_all_messages_as_read(self):
        contact1 = "mr_user1"
        contact2 = "mr_user2"
        contact3 = "mr_user3"
        self.stub.Register(chat_pb2.RegisterRequest(username=contact1, password="p"))
        self.stub.Register(chat_pb2.RegisterRequest(username=contact2, password="p"))
        self.stub.Register(chat_pb2.RegisterRequest(username=contact3, password="p"))

        # contact2 -> contact1 (m1), contact3 -> contact1 (m2), contact2 -> contact1 (m3)
        self.stub.SendMessage(chat_pb2.SendMessageRequest(sender=contact2, recipient=contact1, message="m1"))
        self.stub.SendMessage(chat_pb2.SendMessageRequest(sender=contact3, recipient=contact1, message="m2"))
        self.stub.SendMessage(chat_pb2.SendMessageRequest(sender=contact2, recipient=contact1, message="m3"))

        response = self.stub.MarkRead(chat_pb2.MarkReadRequest(
            username=contact1, contact=contact2, batch_num=0 
        ))
        self.assertIn("Marked 2 messages as read", response.message)

        # Verify statuses
        msgs_resp = self.stub.ReceiveMessages(chat_pb2.ReceiveMessagesRequest(username=contact1))
        statuses = {m.message: m.status for m in msgs_resp.messages}
        self.assertEqual(statuses["m1"], "read")
        self.assertEqual(statuses["m2"], "unread")
        self.assertEqual(statuses["m3"], "read")

    def test_mark_specific_number_of_messages(self):
        contact1 = "mr_batch_user1"
        contact2 = "mr_batch_user2"
        self.stub.Register(chat_pb2.RegisterRequest(username=contact1, password="p"))
        self.stub.Register(chat_pb2.RegisterRequest(username=contact2, password="p"))

        # contact2 -> contact1: m1, m2, m3
        self.stub.SendMessage(chat_pb2.SendMessageRequest(sender=contact2, recipient=contact1, message="m1"))
        self.stub.SendMessage(chat_pb2.SendMessageRequest(sender=contact2, recipient=contact1, message="m2"))
        self.stub.SendMessage(chat_pb2.SendMessageRequest(sender=contact2, recipient=contact1, message="m3"))

        response = self.stub.MarkRead(chat_pb2.MarkReadRequest(
            username=contact1, contact=contact2, batch_num=2
        ))
        self.assertIn("Marked 2 messages as read", response.message)

        msgs = self.stub.ReceiveMessages(chat_pb2.ReceiveMessagesRequest(username=contact1)).messages
        statuses = {m.message: m.status for m in msgs}
        self.assertEqual(statuses["m1"], "read")
        self.assertEqual(statuses["m2"], "read")
        self.assertEqual(statuses["m3"], "unread")

    def test_mark_read_user_not_found(self):
        # Mark read on a nonexistent user
        with self.assertRaises(grpc.RpcError) as context_manager:
            self.stub.MarkRead(chat_pb2.MarkReadRequest(
                username="nonexistent_user", contact="somecontact", batch_num=0
            ))
        rpc_error = context_manager.exception
        self.assertEqual(rpc_error.code(), grpc.StatusCode.NOT_FOUND)
        self.assertEqual(rpc_error.details(), "User not found")

    # -------------------------------------------------------------------------
    # 7. Delete Unread Message Tests
    # -------------------------------------------------------------------------
    def test_handle_delete_unread_message_success(self):
        sender = "del_sender"
        recipient = "del_recipient"
        self.stub.Register(chat_pb2.RegisterRequest(username=sender, password="p"))
        self.stub.Register(chat_pb2.RegisterRequest(username=recipient, password="p"))

        # Send a message -> unread in recipient
        send_resp = self.stub.SendMessage(chat_pb2.SendMessageRequest(
            sender=sender, recipient=recipient, message="Hello"
        ))
        msg_id = send_resp.message_id

        del_resp = self.stub.DeleteUnreadMessage(chat_pb2.DeleteUnreadMessageRequest(
            sender=sender, recipient=recipient, message_id=msg_id
        ))
        self.assertEqual(del_resp.status, "success")
        self.assertIn("deleted", del_resp.message.lower())

        # Check the message status
        rcv_resp = self.stub.ReceiveMessages(chat_pb2.ReceiveMessagesRequest(username=recipient))
        for m in rcv_resp.messages:
            if m.id == msg_id:
                self.assertEqual(m.status, "deleted")

    def test_handle_delete_unread_message_not_found(self):
        sender = "del_nf_sender"
        recipient = "del_nf_recipient"
        self.stub.Register(chat_pb2.RegisterRequest(username=sender, password="p"))
        self.stub.Register(chat_pb2.RegisterRequest(username=recipient, password="p"))

        # Do not send a message with ID=999
        response = self.stub.DeleteUnreadMessage(chat_pb2.DeleteUnreadMessageRequest(
            sender=sender, recipient=recipient, message_id="999"
        ))
        self.assertEqual(response.status, "error")
        self.assertIn("not found or already read", response.message)

    # -------------------------------------------------------------------------
    # 8. Receive Messages Tests
    # -------------------------------------------------------------------------
    def test_handle_receive_messages_success(self):
        userA = "rm_userA"
        userB = "rm_userB"
        self.stub.Register(chat_pb2.RegisterRequest(username=userA, password="p"))
        self.stub.Register(chat_pb2.RegisterRequest(username=userB, password="p"))

        # userB -> userA
        self.stub.SendMessage(chat_pb2.SendMessageRequest(sender=userB, recipient=userA, message="TestMsg"))

        response = self.stub.ReceiveMessages(chat_pb2.ReceiveMessagesRequest(username=userA))
        self.assertIn("success", response.status)
        self.assertTrue(len(response.messages) >= 1)
        msgs = [m for m in response.messages if m.message == "TestMsg"]
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].sender, userB)

    def test_handle_receive_messages_account_not_found(self):
        response = self.stub.ReceiveMessages(chat_pb2.ReceiveMessagesRequest(username="nonexistent_xyz"))
        self.assertIn("error: User not found", response.status)
        self.assertEqual(len(response.messages), 0)

    # -------------------------------------------------------------------------
    # 9. Delete Account Tests
    # -------------------------------------------------------------------------
    def test_handle_delete_account_success(self):
        uname = "delete_acc_user"
        self.stub.Register(chat_pb2.RegisterRequest(username=uname, password="p"))
        response = self.stub.DeleteAccount(chat_pb2.DeleteAccountRequest(username=uname))
        self.assertIn("success", response.message)

        # Confirm it's not in the list
        list_resp = self.stub.ListUsers(chat_pb2.ListUsersRequest())
        self.assertNotIn(uname, list_resp.users)

    def test_handle_delete_account_nonexistent(self):
        response = self.stub.DeleteAccount(chat_pb2.DeleteAccountRequest(username="unknown_user"))
        self.assertIn("error: User not found", response.message)

    def test_handle_delete_account_already_deleted(self):
        uname = "already_del"
        self.stub.Register(chat_pb2.RegisterRequest(username=uname, password="p"))
        self.stub.DeleteAccount(chat_pb2.DeleteAccountRequest(username=uname))
        response = self.stub.DeleteAccount(chat_pb2.DeleteAccountRequest(username=uname))
        self.assertIn("error: User not found or already deleted", response.message)

    # -------------------------------------------------------------------------
    # 10. Logout Tests
    # -------------------------------------------------------------------------
    def test_handle_logout_success(self):
        uname = "logout_success_user"
        self.stub.Register(chat_pb2.RegisterRequest(username=uname, password="p"))
        self.stub.Login(chat_pb2.LoginRequest(username=uname, password="p"))

        response = self.stub.Logout(chat_pb2.LogoutRequest(username=uname))
        self.assertIn("success: Logged out", response.message)

    def test_handle_logout_non_active_user(self):
        uname = "logout_non_active"
        self.stub.Register(chat_pb2.RegisterRequest(username=uname, password="p"))
        # Attempt logout without ever logging in
        response = self.stub.Logout(chat_pb2.LogoutRequest(username=uname))
        self.assertIn("error: Failed to log out. User not active.", response.message)


###############################################################################
# Multi-server + 2-fault-tolerance demonstration
###############################################################################

class TestFaultToleranceCLI(unittest.TestCase):
    """
    Demonstrates how to spin up the servers by mimicking CLI usage
    in a single test environment.
    """

    @classmethod
    def setUpClass(cls):
        """
        1) Clear any leftover .json
        2) Launch 3 servers with subprocess.Popen
        3) Wait for them to start
        """
        # For example, if your 'server.py' has a 'clear(ports)' function,
        # either call that beforehand or delete the .json files in Python.

        # Start each server. We assume:
        #   python server.py --id 1 --all_ips localhost,localhost,localhost
        #   python server.py --id 2 --all_ips localhost,localhost,localhost
        #   python server.py --id 3 --all_ips localhost,localhost,localhost
        # That means each server binds on ports: {1:8001, 2:8002, 3:8003} or similar.

        server.clear(server.ports)

        cls.procs = []
        # Start server #1
        p1 = subprocess.Popen(
            ["python", "server.py", "--id", "1", "--all_ips", "localhost,localhost,localhost"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        cls.procs.append(p1)

        # Start server #2
        p2 = subprocess.Popen(
            ["python", "server.py", "--id", "2", "--all_ips", "localhost,localhost,localhost"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        cls.procs.append(p2)

        # Start server #3
        p3 = subprocess.Popen(
            ["python", "server.py", "--id", "3", "--all_ips", "localhost,localhost,localhost"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        cls.procs.append(p3)

        # Wait a bit for them to come online and elect a leader
        time.sleep(3)

        # We'll build stubs for each server if needed. For example, 
        # if we know port mapping is {1->8001, 2->8002, 3->8003}, do:
        cls.channel1 = grpc.insecure_channel("localhost:8001")
        cls.channel2 = grpc.insecure_channel("localhost:8002")
        cls.channel3 = grpc.insecure_channel("localhost:8003")

        cls.stub1 = chat_pb2_grpc.ChatServiceStub(cls.channel1)
        cls.stub2 = chat_pb2_grpc.ChatServiceStub(cls.channel2)
        cls.stub3 = chat_pb2_grpc.ChatServiceStub(cls.channel3)

    @classmethod
    def tearDownClass(cls):
        """
        Terminate all server processes and wait for them to exit.
        """
        for p in cls.procs:
            if p.poll() is None:  # still running?
                p.terminate()
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()

        # Close gRPC channels
        cls.channel1.close()
        cls.channel2.close()
        cls.channel3.close()

        server.clear(server.ports)  # Clear all user_*.json files

    def test_leader_election_and_failover(self):
        """
        Extended test that:
        1) Identifies the leader among the 3 servers
        2) Registers a user on the leader
        3) Kills the leader process
        4) Verifies a new leader
        5) Checks user data is still present
        6) Registers another user on the new leader
        7) Kills the new leader
        8) Repeats until all servers are dead
        9) Ensures an error is raised when no leader remains
        """

        registered_users = []

        # ---------------------------
        # Step 1: Identify leader
        # ---------------------------
        leader_stub = None
        for stub in [self.stub1, self.stub2, self.stub3]:
            try:
                resp = stub.GetLeaderInfo(chat_pb2.GetLeaderInfoRequest(), timeout=1)
                if resp.info:
                    leader_stub = stub
                    break
            except:
                pass
        self.assertIsNotNone(leader_stub, "No leader found among the 3 servers")

        # ---------------------------
        # Step 2: Register a user
        # ---------------------------
        uname = "cli_test_user"
        reg_resp = leader_stub.Register(
            chat_pb2.RegisterRequest(username=uname, password="cli_test_pw"))
        self.assertIn("success", reg_resp.message)
        registered_users.append(uname)

        # ---------------------------
        # Helper to find which process is leader
        # ---------------------------
        def find_leader_index():
            for i, s in enumerate([self.stub1, self.stub2, self.stub3]):
                try:
                    r = s.GetLeaderInfo(chat_pb2.GetLeaderInfoRequest(), timeout=1)
                    if r.info:
                        return i
                except:
                    pass
            return None

        # ---------------------------
        # Step 3 & 4: Kill current leader, see who becomes new leader
        # (We will repeat this until all servers die.)
        # ---------------------------
        def kill_leader_and_get_new_leader(old_leader_stub):
            """
            Terminates the current leader and returns a stub for the newly elected leader.
            If none can be found, returns None.
            """
            # Find index of current leader
            leader_idx = find_leader_index()
            self.assertIsNotNone(leader_idx, "Could not identify the leader to kill it.")
            leader_proc = self.procs[leader_idx]
            if leader_proc.poll() is None:
                leader_proc.terminate()
                leader_proc.wait(timeout=3)

            # Wait a bit for new leader to appear
            time.sleep(2)
            new_leader_stub = None
            for s in [self.stub1, self.stub2, self.stub3]:
                # skip the old leader if it's the same stub
                if s == old_leader_stub:
                    continue
                try:
                    resp = s.GetLeaderInfo(chat_pb2.GetLeaderInfoRequest(), timeout=1)
                    if resp.info:
                        new_leader_stub = s
                        break
                except:
                    pass
            return new_leader_stub

        # ---------------------------
        # Check our old user is visible on the new leader
        # ---------------------------
        def verify_all_users_on_leader(leader_stub, user_list):
            resp = leader_stub.ListUsers(chat_pb2.ListUsersRequest())
            for u in user_list:
                self.assertIn(u, resp.users, f"User {u} missing on new leader's user list.")

        # ---------------------------
        # Perform the kill-failover cycle until no servers remain alive
        # ---------------------------
        while True:
            # Step 3 & 4: kill the current leader
            new_leader_stub = kill_leader_and_get_new_leader(leader_stub)
            if not new_leader_stub:
                # We found no new leader, presumably all servers are dead
                break

            # Step 5: confirm old users are still present
            verify_all_users_on_leader(new_leader_stub, registered_users)

            # Step 6: register a fresh user on the new leader
            new_uname = f"cli_test_user_{len(registered_users)+1}"
            reg = new_leader_stub.Register(
                chat_pb2.RegisterRequest(username=new_uname, password="cli_test_pw"))
            self.assertIn("success", reg.message)
            registered_users.append(new_uname)

            # Update leader_stub reference for the next iteration
            leader_stub = new_leader_stub

            # If only one server left, next iteration might kill it,
            # so we let the loop continue until it fails to find a new leader
            alive = [p for p in self.procs if p.poll() is None]
            if len(alive) == 0:
                # All are dead, break
                break

        # ---------------------------
        # Step 9: Confirm an error is raised if we look for a leader now
        # ---------------------------
        with self.assertRaises(AssertionError):
            idx = find_leader_index()  # expecting None
            self.assertIsNotNone(idx, "Somehow found a leader even though all servers should be dead!")

if __name__ == "__main__":
    unittest.main()
