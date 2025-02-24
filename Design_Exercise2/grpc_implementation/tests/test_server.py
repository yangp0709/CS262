#!/Users/jlin/Desktop/cs2620/CS262/Design_Exercise2/cs2620_design_exercise_2_env/bin/python
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
import threading
import time
import grpc

import chat_pb2
import chat_pb2_grpc
import server 

class TestChatService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """
        Start the gRPC server in a separate thread before running any tests.
        Create a gRPC channel + stub for client calls.
        """
        cls.server_thread = threading.Thread(target=server.serve, daemon=True)
        cls.server_thread.start()
        time.sleep(1)  # Give the server a moment to start
        
        # Create a channel and stub for all tests to use
        cls.channel = grpc.insecure_channel('localhost:5001')
        cls.stub = chat_pb2_grpc.ChatServiceStub(cls.channel)

    def setUp(self):
        """
        Clear global dictionaries before each test to ensure a clean state.
        """
        server.users.clear()
        server.active_users.clear()
        server.subscribers.clear()

    # -------------------------------------------------------------------------
    # 1. Version Check Tests
    # -------------------------------------------------------------------------
    def test_check_version_success(self):
        """
        Test that CheckVersion returns success when the client version matches the server version.
        """
        response = self.stub.CheckVersion(chat_pb2.Version(version="1.0.0"))
        self.assertTrue(response.success)
        self.assertIn("Version matched", response.message)
    
    def test_check_version_mismatch(self):
        """
        Test that CheckVersion returns an error when the client version does not match the server version.
        """
        response = self.stub.CheckVersion(chat_pb2.Version(version="999.999.999"))
        self.assertFalse(response.success)
        self.assertIn("Version mismatch", response.message)

    # -------------------------------------------------------------------------
    # 2. Register Tests
    # -------------------------------------------------------------------------
    def test_handle_register_success(self):
        """
        Test successful user registration.
        Verifies that the server returns a success message and that the user is added to the user store.
        """
        response = self.stub.Register(
            chat_pb2.RegisterRequest(username="testuser", password="password123")
        )
        self.assertIn("success", response.message)
        self.assertIn("testuser", server.users)
    
    def test_handle_register_duplicate(self):
        """
        Test registration of a duplicate user.
        Verifies that attempting to register an already existing user returns an error message.
        """
        self.stub.Register(
            chat_pb2.RegisterRequest(username="testuser", password="password123")
        )
        response = self.stub.Register(
            chat_pb2.RegisterRequest(username="testuser", password="anotherpass")
        )
        self.assertIn("error", response.message)

    # -------------------------------------------------------------------------
    # 3. Login Tests
    # -------------------------------------------------------------------------
    def test_handle_login_success(self):
        """
        Test successful user login.
        Verifies that a registered user can log in with correct credentials and is added to active users.
        """
        self.stub.Register(
            chat_pb2.RegisterRequest(username="testuser", password="pass123")
        )
        response = self.stub.Login(
            chat_pb2.LoginRequest(username="testuser", password="pass123")
        )
        self.assertIn("success: Logged in", response.message)
        self.assertIn("testuser", server.active_users)
        self.assertEqual(response.unread_messages, 0)

    def test_handle_login_already_logged_in(self):
        """
        Test logging in when the user is already logged in.
        Verifies that a second login attempt returns an error and that the active users set remains unchanged.
        """
        self.stub.Register(
            chat_pb2.RegisterRequest(username="testuser", password="pass123")
        )
        self.stub.Login(chat_pb2.LoginRequest(username="testuser", password="pass123"))
        response = self.stub.Login(chat_pb2.LoginRequest(username="testuser", password="pass123"))
        self.assertIn("error: User already logged in", response.message)
        self.assertIn("testuser", server.active_users)

    def test_handle_login_invalid_password(self):
        """
        Test login with an invalid password.
        Verifies that the server returns an error and the user is not added to active users.
        """
        self.stub.Register(
            chat_pb2.RegisterRequest(username="testuser", password="pass123")
        )
        response = self.stub.Login(chat_pb2.LoginRequest(username="testuser", password="WRONGPASS"))
        self.assertIn("error: Invalid username or password", response.message)
        self.assertNotIn("testuser", server.active_users)

    # -------------------------------------------------------------------------
    # 4. List Users Test
    # -------------------------------------------------------------------------
    def test_handle_list_users(self):
        """
        Test listing of users.
        Verifies that only non-deleted users are returned by the ListUsers call.
        """
        self.stub.Register(chat_pb2.RegisterRequest(username="user1", password="p1"))
        self.stub.Register(chat_pb2.RegisterRequest(username="user2", password="p2"))
        self.stub.Register(chat_pb2.RegisterRequest(username="user3", password="p3"))
        server.users["user3"]["deleted"] = True
        response = self.stub.ListUsers(chat_pb2.ListUsersRequest())
        self.assertCountEqual(response.users, ["user1", "user2"])

    # -------------------------------------------------------------------------
    # 5. Send Message Tests
    # -------------------------------------------------------------------------
    def test_handle_send_success(self):
        """
        Test sending a message successfully.
        Verifies that a message is sent, a unique message ID is generated, and the message is stored as unread.
        """
        self.stub.Register(chat_pb2.RegisterRequest(username="sender", password="pass"))
        self.stub.Register(chat_pb2.RegisterRequest(username="recipient", password="pass"))
        response = self.stub.SendMessage(chat_pb2.SendMessageRequest(
            sender="sender", recipient="recipient", message="Hello!"
        ))
        self.assertEqual(response.status, "success")
        self.assertNotEqual(response.message_id, "")
        msgs = server.users["recipient"]["messages"]
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["message"], "Hello!")
        self.assertEqual(msgs[0]["status"], "unread")

    def test_handle_send_nonexistent_recipient(self):
        """
        Test sending a message to a non-existent recipient.
        Verifies that an error is returned and no message ID is generated.
        """
        self.stub.Register(chat_pb2.RegisterRequest(username="sender", password="pass"))
        response = self.stub.SendMessage(chat_pb2.SendMessageRequest(
            sender="sender", recipient="recipient", message="Hello"
        ))
        self.assertIn("error", response.status)
        self.assertEqual(response.message_id, "")

    def test_handle_send_deleted_recipient(self):
        """
        Test sending a message to a deleted recipient.
        Verifies that the server returns an error indicating the recipient is not available.
        """
        self.stub.Register(chat_pb2.RegisterRequest(username="sender", password="pass"))
        self.stub.Register(chat_pb2.RegisterRequest(username="recipient", password="pass"))
        server.users["recipient"]["deleted"] = True
        response = self.stub.SendMessage(chat_pb2.SendMessageRequest(
            sender="sender", recipient="recipient", message="Hello"
        ))
        self.assertIn("error: Recipient not found or deleted", response.status)

    # -------------------------------------------------------------------------
    # 6. Mark Read Tests
    # -------------------------------------------------------------------------
    def test_mark_all_messages_as_read(self):
        """
        Test marking all unread messages from a specific contact as read.
        Verifies that only messages from the given contact are marked as read.
        """
        server.users["contact1"] = {
            "password": "p",
            "messages": [
                {"from": "contact2", "message": "m1", "status": "unread"},
                {"from": "contact3", "message": "m2", "status": "unread"},
                {"from": "contact2", "message": "m3", "status": "unread"},
            ],
        }
        response = self.stub.MarkRead(chat_pb2.MarkReadRequest(
            username="contact1",
            contact="contact2",
            batch_num=0 
        ))
        self.assertIn("Marked 2 messages as read", response.message)
        msgs = server.users["contact1"]["messages"]
        self.assertEqual(msgs[0]["status"], "read")  
        self.assertEqual(msgs[1]["status"], "unread") 
        self.assertEqual(msgs[2]["status"], "read") 

    def test_mark_specific_number_of_messages(self):
        """
        Test marking a specific number of unread messages as read.
        Verifies that only the specified number of messages are marked as read.
        """
        server.users["contact1"] = {
            "password": "p",
            "messages": [
                {"from": "contact2", "message": "m1", "status": "unread"},
                {"from": "contact2", "message": "m2", "status": "unread"},
                {"from": "contact2", "message": "m3", "status": "unread"},
            ],
        }
        response = self.stub.MarkRead(chat_pb2.MarkReadRequest(
            username="contact1",
            contact="contact2",
            batch_num=2
        ))
        self.assertIn("Marked 2 messages as read", response.message)
        msgs = server.users["contact1"]["messages"]
        self.assertEqual(msgs[0]["status"], "read")
        self.assertEqual(msgs[1]["status"], "read")
        self.assertEqual(msgs[2]["status"], "unread")

    def test_mark_read_user_not_found(self):
        """
        Test marking messages as read for a non-existent user.
        Verifies that a NOT_FOUND error is returned.
        """
        with self.assertRaises(grpc.RpcError) as context_manager:
            self.stub.MarkRead(chat_pb2.MarkReadRequest(
                username="nonexistent",
                contact="somecontact",
                batch_num=0
            ))
        rpc_error = context_manager.exception
        self.assertEqual(rpc_error.code(), grpc.StatusCode.NOT_FOUND)
        self.assertEqual(rpc_error.details(), "User not found")

    # -------------------------------------------------------------------------
    # 7. Delete Unread Message Tests
    # -------------------------------------------------------------------------
    def test_handle_delete_unread_message_success(self):
        """
        Test successfully deleting an unread message.
        Verifies that the message status is updated to 'deleted'.
        """
        server.users["recipient"] = {
            "password": "p",
            "messages": [{"id": "123", "from": "sender", "message": "Hello", "status": "unread"}],
        }
        response = self.stub.DeleteUnreadMessage(chat_pb2.DeleteUnreadMessageRequest(
            sender="sender",
            recipient="recipient",
            message_id="123",
        ))
        self.assertEqual(response.status, "success")
        self.assertIn("deleted", response.message.lower())
        self.assertEqual(server.users["recipient"]["messages"][0]["status"], "deleted")

    def test_handle_delete_unread_message_not_found(self):
        """
        Test attempting to delete a non-existent or already-read message.
        Verifies that an error is returned.
        """
        server.users["recipient"] = {"password": "p", "messages": []}
        response = self.stub.DeleteUnreadMessage(chat_pb2.DeleteUnreadMessageRequest(
            sender="sender",
            recipient="recipient",
            message_id="999",
        ))
        self.assertEqual(response.status, "error")
        self.assertIn("not found or already read", response.message)

    # -------------------------------------------------------------------------
    # 8. Receive Messages Tests
    # -------------------------------------------------------------------------
    def test_handle_receive_messages_success(self):
        """
        Test successfully retrieving messages for a user.
        Verifies that the server returns a success status and the correct messages.
        """
        server.users["recipient"] = {
            "password": "p",
            "messages": [{"id": "1", "from": "sender", "message": "Test", "status": "read"}],
        }
        response = self.stub.ReceiveMessages(chat_pb2.ReceiveMessagesRequest(username="recipient"))
        self.assertIn("success", response.status)
        self.assertEqual(len(response.messages), 1)
        self.assertEqual(response.messages[0].id, "1")

    def test_handle_receive_messages_account_not_found(self):
        """
        Test retrieving messages for a non-existent user.
        Verifies that the server returns an error status and an empty message list.
        """
        response = self.stub.ReceiveMessages(chat_pb2.ReceiveMessagesRequest(username="nonexistent"))
        self.assertIn("error: User not found", response.status)
        self.assertEqual(len(response.messages), 0)

    # -------------------------------------------------------------------------
    # 9. Delete Account Tests
    # -------------------------------------------------------------------------
    def test_handle_delete_account_success(self):
        """
        Test successfully deleting an account.
        Verifies that the user is marked as deleted.
        """
        server.users["testuser"] = {"password": "p", "messages": []}
        response = self.stub.DeleteAccount(chat_pb2.DeleteAccountRequest(username="testuser"))
        self.assertIn("success", response.message)
        self.assertTrue(server.users["testuser"].get("deleted", False))

    def test_handle_delete_account_nonexistent(self):
        """
        Test attempting to delete a non-existent account.
        Verifies that an error message is returned.
        """
        response = self.stub.DeleteAccount(chat_pb2.DeleteAccountRequest(username="unknown"))
        self.assertIn("error: User not found", response.message)

    def test_handle_delete_account_already_deleted(self):
        """
        Test attempting to delete an account that is already deleted.
        Verifies that an error message is returned.
        """
        server.users["testuser"] = {"password": "p", "messages": [], "deleted": True}
        response = self.stub.DeleteAccount(chat_pb2.DeleteAccountRequest(username="testuser"))
        self.assertIn("error: User not found or already deleted", response.message)

    # -------------------------------------------------------------------------
    # 10. Logout Tests
    # -------------------------------------------------------------------------
    def test_handle_logout_success(self):
        """
        Test successful logout.
        Verifies that an active user is logged out and removed from the active users set.
        """
        server.users["testuser"] = {"password": "p", "messages": []}
        server.active_users.add("testuser")
        response = self.stub.Logout(chat_pb2.LogoutRequest(username="testuser"))
        self.assertIn("success: Logged out", response.message)
        self.assertNotIn("testuser", server.active_users)

    def test_handle_logout_non_active_user(self):
        """
        Test logout for a non-active user.
        Verifies that the server returns an error indicating the user was not active.
        """
        server.users["testuser"] = {"password": "p", "messages": []}
        response = self.stub.Logout(chat_pb2.LogoutRequest(username="testuser"))
        self.assertIn("error: Failed to log out. User not active.", response.message)

    # -------------------------------------------------------------------------
    # Subscription (Streaming) Test (Test passes but prevents pytest from exiting, so commented until needed)
    # -------------------------------------------------------------------------
    # def test_handle_subscribe_and_receive_stream(self):
    #     """
    #     Test subscription streaming.
    #     Verifies that when a user subscribes, they receive the expected message.
    #     Note: This test may prevent pytest from exiting cleanly if the streaming call is not canceled.
    #     """
    #     self.stub.Register(chat_pb2.RegisterRequest(username="alice", password="p"))
    #     received_event = threading.Event()
    #     def subscription_reader(stub, messages_received, event):
    #         stream = stub.Subscribe(chat_pb2.SubscribeRequest(username="alice"))
    #         for msg in stream:
    #             messages_received.append(msg)
    #             event.set() 
    #             break
    #     messages = []
    #     t = threading.Thread(target=subscription_reader, args=(self.stub, messages, received_event), daemon=True)
    #     t.start()
    #     time.sleep(0.5)
    #     self.stub.Register(chat_pb2.RegisterRequest(username="bob", password="p"))
    #     self.stub.SendMessage(chat_pb2.SendMessageRequest(
    #         sender="bob", recipient="alice", message="Hello from Bob"
    #     ))
    #     received_event.wait(timeout=2)
    #     self.assertEqual(len(messages), 1)
    #     self.assertEqual(messages[0].sender, "bob")
    #     self.assertEqual(messages[0].message, "Hello from Bob")
    #     self.assertEqual(messages[0].status, "unread")


if __name__ == "__main__":
    unittest.main()

