import sys
import os
import tkinter as tk

# Add the 'client' directory to the system path so that we can import from it
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Now you can import from the client directory
import client  # Adjust based on what you need to test

# import pytest
# from unittest.mock import Mock


import unittest
from unittest.mock import MagicMock, patch
import socket
import struct

class TestSendRequest(unittest.TestCase):
    def test_add_message(self):
      """
      Test add_message function to add new and update message
      """

      contact = "test_user"
      msg = {"id": 1, "from": "test_user", "message": "Hello!", "status": "unread"}
      
      # test add new message
      client.add_message(contact, msg)
      assert len(client.conversations[contact]) == 1
      assert client.conversations[contact][0] == msg

      # test update message
      updated_msg = {"id": 1, "from": "test_user", "message": "Hello, World!", "status": "read"}
      client.add_message(contact, updated_msg)
      assert client.conversations[contact][0] == updated_msg
    
    @patch("socket.socket")
    # @patch("tkinter.messagebox")
    def test_send_request_success(self, mock_socket):
        """
        Test send_request function during succes
        """
        # Mock socket instance
        mock_conn = MagicMock()
        mock_socket.return_value = mock_conn
        
        # Simulated response from the server
        mock_conn.recv.return_value = b'response'
        
        # Call function
        request_type = 2
        data = "empty"
        message = struct.pack("!I", request_type) + data.encode()
        response = client.send_request(request_type, data)
        
        # Assertions
        mock_socket.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)
        mock_conn.connect.assert_called_once()
        mock_conn.send.assert_called_once_with(message)
        mock_conn.recv.assert_called_once()
        mock_conn.close.assert_called_once()
        self.assertEqual(response, 'response')
    
    @patch("socket.socket")
    def test_send_request_connect_error(self, mock_socket):
        """
        Test send_request function when client fails to connect
        """
        # Mock socket instance
        mock_conn = MagicMock()
        mock_socket.return_value = mock_conn
        
        # Simulate connection failure
        mock_conn.connect.side_effect = Exception("Connection failed")
        
        # Call the function
        response = client.send_request(1, "Test Data")
        
        # Assert that the function returns None (since the connection failed)
        self.assertIsNone(response)
        mock_conn.connect.assert_called_once()
        mock_conn.send.assert_not_called()
        mock_conn.close.assert_not_called()

    @patch("socket.socket")
    def test_send_request_send_error(self, mock_socket):
        """
        Test send_request function when client fails to connect
        """
        # Mock socket instance
        mock_conn = MagicMock()
        mock_socket.return_value = mock_conn
        
        # Simulate send failure
        mock_conn.send.side_effect = Exception("Send failed")
        
        # Call the function
        response = client.send_request(1, "Test Data")
        
        # Assert that the function returns None (since the connection failed)
        self.assertIsNone(response)
        mock_conn.connect.assert_called_once()
        mock_conn.send.assert_called_once()
        mock_conn.close.assert_not_called()

    @patch("socket.socket")
    def test_send_request_close_error(self, mock_socket):
        """
        Test send_request function when client fails to connect
        """
        # Mock socket instance
        mock_conn = MagicMock()
        mock_socket.return_value = mock_conn
        
        # Simulate socket close failure
        mock_conn.close.side_effect = Exception("Close failed")
        
        # Call the function
        response = client.send_request(1, "Test Data")
        
        # Assert that the function returns None (since the connection failed)
        self.assertIsNone(response)
        mock_conn.connect.assert_called_once()
        mock_conn.send.assert_called_once()
        mock_conn.close.assert_called_once()


    # GETS STUCK AT UPDATE_CHAT_WINDOW
    # @patch('socket.socket')  # Mock socket
    # @patch('client.add_message')  # Mock add_message
    # @patch('client.update_conversation_list')  # Mock update_conversation_list
    # @patch('client.update_chat_window')  # Mock update_chat_window
    # # @patch('client.send_request')
    # def test_successful_subscribe_thread(self, mock_update_chat_window, mock_update_conversation_list, mock_add_message, mock_socket):
    #     # Mock the socket connection
    #     client.current_user = "test_user"
    #     client.subscription_socket = MagicMock()
    #     mock_toplevel = MagicMock()
    #     mock_toplevel.winfo_exists.return_value = True
    #     mock_toplevel.refresh_chat_text = True
    #     client.chat_windows = {'test_user': mock_toplevel}
    #     mock_socket.return_value = client.subscription_socket
    #     # mock_send_request.return_value = True
        
    #     # Mock the response from the server
    #     client.subscription_socket.recv.return_value = b"success:{'id': 1, 'from': 'test_user', 'message': 'Hello!', 'stats': 'unread'}"  # Server response
    #     # mock_add_message.return_value = True  # Simulate add_message returning True
    #     mock_update_chat_window.return_value = True

    #     # Call the function
    #     client.subscribe_thread()

    #     # Ensure socket connection was made
    #     # mock_conn.connect.assert_called_once()
        
    #     # Ensure the correct message was sent
    #     request_type = 5
    #     data = client.current_user
    #     message = struct.pack("!I", request_type) + data.encode()
    #     client.subscription_socket.send.assert_called_once_with(message)

    #     # # Ensure the response was processed
    #     client.subscription_socket.recv.assert_called_once()

    #     mock_add_message.assert_called_once_with('test_user', {'id': 1, 'from': 'test_user', 'message': 'Hello!', 'stats': 'unread'})
    #     mock_update_conversation_list.assert_called_once()
    #     mock_update_chat_window.assert_called_once_with('test_user')

    @patch('client.send_request')  # Mock send_request to control the response
    @patch('client.add_message')  # Mock add_message to ensure it is called
    @patch('client.update_conversation_list')  # Mock update_conversation_list to ensure it is called
    @patch('client.messagebox.showerror')  # Mock showerror to ensure it is not called on success
    def test_load_conversations_success(self, mock_showerror, mock_update_conversation_list, mock_add_message, mock_send_request):
        """
        Test load_conversations function when it is a success
        """
        # Mock the send_request to return a successful response with valid messages
        mock_send_request.return_value = "success:[{'from': 'user1', 'message': 'Hello'}, {'from': 'user2', 'message': 'Hi'}]"

        # Call the function
        client.current_user = "test_user"
        client.load_conversations()

        # Ensure that send_request was called with the correct arguments
        mock_send_request.assert_called_once_with(8, "test_user")  # assuming current_user = "test_user"

        # Ensure add_message is called for each message
        mock_add_message.assert_any_call('user1', {'from': 'user1', 'message': 'Hello'})
        mock_add_message.assert_any_call('user2', {'from': 'user2', 'message': 'Hi'})

        # Ensure update_conversation_list is called
        mock_update_conversation_list.assert_called_once()

        # Ensure that messagebox.showerror is NOT called
        mock_showerror.assert_not_called()

    @patch('client.send_request')
    @patch('client.add_message')
    @patch('client.update_conversation_list')
    @patch('tkinter.messagebox.showerror')  # Patch tkinter's showerror
    def test_load_conversations_no_messages(self, mock_showerror, mock_update_conversation_list, mock_add_message, mock_send_request):
        """
        Test load_conversations function when there are no messages
        """
        # Mock the send_request to return a successful response with no messages
        mock_send_request.return_value = "error: User not found."

        # Call the function
        client.current_user = "test_user"
        client.load_conversations()

        # Ensure that send_request was called with the correct arguments
        mock_send_request.assert_called_once_with(8, "test_user")

        # Ensure that add_message was never called (no messages)
        mock_add_message.assert_not_called()

        # Ensure update_conversation_list is not called
        mock_update_conversation_list.assert_not_called()

        # Ensure that messagebox.showerror is called
        mock_showerror.assert_called_once()

    @patch('client.conversation_list')  # Mock conversation_list
    def test_update_conversation_list_empty(self, mock_conversation_list):
        """
        Test update_conversation_list when conversation is empty
        """
        # Mock the conversation_list widget's delete and insert methods
        mock_conversation_list.delete = MagicMock()
        mock_conversation_list.insert = MagicMock()

        # Call the function
        client.conversations = {}
        client.update_conversation_list()

        # Ensure the conversation_list.delete method was called to clear the list
        mock_conversation_list.delete.assert_called_once_with(0, tk.END)

        # Ensure that the insert method was never called, since there are no conversations
        mock_conversation_list.insert.assert_not_called()

    @patch('client.conversation_list')  # Mock conversation_list
    def test_update_conversation_list_unread(self, mock_conversation_list):
        """
        Test update_conversation_list when conversation has unread message
        """

        # Mock the conversation_list widget's delete and insert methods
        mock_conversation_list.delete = MagicMock()
        mock_conversation_list.insert = MagicMock()

        # Call the function
        client.conversations = {"user1": [{"from": "user1", "status": "unread", "message": "Hello!"}],
                                "user2": [{"from": "user2", "status": "read", "message": "Hi!"}]}
        client.update_conversation_list()

        # Ensure the conversation_list.delete method was called to clear the list
        mock_conversation_list.delete.assert_called_once_with(0, tk.END)

        # Ensure the insert method is called for each contact
        mock_conversation_list.insert.assert_any_call(tk.END, "user1 🔴(1 unread)")
        mock_conversation_list.insert.assert_any_call(tk.END, "user2")

        # Ensure that user1's conversation has the unread indicator
        self.assertTrue("🔴(1 unread)" in mock_conversation_list.insert.call_args_list[0][0][1])

    @patch('client.conversation_list')  # Mock conversation_list
    def test_update_conversation_list_no_unread(self, mock_conversation_list):
        """
        Test update_conversation_list when conversation has no unread message
        """
        
        # Mock the conversation_list widget's delete and insert methods
        mock_conversation_list.delete = MagicMock()
        mock_conversation_list.insert = MagicMock()

        # Call the function
        client.conversations = {"user1": [{"from": "user1", "status": "read", "message": "Hello!"}],
                                "user2": [{"from": "user2", "status": "read", "message": "Hi!"}]}
        client.update_conversation_list()

        # Ensure the conversation_list.delete method was called to clear the list
        mock_conversation_list.delete.assert_called_once_with(0, tk.END)

        # Ensure the insert method is called for each contact without the unread indicator
        mock_conversation_list.insert.assert_any_call(tk.END, "user1")
        mock_conversation_list.insert.assert_any_call(tk.END, "user2")

    @patch('client.send_request')  # Mock send_request
    @patch('client.update_conversation_list')  # Mock update_conversation_list
    def test_update_chat_window_unread_messages_marked_as_read(self, mock_update_conversation_list, mock_send_request):
        """
        Test update_chat_window function such that it marks unread messages as read
        """
        
        # Setup chat_window mock
        mock_chat_window = MagicMock()
        mock_chat_window.winfo_exists.return_value = True
        mock_chat_window.refresh_chat_text.return_value = True
        client.chat_windows = {}
        client.chat_windows["test_user"] = mock_chat_window
        client.conversations = {"test_user": [{"from": "test_user", "status": "unread", "message": "Hello!", "id": 1}]}
        client.current_user = "current_user"
        # Call update_chat_window
        client.update_chat_window("test_user")
        
        # Ensure that the status of the unread message is updated to "read"
        for message in client.conversations["test_user"]:
            if message["from"] == "test_user" and message["status"] == "unread":
                self.assertEqual(message["status"], "read")
        
        # Ensure send_request was called to mark messages as read
        mock_send_request.assert_called_once_with(6, f"{client.current_user}|test_user|0")
        
        # Ensure update_conversation_list was called to update the conversation list
        mock_update_conversation_list.assert_called_once()
        
    @patch('client.send_request')  # Mock send_request
    @patch('client.update_conversation_list')  # Mock update_conversation_list
    def test_update_chat_window_with_all_read_messages(self, mock_update_conversation_list, mock_send_request):
        """
        Test update_chat_window function such that it marks unread messages as read
        """
        
        # Setup chat_window mock
        mock_chat_window = MagicMock()
        mock_chat_window.winfo_exists.return_value = True
        mock_chat_window.refresh_chat_text.return_value = True
        client.chat_windows = {}
        client.chat_windows["test_user"] = mock_chat_window
        client.conversations = {"test_user": [{"from": "test_user", "status": "read", "message": "Hello!", "id": 1}]}
        
        # Call update_chat_window
        client.update_chat_window("test_user")
        
        mock_send_request.assert_not_called()
        
        # Ensure update_conversation_list was called to update the conversation list
        mock_update_conversation_list.assert_not_called()

    @patch('client.root.after')  # Mock the root.after method
    @patch('client.load_conversations')  # Mock load_conversations to avoid actual network calls
    def test_check_new_messages(self, mock_load_conversations, mock_after):
        """
        Test check_new_messages 
        """
        # Set up the mock for current_user
        client.current_user = "test_user"
        
        # Call check_new_messages
        client.check_new_messages()

        # Verify that load_conversations was called
        mock_load_conversations.assert_called_once()

        # Verify that root.after was called with 5000 as the delay, simulating recursive behavior
        mock_after.assert_called_once_with(5000, client.check_new_messages)

    @patch('client.chat_frame')  # Mock the chat frame
    @patch('client.login_frame')  # Mock the login frame
    @patch('client.new_conversation_entry')  # Mock the new conversation entry
    def test_logout_successful(self, mock_new_conversation_entry, mock_login_frame, mock_chat_frame):
        """
        Test logout function where the logout is successful
        """
        
        # Set up initial conditions
        client.current_user = "test_user"  # Set a valid current user

        # Properly mock subscription_socket with a MagicMock that has a close() method
        mock_socket = MagicMock()
        client.subscription_socket = mock_socket  # Assign the mock socket

        client.undelivered = {}

        # Call the logout function
        client.logout()

        # Verify that current_user is set to None
        self.assertIsNone(client.current_user)

        # Verify that the subscription_socket is closed
        mock_socket.close.assert_called_once()

        # Verify that the subscription_socket is set to None
        self.assertIsNone(client.subscription_socket)

        # Verify that chat_frame is packed for forget (hides chat frame)
        mock_chat_frame.pack_forget.assert_called_once()

        # Verify that login_frame is packed (shows login frame)
        mock_login_frame.pack.assert_called_once()

        # Verify that new_conversation_entry is cleared
        mock_new_conversation_entry.delete.assert_called_once_with(0, tk.END)

        # Verify that undelivered messages are cleared
        self.assertEqual(len(client.undelivered), 0)

    @patch('client.chat_frame')  # Mock the chat frame
    @patch('client.login_frame')  # Mock the login frame
    @patch('client.new_conversation_entry')  # Mock the new conversation entry
    def test_logout_error(self, mock_new_conversation_entry, mock_login_frame, mock_chat_frame):
        """
        Test logout function where the logout is successful
        """
        
        # Set up initial conditions
        client.current_user = "test_user"  # Set a valid current user

        # Properly mock subscription_socket with a MagicMock that has a close() method
        mock_socket = MagicMock()
        client.subscription_socket = mock_socket  # Assign the mock socket

        client.undelivered = {}
        mock_socket.close.side_effect = Exception("Failed to close socket")  # Simulate socket closure failure

        # Call the logout function
        client.logout()

        # Verify that current_user is set to None
        self.assertIsNone(client.current_user)

        # Verify that the subscription_socket is closed
        mock_socket.close.assert_called_once()

        # Verify that the subscription_socket is set to None
        self.assertIsNone(client.subscription_socket)

        # Verify that chat_frame is packed for forget (hides chat frame)
        mock_chat_frame.pack_forget.assert_called_once()

        # Verify that login_frame is packed (shows login frame)
        mock_login_frame.pack.assert_called_once()

        # Verify that new_conversation_entry is cleared
        mock_new_conversation_entry.delete.assert_called_once_with(0, tk.END)

        # Verify that undelivered messages are cleared
        self.assertEqual(len(client.undelivered), 0)



if __name__ == "__main__":
    unittest.main()