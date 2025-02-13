import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from server import ChatServer
from chat_ui import hash_password

class TestServerHandlers(unittest.TestCase):

    def setUp(self):
        """Reset the user store before each test."""
        # Use a fresh UserStore (this writes to users.json but tests run sequentially)
        self.chat_server = ChatServer()
        self.chat_server.store.users.clear()
        self.chat_server.active_users.clear()
        self.chat_server.subscribers.clear()

    def test_handle_register_success(self):
        response, _ = self.chat_server.handle_register(
            {"username": "testuser", "password": "password123"}, None)
        self.assertEqual(response, {"status": "success", "message": "Account created."})
        self.assertIn("testuser", self.chat_server.store.users)

    def test_handle_register_duplicate(self):
        self.chat_server.store.users["testuser"] = {
            "password": hash_password("password123"), "messages": []}
        response, _ = self.chat_server.handle_register(
            {"username": "testuser", "password": "password123"}, None)
        self.assertEqual(response, {"status": "error", "message": "Username already exists."})

    def test_handle_login_success(self):
        self.chat_server.store.users["testuser"] = {
            "password": hash_password("password123"), "messages": []}
        response, _ = self.chat_server.handle_login(
            {"username": "testuser", "password": hash_password("password123")}, None)
        self.assertEqual(response["status"], "success")
        self.assertIn("Logged in", response["message"])
        self.assertIn("testuser", self.chat_server.active_users)

    def test_handle_login_already_logged_in(self):
        self.chat_server.store.users["testuser"] = {
            "password": hash_password("password123"), "messages": []}
        self.chat_server.active_users.add("testuser")
        response, _ = self.chat_server.handle_login(
            {"username": "testuser", "password": hash_password("password123")}, None)
        self.assertEqual(response, {"status": "error", "message": "User already logged in."})
        self.assertEqual(self.chat_server.active_users, {"testuser"})

    def test_handle_login_invalid_password(self):
        self.chat_server.store.users["testuser"] = {
            "password": hash_password("password123"), "messages": []}
        response, _ = self.chat_server.handle_login(
            {"username": "testuser", "password": hash_password("wrongpassword")}, None)
        self.assertEqual(response, {"status": "error", "message": "Invalid credentials or account deleted."})
        self.assertEqual(self.chat_server.active_users, set())

    def test_handle_list_users(self):
        self.chat_server.store.users["user1"] = {"password": hash_password("pass1"), "messages": []}
        self.chat_server.store.users["user2"] = {"password": hash_password("pass2"), "messages": []}
        self.chat_server.store.users["user3"] = {"password": hash_password("pass3"), "messages": [], "deleted": True}
        response, _ = self.chat_server.handle_list_users({"prefix": "*"}, None)
        # Order may vary; so we compare sets.
        self.assertEqual(set(response["users"]), set(["user1", "user2"]))
        self.assertEqual(response["status"], "success")

    def test_handle_send_success(self):
        self.chat_server.store.users["sender"] = {"password": hash_password("pass"), "messages": []}
        self.chat_server.store.users["recipient"] = {"password": hash_password("pass"), "messages": []}
        response, _ = self.chat_server.handle_send(
            {"sender": "sender", "recipient": "recipient", "message": "Hello"}, None)
        self.assertEqual(response["status"], "success")
        self.assertTrue(response["message"].startswith("Message sent"))

    def test_handle_send_nonexistent_recipient(self):
        self.chat_server.store.users["sender"] = {"password": hash_password("pass"), "messages": []}
        response, _ = self.chat_server.handle_send(
            {"sender": "sender", "recipient": "recipient", "message": "Hello"}, None)
        self.assertEqual(response, {"status": "error", "message": "Recipient not found."})

    def test_handle_send_deleted_recipient(self):
        self.chat_server.store.users["sender"] = {"password": hash_password("pass"), "messages": []}
        self.chat_server.store.users["recipient"] = {"password": hash_password("pass"), "messages": [], "deleted": True}
        response, _ = self.chat_server.handle_send(
            {"sender": "sender", "recipient": "recipient", "message": "Hello"}, None)
        self.assertEqual(response, {"status": "error", "message": "User no longer exists."})

    def test_mark_all_messages_as_read(self):
        """
        Assume that a read_batch_num of 0 means “mark all” unread messages.
        """
        self.chat_server.store.users = {
            "contact1": {
                "messages": [
                    {"from": "contact1", "status": "unread"},
                    {"from": "contact2", "status": "unread"},
                    {"from": "contact2", "status": "unread"},
                    {"from": "contact1", "status": "unread"},
                ]
            }
        }
        # Expected: messages from contact2 (there are 2) are marked as read.
        response, _ = self.chat_server.handle_mark_read(
            {"username": "contact1", "contact": "contact2", "read_batch_num": 0}, None)
        self.assertEqual(response, {"status": "success", "message": "2 messages marked as read."})
        self.assertEqual(self.chat_server.store.users["contact1"]["messages"][0]["status"], "unread")
        self.assertEqual(self.chat_server.store.users["contact1"]["messages"][1]["status"], "read")
        self.assertEqual(self.chat_server.store.users["contact1"]["messages"][2]["status"], "read")
        self.assertEqual(self.chat_server.store.users["contact1"]["messages"][3]["status"], "unread")

    def test_mark_specific_number_of_messages(self):
        self.chat_server.store.users = {
            "contact1": {
                "messages": [
                    {"from": "contact1", "status": "unread"},
                    {"from": "contact2", "status": "unread"},
                    {"from": "contact2", "status": "unread"},
                    {"from": "contact2", "status": "unread"},
                    {"from": "contact1", "status": "unread"},
                ]
            }
        }
        response, _ = self.chat_server.handle_mark_read(
            {"username": "contact1", "contact": "contact2", "read_batch_num": 2}, None)
        self.assertEqual(response, {"status": "success", "message": "2 messages marked as read."})
        self.assertEqual(self.chat_server.store.users["contact1"]["messages"][0]["status"], "unread")
        self.assertEqual(self.chat_server.store.users["contact1"]["messages"][1]["status"], "read")
        self.assertEqual(self.chat_server.store.users["contact1"]["messages"][2]["status"], "read")
        self.assertEqual(self.chat_server.store.users["contact1"]["messages"][3]["status"], "unread")
        self.assertEqual(self.chat_server.store.users["contact1"]["messages"][4]["status"], "unread")

    def test_user_not_found(self):
        self.chat_server.store.users = {
            "contact1": {
                "messages": [
                    {"from": "contact1", "status": "unread"},
                    {"from": "contact2", "status": "unread"},
                    {"from": "contact2", "status": "unread"},
                    {"from": "contact1", "status": "unread"},
                ]
            }
        }
        response, _ = self.chat_server.handle_mark_read(
            {"username": "nonexistent", "contact": "contact1", "read_batch_num": 0}, None)
        self.assertEqual(response, {"status": "error", "message": "User not found."})

    def test_no_unread_messages(self):
        self.chat_server.store.users = {
            "contact1": {
                "messages": [
                    {"from": "contact1", "status": "unread"},
                    {"from": "contact2", "status": "read"},
                    {"from": "contact2", "status": "read"},
                    {"from": "contact1", "status": "unread"},
                ]
            }
        }
        response, _ = self.chat_server.handle_mark_read(
            {"username": "contact1", "contact": "contact2", "read_batch_num": 0}, None)
        self.assertEqual(response, {"status": "error", "message": "No unread messages."})
    
    def test_no_messages_from_contact(self):
        self.chat_server.store.users = {
            "contact1": {
                "messages": [
                    {"from": "contact1", "status": "unread"},
                    {"from": "contact1", "status": "unread"},
                ]
            }
        }
        response, _ = self.chat_server.handle_mark_read(
            {"username": "contact1", "contact": "contact2", "read_batch_num": 0}, None)
        self.assertEqual(response, {"status": "error", "message": "No unread messages."})
    
    def test_handle_delete_unread_message_success(self):
        self.chat_server.store.users["recipient"] = {
            "password": hash_password("pass"),
            "messages": [{"id": "123", "from": "sender", "message": "Hello", "status": "unread"}]
        }
        response, _ = self.chat_server.handle_delete(
            {"sender": "sender", "recipient": "recipient", "message_id": "123"}, None)
        self.assertEqual(response, {"status": "success", "message": "Message deleted."})
    
    def test_handle_delete_unread_message_not_found(self):
        self.chat_server.store.users["recipient"] = {"password": hash_password("pass"), "messages": []}
        response, _ = self.chat_server.handle_delete(
            {"sender": "sender", "recipient": "recipient", "message_id": "999"}, None)
        self.assertEqual(response, {"status": "error", "message": "Message not found or already read."})
    
    def test_handle_delete_unread_message_already_read(self):
        self.chat_server.store.users["recipient"] = {
            "password": hash_password("pass"),
            "messages": [{"id": "123", "from": "sender", "message": "Hello", "status": "read"}]
        }
        response, _ = self.chat_server.handle_delete(
            {"sender": "sender", "recipient": "recipient", "message_id": "123"}, None)
        self.assertEqual(response, {"status": "error", "message": "Message not found or already read."})
    
    def test_handle_delete_unread_message_recipient_not_found(self):
        self.chat_server.store.users["recipient1"] = {"password": hash_password("pass"), "messages": []}
        response, _ = self.chat_server.handle_delete(
            {"sender": "sender", "recipient": "recipient", "message_id": "123"}, None)
        self.assertEqual(response, {"status": "error", "message": "Recipient not found."})
    
    def test_handle_receive_messages_success(self):
        self.chat_server.store.users["recipient"] = {
            "password": hash_password("pass"),
            "messages": [{"id": "123", "from": "sender", "message": "Hello", "status": "read"}]
        }
        response, _ = self.chat_server.handle_receive({"username": "recipient"}, None)
        self.assertEqual(response, {"status": "success", "messages": [{"id": "123", "from": "sender", "message": "Hello", "status": "read"}]})
    
    def test_handle_receive_messages_account_not_found(self):
        self.chat_server.store.users["recipient"] = {
            "password": hash_password("pass"),
            "messages": [{"id": "123", "from": "sender", "message": "Hello", "status": "read"}]
        }
        response, _ = self.chat_server.handle_receive({"username": "recipient1"}, None)
        self.assertEqual(response, {"status": "error", "message": "User not found."})
    
    def test_handle_delete_account_success(self):
        self.chat_server.store.users["testuser"] = {"password": hash_password("pass"), "messages": []}
        response, _ = self.chat_server.handle_delete_account({"username": "testuser"}, None)
        self.assertEqual(response, {"status": "success", "message": "Account deleted."})
        self.assertTrue(self.chat_server.store.users["testuser"].get("deleted", False))
    
    def test_handle_delete_account_nonexistent(self):
        response, _ = self.chat_server.handle_delete_account({"username": "unknown"}, None)
        self.assertEqual(response, {"status": "error", "message": "User not found or already deleted."})
    
    def test_handle_delete_account_already_deleted(self):
        self.chat_server.store.users["testuser"] = {"password": hash_password("pass"), "messages": [], "deleted": True}
        response, _ = self.chat_server.handle_delete_account({"username": "testuser"}, None)
        self.assertEqual(response, {"status": "error", "message": "User not found or already deleted."})
        self.assertTrue(self.chat_server.store.users["testuser"].get("deleted", False))
    
    def test_handle_logout_success(self):
        self.chat_server.active_users = {"testuser"}
        response, _ = self.chat_server.handle_logout({"username": "testuser"}, None)
        self.assertEqual(response, {"status": "success", "message": "Logged out."})
        self.assertEqual(self.chat_server.active_users, set())
    
    def test_handle_logout_error(self):
        # In this implementation, logging out a non–active user simply discards nothing.
        self.chat_server.active_users = {"testuser1"}
        response, _ = self.chat_server.handle_logout({"username": "testuser"}, None)
        self.assertEqual(response, {"status": "success", "message": "Logged out."})
        self.assertEqual(self.chat_server.active_users, {"testuser1"})
        
if __name__ == '__main__':
    unittest.main()
