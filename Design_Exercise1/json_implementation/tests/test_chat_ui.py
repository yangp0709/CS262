import sys
import os
import json
import socket
import tkinter as tk
from tkinter import messagebox
from unittest.mock import MagicMock, patch
import unittest

# Add the parent directory so we can import chat_ui.py.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import chat_ui as client
sys.modules["client"] = client

class TestChatUI(unittest.TestCase):

    def test_add_message(self):
        """
        Test add_message function adds new and updates message.
        """
        contact = "test_user"
        msg = {"id": 1, "from": "test_user", "message": "Hello!", "status": "unread"}
        
        # test add new message
        client.add_message(contact, msg)
        self.assertEqual(len(client.conversations[contact]), 1)
        self.assertEqual(client.conversations[contact][0], msg)
        
        # test update message
        updated_msg = {"id": 1, "from": "test_user", "message": "Hello, World!", "status": "read"}
        client.add_message(contact, updated_msg)
        self.assertEqual(client.conversations[contact][0], updated_msg)
    
    @patch("socket.socket")
    def test_send_request_success(self, mock_socket):
        """
        Test send_request function during success.
        """
        mock_conn = MagicMock()
        mock_socket.return_value = mock_conn
        response_dict = {"status": "success", "data": "ok"}
        mock_conn.recv.return_value = json.dumps(response_dict).encode()
        
        request = {"type": "test", "data": "empty"}
        response = client.send_request(request)
        
        mock_socket.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)
        mock_conn.connect.assert_called_once_with((client.SERVER_HOST, client.SERVER_PORT))
        mock_conn.send.assert_called_once_with(json.dumps(request).encode())
        mock_conn.recv.assert_called_once()
        mock_conn.close.assert_called_once()
        self.assertEqual(response, response_dict)
    
    @patch("socket.socket")
    @patch("tkinter.messagebox.showerror")
    def test_send_request_connect_error(self, mock_showerror, mock_socket):
        """
        Test send_request when connection fails.
        """
        mock_conn = MagicMock()
        mock_socket.return_value = mock_conn
        mock_conn.connect.side_effect = Exception("Connection failed")
        
        request = {"type": "test", "data": "Test Data"}
        response = client.send_request(request)
        
        mock_conn.connect.assert_called_once_with((client.SERVER_HOST, client.SERVER_PORT))
        mock_conn.send.assert_not_called()
        mock_conn.close.assert_not_called()
        mock_showerror.assert_called_once()
        self.assertIsNone(response)
    
    @patch("socket.socket")
    @patch("tkinter.messagebox.showerror")
    def test_send_request_send_error(self, mock_showerror, mock_socket):
        """
        Test send_request when sending fails.
        """
        mock_conn = MagicMock()
        mock_socket.return_value = mock_conn
        mock_conn.send.side_effect = Exception("Send failed")
        
        request = {"type": "test", "data": "Test Data"}
        response = client.send_request(request)
        
        mock_conn.connect.assert_called_once_with((client.SERVER_HOST, client.SERVER_PORT))
        mock_conn.send.assert_called_once()
        mock_conn.close.assert_not_called()
        mock_showerror.assert_called_once()
        self.assertIsNone(response)
    
    @patch("socket.socket")
    @patch("tkinter.messagebox.showerror")
    def test_send_request_close_error(self, mock_showerror, mock_socket):
        """
        Test send_request when closing the socket fails.
        """
        mock_conn = MagicMock()
        mock_socket.return_value = mock_conn
        response_dict = {"status": "success", "data": "ok"}
        mock_conn.recv.return_value = json.dumps(response_dict).encode()
        mock_conn.close.side_effect = Exception("Close failed")
        
        request = {"type": "test", "data": "Test Data"}
        response = client.send_request(request)
        
        mock_conn.connect.assert_called_once_with((client.SERVER_HOST, client.SERVER_PORT))
        mock_conn.send.assert_called_once_with(json.dumps(request).encode())
        mock_conn.recv.assert_called_once()
        mock_conn.close.assert_called_once()
        mock_showerror.assert_called_once()
        self.assertIsNone(response)
    
    @patch('client.send_request')
    @patch('client.add_message')
    @patch('client.update_conversation_list')
    @patch('tkinter.messagebox.showerror')
    def test_load_conversations_success(self, mock_showerror, mock_update_conversation_list, mock_add_message, mock_send_request):
        """
        Test load_conversations when server returns messages.
        """
        mock_send_request.return_value = {"status": "success", "messages": [
            {'from': 'user1', 'message': 'Hello'},
            {'from': 'user2', 'message': 'Hi'}
        ]}
        client.current_user = "test_user"
        client.load_conversations()
        mock_send_request.assert_called_once_with({"type": "receive", "username": client.current_user})
        mock_add_message.assert_any_call('user1', {'from': 'user1', 'message': 'Hello'})
        mock_add_message.assert_any_call('user2', {'from': 'user2', 'message': 'Hi'})
        mock_update_conversation_list.assert_called_once()
        mock_showerror.assert_not_called()
    
    @patch('client.send_request')
    @patch('client.add_message')
    @patch('client.update_conversation_list')
    @patch('tkinter.messagebox.showerror')
    def test_load_conversations_no_messages(self, mock_showerror, mock_update_conversation_list, mock_add_message, mock_send_request):
        """
        Test load_conversations when server returns an error.
        """
        mock_send_request.return_value = {"status": "error", "message": "User not found."}
        client.current_user = "test_user"
        client.load_conversations()
        mock_send_request.assert_called_once_with({"type": "receive", "username": client.current_user})
        mock_add_message.assert_not_called()
        mock_update_conversation_list.assert_not_called()
        mock_showerror.assert_called_once()
    
    @patch('client.conversation_list')
    def test_update_conversation_list_empty(self, mock_conversation_list):
        """
        Test update_conversation_list with no conversations.
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
        Test update_conversation_list shows unread indicator.
        """
        mock_conversation_list.delete = MagicMock()
        mock_conversation_list.insert = MagicMock()
        client.conversations = {
            "user1": [{"from": "user1", "status": "unread", "message": "Hello!"}],
            "user2": [{"from": "user2", "status": "read", "message": "Hi!"}]
        }
        client.update_conversation_list()
        mock_conversation_list.delete.assert_called_once_with(0, tk.END)
        mock_conversation_list.insert.assert_any_call(tk.END, "user1 🔴(1 unread)")
        mock_conversation_list.insert.assert_any_call(tk.END, "user2")
    
    @patch('client.conversation_list')
    def test_update_conversation_list_no_unread(self, mock_conversation_list):
        """
        Test update_conversation_list when there are no unread messages.
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
    
    @patch('client.send_request')
    @patch('client.update_conversation_list')
    def test_update_chat_window_unread_messages_marked_as_read(self, mock_update_conversation_list, mock_send_request):
        """
        Test update_chat_window marks unread messages as read.
        """
        mock_chat_window = MagicMock()
        mock_chat_window.winfo_exists.return_value = True
        mock_chat_window.refresh_chat_text.return_value = True
        client.chat_windows = {"test_user": mock_chat_window}
        client.conversations = {"test_user": [{"from": "test_user", "status": "unread", "message": "Hello!", "id": 1}]}
        client.current_user = "current_user"
        client.update_chat_window("test_user")
        for message in client.conversations["test_user"]:
            if message["from"] == "test_user":
                self.assertEqual(message["status"], "read")
        mock_send_request.assert_called_once_with({"type": "mark_read", "username": client.current_user, "contact": "test_user"})
        mock_update_conversation_list.assert_called_once()
    
    @patch('client.send_request')
    @patch('client.update_conversation_list')
    def test_update_chat_window_with_all_read_messages(self, mock_update_conversation_list, mock_send_request):
        """
        Test update_chat_window does not call mark_read when all messages are read.
        """
        mock_chat_window = MagicMock()
        mock_chat_window.winfo_exists.return_value = True
        mock_chat_window.refresh_chat_text.return_value = True
        client.chat_windows = {"test_user": mock_chat_window}
        client.conversations = {"test_user": [{"from": "test_user", "status": "read", "message": "Hello!", "id": 1}]}
        client.update_chat_window("test_user")
        mock_send_request.assert_not_called()
        mock_update_conversation_list.assert_not_called()
    
    @patch('client.root.after')
    @patch('client.load_conversations')
    def test_check_new_messages(self, mock_load_conversations, mock_after):
        """
        Test check_new_messages calls load_conversations and reschedules itself.
        """
        client.current_user = "test_user"
        client.check_new_messages()
        mock_load_conversations.assert_called_once()
        mock_after.assert_called_once_with(5000, client.check_new_messages)
    @patch('client.load_all_usernames', lambda: None)
    @patch('client.send_request')
    def test_logout_successful(self, mock_send_request):
        """
        Test logout function when logout succeeds.
        """
        client.current_user = "test_user"
        mock_socket = MagicMock()
        client.subscription_socket = mock_socket
        mock_send_request.return_value = {"status": "success", "message": "Logged out."}
        client.unsent_texts = {"dummy": "data"}
        client.chat_frame = MagicMock()
        client.login_frame = MagicMock()
        client.new_conversation_entry = MagicMock()
        
        client.logout()
        
        self.assertIsNone(client.current_user)
        mock_socket.close.assert_called_once()
        self.assertIsNone(client.subscription_socket)
        client.chat_frame.pack_forget.assert_called_once()
        client.login_frame.pack.assert_called_once()
        self.assertEqual(client.recipient_var.get(), "")
        self.assertEqual(client.unsent_texts, {})
    
    @patch('client.load_all_usernames', lambda: None)
    @patch('client.send_request')
    def test_logout_socket_error(self, mock_send_request):
        """
        Test logout when closing the socket raises an exception.
        """
        client.current_user = "test_user"
        mock_socket = MagicMock()
        client.subscription_socket = mock_socket
        mock_send_request.return_value = {"status": "success", "message": "Logged out."}
        client.unsent_texts = {"dummy": "data"}
        client.chat_frame = MagicMock()
        client.login_frame = MagicMock()
        client.new_conversation_entry = MagicMock()
        mock_socket.close.side_effect = Exception("Failed to close socket")
        
        client.logout()
        
        self.assertIsNone(client.current_user)
        mock_socket.close.assert_called_once()
        self.assertIsNone(client.subscription_socket)
        client.chat_frame.pack_forget.assert_called_once()
        client.login_frame.pack.assert_called_once()
        self.assertEqual(client.recipient_var.get(), "")
        self.assertEqual(client.unsent_texts, {})
    
    @patch('client.send_request')
    def test_logout_request_error1(self, mock_send_request):
        """
        Test logout when send_request returns None.
        """
        client.current_user = "test_user"
        mock_socket = MagicMock()
        client.subscription_socket = mock_socket
        mock_send_request.return_value = None
        client.unsent_texts = {}
        result = client.logout()
        self.assertIsNone(result)
    
    @patch('client.send_request')
    def test_logout_request_error2(self, mock_send_request):
        """
        Test logout when send_request returns an error response.
        """
        client.current_user = "test_user"
        mock_socket = MagicMock()
        client.subscription_socket = mock_socket
        mock_send_request.return_value = {"status": "error", "message": "Failed to log out. Username does not exist in active users."}
        client.unsent_texts = {}
        result = client.logout()
        self.assertIsNone(result)

if __name__ == "__main__":
    unittest.main()
