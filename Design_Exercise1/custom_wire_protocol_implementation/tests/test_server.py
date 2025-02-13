import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import unittest
import threading
import server  # Import your server module

class TestServerHandlers(unittest.TestCase):

    def setUp(self):
        """
        Reset user database before each test
        """
        server.users.clear()
        server.subscribers.clear()

    def test_handle_register_success(self):
        """
        Test handle_register for successful case
        """
        response = server.handle_register("testuser|password123")
        self.assertEqual(response, "success: Account created")
        self.assertIn("testuser", server.users)

    def test_handle_register_duplicate(self):
        """
        Test handle_register for when username already exists
        """
        server.users["testuser"] = {"password": "password123", "messages": []}
        response = server.handle_register("testuser|password123")
        self.assertEqual(response, "error: This username is unavailable")

    def test_handle_login_success(self):
        """
        Test handle_login for successful case
        """
        server.users["testuser"] = {"password": "password123", "messages": []}
        server.active_users = set(["testuser1"])
        server.active_users_lock = threading.Lock()
        response = server.handle_login("testuser|password123")
        self.assertIn("success: Logged in", response)
        self.assertEqual(server.active_users, set(["testuser1", "testuser"]))

    def test_handle_login_already_logged_in(self):
        """
        Test handle_login for user who's already logged in
        """
        server.users["testuser"] = {"password": "password123", "messages": []}
        server.active_users = set(["testuser"])
        server.active_users_lock = threading.Lock()
        response = server.handle_login("testuser|password123")
        self.assertEqual("error: User already logged in", response)
        self.assertEqual(server.active_users, set(["testuser"]))

    def test_handle_login_invalid_password(self):
        """
        Test handle_login with invalid password
        """
        server.users["testuser"] = {"password": "password123", "messages": []}
        server.active_users = set(["testuser1"])
        server.active_users_lock = threading.Lock()
        response = server.handle_login("testuser|wrongpassword")
        self.assertEqual(response, "error: Invalid username or password")
        self.assertEqual(server.active_users, set(["testuser1"]))

    def test_handle_list_users(self):
        """
        Test handle_list_users
        """
        server.users["user1"] = {"password": "pass1", "messages": []}
        server.users["user2"] = {"password": "pass2", "messages": []}
        server.users["user3"] = {"password": "pass3", "messages": [], "deleted": True}
        response = server.handle_list_users()
        self.assertEqual(response, "['user1', 'user2']")

    def test_handle_send_success(self):
        """
        Test handle_send for a successful case
        """
        server.users["sender"] = {"password": "pass", "messages": []}
        server.users["recipient"] = {"password": "pass", "messages": []}
        response = server.handle_send("sender|recipient|Hello")
        self.assertTrue(response.startswith("success:"))

    def test_handle_send_nonexistent_recipient(self):
        """
        Test handle_send with nonexistent recipient
        """
        server.users["sender"] = {"password": "pass", "messages": []}
        response = server.handle_send("sender|recipient|Hello")
        self.assertEqual(response, "error: Recipient not found")

    def test_handle_send_deleted_recipient(self):
        """
        Test handle_send with deleted recipient
        """
        server.users["sender"] = {"password": "pass", "messages": []}
        server.users["recipient"] = {"password": "pass", "messages": [], "deleted": True}
        response = server.handle_send("sender|recipient|Hello")
        self.assertEqual(response, "error: User no longer exists.")

    def test_mark_all_messages_as_read(self):
        """
        Test handle_mark_read function where we mark all messages as read (read_batch_num = 0)
        """
        server.users = {
                    "contact1": {
                        "messages": [
                            {"from": "contact1", "status": "unread"},
                            {"from": "contact2", "status": "unread"},
                            {"from": "contact2", "status": "unread"},
                            {"from": "contact1", "status": "unread"},
                        ]
                    }
                }
        response = server.handle_mark_read("contact1|contact2|0")
        self.assertEqual(response, "success: Marked 2 messages as read.")
        self.assertEqual(server.users["contact1"]["messages"][0]["status"], "unread")
        self.assertEqual(server.users["contact1"]["messages"][1]["status"], "read")
        self.assertEqual(server.users["contact1"]["messages"][2]["status"], "read")
        self.assertEqual(server.users["contact1"]["messages"][3]["status"], "unread")

    def test_mark_specific_number_of_messages(self):
        """
        Test handle_mark_read function where we mark a specific number of messages as read
        """
        server.users = {
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
        response = server.handle_mark_read("contact1|contact2|2")
        self.assertEqual(response, "success: Marked 2 messages as read.")
        self.assertEqual(server.users["contact1"]["messages"][0]["status"], "unread")
        self.assertEqual(server.users["contact1"]["messages"][1]["status"], "read")
        self.assertEqual(server.users["contact1"]["messages"][2]["status"], "read")
        self.assertEqual(server.users["contact1"]["messages"][3]["status"], "unread")
        self.assertEqual(server.users["contact1"]["messages"][4]["status"], "unread")

    def test_user_not_found(self):
        """
        Test handle_mark_read function where we mark messages for a non-existent user
        """
        server.users = {
                    "contact1": {
                        "messages": [
                            {"from": "contact1", "status": "unread"},
                            {"from": "contact2", "status": "unread"},
                            {"from": "contact2", "status": "unread"},
                            {"from": "contact1", "status": "unread"},
                        ]
                    }
                }
        response = server.handle_mark_read("nonexistent|contact1|0")
        self.assertEqual(response, "error: User not found.")

    def test_no_unread_messages(self):
        """
        Test handle_mark_read function where there are no unread messages from the contact
        """
        server.users = {
                    "contact1": {
                        "messages": [
                            {"from": "contact1", "status": "unread"},
                            {"from": "contact2", "status": "read"},
                            {"from": "contact2", "status": "read"},
                            {"from": "contact1", "status": "unread"},
                        ]
                    }
                }
        response = server.handle_mark_read("contact1|contact2|0")
        self.assertEqual(response, "success: Marked 0 messages as read.")
        self.assertEqual(server.users["contact1"]["messages"][0]["status"], "unread")
        self.assertEqual(server.users["contact1"]["messages"][1]["status"], "read")
        self.assertEqual(server.users["contact1"]["messages"][2]["status"], "read")
        self.assertEqual(server.users["contact1"]["messages"][3]["status"], "unread")

    def test_no_messages_from_contact(self):
        """
        Test handle_mark_read function when there are no messages from the given contact
        """
        server.users = {
                    "contact1": {
                        "messages": [
                            {"from": "contact1", "status": "unread"},
                            {"from": "contact1", "status": "unread"},
                        ]
                    }
                }
        response = server.handle_mark_read("contact1|contact2|0")
        self.assertEqual(response, "success: Marked 0 messages as read.")
        self.assertEqual(server.users["contact1"]["messages"][0]["status"], "unread")
        self.assertEqual(server.users["contact1"]["messages"][1]["status"], "unread")


    def test_handle_delete_unread_message_success(self):
        """
        Test handle_delete_unread_message when it is success
        """
        server.users["recipient"] = {
            "password": "pass",
            "messages": [{"id": "123", "from": "sender", "message": "Hello", "status": "unread"}]
        }
        response = server.handle_delete_unread_message("sender|recipient|123")
        self.assertEqual(response, "success: Message deleted.")

    def test_handle_delete_unread_message_not_found(self):
        """
        Test handle_delete_unread_message when the message is not found
        """
        server.users["recipient"] = {"password": "pass", "messages": []}
        response = server.handle_delete_unread_message("sender|recipient|999")
        self.assertEqual(response, "error: Message not found or already read.")

    def test_handle_delete_unread_message_already_read(self):
        """
        Test handle_delete_unread_message when the message is already read
        """
        server.users["recipient"] = {"password": "pass", 
                                     "messages": [{"id": "123", "from": "sender", "message": "Hello", "status": "read"}]}
        response = server.handle_delete_unread_message("sender|recipient|123")
        self.assertEqual(response, "error: Message not found or already read.")

    def test_handle_delete_unread_message_recipient_not_found(self):
        """
        Test handle_delete_unread_message when recipient not found
        """
        server.users["recipient1"] = {"password": "pass", 
                                     "messages": []}
        response = server.handle_delete_unread_message("sender|recipient|123")
        self.assertEqual(response, "error: Recipient not found.")

    def test_handle_receive_messages_success(self):
        """
        Test handle_receive_messages when success
        """
        server.users["recipient"] = {"password": "pass", 
                                     "messages": [{"id": "123", "from": "sender", "message": "Hello", "status": "read"}]}
        
        response = server.handle_receive_messages("recipient")
        self.assertEqual(response, "success:[{'id': '123', 'from': 'sender', 'message': 'Hello', 'status': 'read'}]")

    def test_handle_receive_messages_account_not_found(self):
        """
        Test handle_receive_messages when account not found
        """
        server.users["recipient"] = {"password": "pass", 
                                     "messages": [{"id": "123", "from": "sender", "message": "Hello", "status": "read"}]}
        
        response = server.handle_receive_messages("recipient1")
        self.assertEqual(response, "error: User not found.")
    
    def test_handle_delete_account_success(self):
        """
        Test handle_delete_account when success
        """
        server.users["testuser"] = {"password": "pass", "messages": []}
        response = server.handle_delete_account("testuser")
        self.assertEqual(response, "success: Your account 'testuser' was deleted.")
        self.assertTrue(server.users["testuser"]["deleted"])

    def test_handle_delete_account_nonexistent(self):
        """
        Test handle_delete_account when account not found
        """
        response = server.handle_delete_account("unknown")
        self.assertEqual(response, "error: User not found or already deleted.")

    def test_handle_delete_account_success(self):
        """
        Test handle_delete_account when account is already deleted
        """
        server.users["testuser"] = {"password": "pass", "messages": [], "deleted": True}
        response = server.handle_delete_account("testuser")
        self.assertEqual(response, "error: User not found or already deleted.")
        self.assertTrue(server.users["testuser"]["deleted"])

    def test_handle_logout_success(self):
        """
        Test handle_logout function when success
        """
        server.active_users = set(["testuser"])
        server.active_users_lock = threading.Lock()
        response = server.handle_logout("testuser")
        self.assertEqual(response, "success: Logged out.")
        self.assertEqual(server.active_users, set())

    def test_handle_logout_error(self):
        """
        Test handle_logout function when error
        """
        server.active_users = set(["testuser1"])
        server.active_users_lock = threading.Lock()
        response = server.handle_logout("testuser")
        self.assertEqual(response, "error: Failed to log out. Username does not exist in active users.")
        self.assertEqual(server.active_users, set(["testuser1"]))
        
        
if __name__ == '__main__':
    unittest.main()
