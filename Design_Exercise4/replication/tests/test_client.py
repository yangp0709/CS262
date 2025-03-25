import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import grpc
import tkinter as tk

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import client
import chat_pb2

class TestClient(unittest.TestCase):
    def setUp(self):
        """
        Reset global variables before each test to ensure a clean state.
        """
        client.current_user = None
        client.conversations = {}
        client.chat_windows = {}
        client.undelivered = {}
        client.subscription_active = False

    def test_add_message(self):
        """
        Test that add_message correctly adds a new message and updates an existing message.
        """
        contact = "test_user"
        msg = {"id": 1, "from": "test_user", "message": "Hello!", "status": "unread"}
        # Add a new message
        client.add_message(contact, msg)
        self.assertEqual(len(client.conversations[contact]), 1)
        self.assertEqual(client.conversations[contact][0], msg)

        # Update the same message (same id)
        updated_msg = {"id": 1, "from": "test_user", "message": "Hello, World!", "status": "read"}
        client.add_message(contact, updated_msg)
        self.assertEqual(client.conversations[contact][0], updated_msg)

    @patch('client.stub')
    def test_check_version_number_success(self, mock_stub):
        """
        Test check_version_number when the version matches successfully.
        """
        # Create a fake response indicating a version match
        fake_response = MagicMock()
        fake_response.success = True
        fake_response.message = "Version matched"
        mock_stub.CheckVersion.return_value = fake_response

        result = client.check_version_number()
        self.assertTrue(result)
        mock_stub.CheckVersion.assert_called_once_with(chat_pb2.Version(version=client.CLIENT_VERSION))

    @patch('client.stub')
    def test_check_version_number_mismatch(self, mock_stub):
        """
        Test check_version_number when the version does not match.
        """
        # Simulate a response with a version mismatch
        fake_response = MagicMock()
        fake_response.success = False
        fake_response.message = "Version mismatch"
        mock_stub.CheckVersion.return_value = fake_response

        result = client.check_version_number()
        self.assertIsNone(result)
        mock_stub.CheckVersion.assert_called_once_with(chat_pb2.Version(version=client.CLIENT_VERSION))

    @patch('client.stub')
    def test_check_version_number_exception(self, mock_stub):
        """
        Test check_version_number when a gRPC exception occurs.
        A custom FakeRpcError is used to simulate a gRPC exception that implements details().
        """
        class FakeRpcError(grpc.RpcError):
            def details(self):
                return "RPC Error occurred"

        fake_exception = FakeRpcError()
        mock_stub.CheckVersion.side_effect = fake_exception

        result = client.check_version_number()
        self.assertIsNone(result)
        mock_stub.CheckVersion.assert_called_once_with(chat_pb2.Version(version=client.CLIENT_VERSION))

    @patch('client.stub')
    @patch('client.conversation_list')
    @patch('client.messagebox.showerror')
    def test_load_conversations_success(self, mock_showerror, mock_conversation_list, mock_stub):
        """
        Test load_conversations when messages are successfully received from the server.
        It verifies that messages are properly added to the conversation list.
        """
        fake_msg1 = MagicMock()
        fake_msg1.id = 1
        fake_msg1.sender = "user1"
        fake_msg1.message = "Hello"
        fake_msg1.status = "unread"

        fake_msg2 = MagicMock()
        fake_msg2.id = 2
        fake_msg2.sender = "user2"
        fake_msg2.message = "Hi"
        fake_msg2.status = "read"

        fake_response = MagicMock()
        fake_response.status = "success"
        fake_response.messages = [fake_msg1, fake_msg2]
        mock_stub.ReceiveMessages.return_value = fake_response

        client.current_user = "test_user"
        client.conversations = {}
        client.load_conversations()

        # Check that messages are added to conversations for both senders
        self.assertIn("user1", client.conversations)
        self.assertIn("user2", client.conversations)
        self.assertEqual(client.conversations["user1"][0]["message"], "Hello")
        self.assertEqual(client.conversations["user2"][0]["message"], "Hi")
        mock_stub.ReceiveMessages.assert_called_once_with(chat_pb2.ReceiveMessagesRequest(username="test_user"))

    @patch('client.stub')
    @patch('client.messagebox.showerror')
    def test_load_conversations_failure(self, mock_showerror, mock_stub):
        """
        Test load_conversations when the server response indicates an error.
        It checks that an error message is displayed via messagebox.
        """
        fake_response = MagicMock()
        fake_response.status = "error"
        fake_response.messages = []
        mock_stub.ReceiveMessages.return_value = fake_response

        client.current_user = "test_user"
        client.conversations = {}
        client.load_conversations()

        mock_stub.ReceiveMessages.assert_called_once_with(chat_pb2.ReceiveMessagesRequest(username="test_user"))
        mock_showerror.assert_called_once()

    @patch('client.conversation_list')
    def test_update_conversation_list_empty(self, mock_conversation_list):
        """
        Test update_conversation_list when there are no conversations.
        The conversation list should be cleared and no new entries inserted.
        """
        mock_conversation_list.delete = MagicMock()
        mock_conversation_list.insert = MagicMock()

        client.conversations = {}
        client.update_conversation_list()
        mock_conversation_list.delete.assert_called_once_with(0, tk.END)
        mock_conversation_list.insert.assert_not_called()

    @patch('client.conversation_list')
    def test_update_conversation_list_unread(self, mock_conversation_list):
        """
        Test update_conversation_list when there are unread messages.
        The unread count should be correctly appended to the contact's display.
        """
        mock_conversation_list.delete = MagicMock()
        mock_conversation_list.insert = MagicMock()

        client.conversations = {
            "user1": [{"from": "user1", "status": "unread", "message": "Hello!"}],
            "user2": [{"from": "user2", "status": "read", "message": "Hi!"}]
        }
        client.update_conversation_list()

        mock_conversation_list.delete.assert_called_once_with(0, tk.END)
        calls = mock_conversation_list.insert.call_args_list
        # Verify that the unread indicator is added for user1 and user2 is inserted without it
        self.assertIn("🔴(1 unread)", calls[0][0][1])
        self.assertEqual(calls[1][0][1], "user2")

    @patch('client.conversation_list')
    def test_update_conversation_list_no_unread(self, mock_conversation_list):
        """
        Test update_conversation_list when all messages are read.
        No unread indicators should be present.
        """
        mock_conversation_list.delete = MagicMock()
        mock_conversation_list.insert = MagicMock()

        client.conversations = {
            "user1": [{"from": "user1", "status": "read", "message": "Hello!"}],
            "user2": [{"from": "user2", "status": "read", "message": "Hi!"}]
        }
        client.update_conversation_list()

        mock_conversation_list.delete.assert_called_once_with(0, tk.END)
        mock_conversation_list.insert.assert_any_call(tk.END, "user1")
        mock_conversation_list.insert.assert_any_call(tk.END, "user2")

    @patch('client.stub')
    @patch('client.conversation_list')
    def test_update_chat_window_unread_messages_marked_as_read(self, mock_conversation_list, mock_stub):
        """
        Test update_chat_window to ensure that unread messages are marked as read.
        It verifies that stub.MarkRead is called and the message statuses are updated.
        """
        # Create a fake chat window that exists
        fake_window = MagicMock()
        fake_window.winfo_exists.return_value = True
        fake_window.refresh_chat_text = MagicMock()
        client.chat_windows = {"test_user": fake_window}
        client.conversations = {"test_user": [{"from": "test_user", "status": "unread", "message": "Hello!", "id": 1}]}
        client.current_user = "current_user"
        client.update_chat_window("test_user")

        mock_stub.MarkRead.assert_called_once_with(chat_pb2.MarkReadRequest(username="current_user", contact="test_user", batch_num=0))
        for message in client.conversations["test_user"]:
            if message["from"] == "test_user":
                self.assertEqual(message["status"], "read")

    @patch('client.stub')
    @patch('client.conversation_list')
    def test_update_chat_window_all_read(self, mock_conversation_list, mock_stub):
        """
        Test update_chat_window when all messages are already read.
        It should not call stub.MarkRead again.
        """
        fake_window = MagicMock()
        fake_window.winfo_exists.return_value = True
        fake_window.refresh_chat_text = MagicMock()
        client.chat_windows = {"test_user": fake_window}
        client.conversations = {"test_user": [{"from": "test_user", "status": "read", "message": "Hello!", "id": 1}]}
        client.update_chat_window("test_user")
        mock_stub.MarkRead.assert_not_called()

    @patch('client.root.after')
    @patch('client.load_conversations')
    def test_check_new_messages(self, mock_load_conversations, mock_after):
        """
        Test check_new_messages to verify that it calls load_conversations
        and then schedules itself to run again after 5000ms.
        """
        client.current_user = "test_user"
        client.check_new_messages()
        mock_load_conversations.assert_called_once()
        mock_after.assert_called_once_with(5000, client.check_new_messages)

    @patch('client.stub')
    @patch('client.login_frame')
    @patch('client.chat_frame')
    @patch('client.conversation_list')
    @patch('client.messagebox.showerror')
    def test_logout_successful(self, mock_showerror, mock_conversation_list, mock_chat_frame, mock_login_frame, mock_stub):
        """
        Test logout for a successful logout scenario.
        Ensures that global variables are reset, chat windows are closed, and UI is updated.
        """
        fake_response = MagicMock()
        fake_response.message = "success: Logged out."
        mock_stub.Logout.return_value = fake_response

        client.current_user = "test_user"
        client.subscription_active = True

        mock_chat_frame.pack_forget = MagicMock()
        mock_login_frame.pack = MagicMock()
        mock_conversation_list.delete = MagicMock()
        client.conversations = {"user1": []}
        fake_window = MagicMock()
        fake_window.winfo_exists.return_value = True
        fake_window.destroy = MagicMock()
        client.chat_windows = {"user1": fake_window}
        client.undelivered = {"user1": "test"}

        client.logout()

        self.assertIsNone(client.current_user)
        self.assertFalse(client.subscription_active)
        for win in client.chat_windows.values():
            win.destroy.assert_called_once()
        self.assertEqual(client.conversations, {})
        mock_conversation_list.delete.assert_called_once_with(0, tk.END)
        mock_chat_frame.pack_forget.assert_called_once()
        mock_login_frame.pack.assert_called_once()

    @patch('client.stub')
    @patch('client.messagebox.showerror')
    def test_logout_failure(self, mock_showerror, mock_stub):
        """
        Test logout when the server returns an error message.
        It verifies that an error is displayed via messagebox.
        """
        fake_response = MagicMock()
        fake_response.message = "error: Failed to log out."
        mock_stub.Logout.return_value = fake_response

        client.current_user = "test_user"
        client.logout()
        mock_showerror.assert_called_once_with("Error", fake_response.message)

if __name__ == "__main__":
    unittest.main()