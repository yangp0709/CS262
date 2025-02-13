import sys
import os
import tkinter as tk

# Add the 'client' directory to the system path so that we can import from it
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Now you can import from the client directory
import client  # Adjust based on what you need to test
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
    def test_check_version_number_matched(self, mock_socket):
      """
      Test check_version_number function when the client and server version numbers match successfully
      """
      # Mock socket instance
      mock_conn = MagicMock()
      mock_socket.return_value = mock_conn
      # Simulated response from the server
      mock_conn.recv.return_value = b'success: Version matched'
      response = client.check_version_number()
      self.assertEqual(mock_conn, response)
      mock_socket.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)
      mock_conn.connect.assert_called_once()
      mock_conn.send.assert_called_once_with(client.CLIENT_VERSION.encode().ljust(32))
      mock_conn.recv.assert_called_once()

    @patch("socket.socket")
    def test_check_version_number_mismatch(self, mock_socket):
      """
      Test check_version_number function when the client and server versions mismatch
      """        
      # Mock socket instance
      mock_conn = MagicMock()
      mock_socket.return_value = mock_conn
      # Simulated response from the server
      mock_conn.recv.return_value = b"error: Version mismatch. Server: 1.000, Client: 2.000"
      response = client.check_version_number()
      self.assertIsNone(response)
      mock_socket.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)
      mock_conn.connect.assert_called_once()
      mock_conn.send.assert_called_once_with(client.CLIENT_VERSION.encode().ljust(32))
      mock_conn.recv.assert_called_once()

    @patch("socket.socket")
    def test_check_version_number_connect_error(self, mock_socket):
        """
        Test check_version_number when client fails to connect
        """
        # Mock socket instance
        mock_conn = MagicMock()
        mock_socket.return_value = mock_conn
        
        # Simulate connection failure
        mock_conn.connect.side_effect = Exception("Connection failed")
        response = client.check_version_number()
        self.assertIsNone(response)
        mock_socket.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)
        mock_conn.connect.assert_called_once()
        mock_conn.send.assert_not_called()
        mock_conn.recv.assert_not_called()

    @patch("socket.socket")
    def test_check_version_number_send_error(self, mock_socket):
        """
        Test check_version_number function when client fails to connect
        """
        # Mock socket instance
        mock_conn = MagicMock()
        mock_socket.return_value = mock_conn
        
        # Simulate send failure
        mock_conn.send.side_effect = Exception("Send failed")
        response = client.check_version_number()
        
        # Assert that the function returns None (since the connection failed)
        self.assertIsNone(response)
        mock_socket.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)
        mock_conn.connect.assert_called_once()
        mock_conn.send.assert_called_once()
        mock_conn.close.assert_not_called()

    @patch("client.check_version_number")
    @patch("tkinter.messagebox.showerror")
    def test_send_request_success(self, mock_messagebox, mock_check_version_number):
        """
        Test send_request function during succes
        """
        # Mock socket instance
        mock_socket = MagicMock()
        mock_check_version_number.return_value = mock_socket
        
        # Simulated response from the server
        mock_socket.recv.return_value = b'response'
        
        # Call function
        request_type = 2
        data = "empty"
        message = struct.pack("!I", request_type) + data.encode()
        response = client.send_request(request_type, data)
        
        # Assertions
        mock_socket.send.assert_called_once_with(message)
        mock_socket.recv.assert_called_once()
        mock_socket.close.assert_called_once()
        self.assertEqual(response, 'response')

    @patch("client.check_version_number")
    @patch("tkinter.messagebox.showerror")
    def test_send_request_send_error(self, mock_messagebox, mock_check_version_number):
        """
        Test send_request function when client fails to send
        """
        # Mock socket instance
        mock_socket = MagicMock()
        mock_check_version_number.return_value = mock_socket
        
        # Simulate send failure
        mock_socket.send.side_effect = Exception("Send failed")
        
        # Call the function
        response = client.send_request(1, "Test Data")
        
        # Assert that the function returns None (since the connection failed)
        self.assertIsNone(response)
        mock_socket.send.assert_called_once()
        mock_socket.close.assert_not_called()

    @patch("client.check_version_number")
    @patch("tkinter.messagebox.showerror")
    def test_send_request_close_error(self, mock_messagebox, mock_check_version_number):
        """
        Test send_request function when client fails to close
        """
        # Mock socket instance
        mock_socket = MagicMock()
        mock_check_version_number.return_value = mock_socket
        
        # Simulate send failure
        mock_socket.close.side_effect = Exception("Close failed")
        
        # Call the function
        response = client.send_request(1, "Test Data")
        
        # Assert that the function returns None (since the connection failed)
        self.assertIsNone(response)
        mock_socket.send.assert_called_once()
        mock_socket.close.assert_called_once()

    @patch("client.check_version_number")
    def test_send_request_check_version_error(self, mock_check_version_number):
        """
        Test send_request function when something fails in check_version_number
        """
        mock_check_version_number.return_value = None
    
        # Call function and expect None due to error
        response = client.send_request(1, "Hello")
        
        self.assertIsNone(response)

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
    @patch('client.send_request')
    def test_logout_successful(self, mock_send_request, mock_new_conversation_entry, mock_login_frame, mock_chat_frame):
        """
        Test logout function where the logout is successful
        """
        
        # Set up initial conditions
        client.current_user = "test_user"  # Set a valid current user

        # Properly mock subscription_socket with a MagicMock that has a close() method
        mock_socket = MagicMock()
        client.subscription_socket = mock_socket  # Assign the mock socket

        mock_send_request.return_value = "success: Logged out."

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
    @patch('client.send_request')
    def test_logout_socket_error(self, mock_send_request, mock_new_conversation_entry, mock_login_frame, mock_chat_frame):
        """
        Test logout function where the logout errors out due to failure to close socket
        """
        
        # Set up initial conditions
        client.current_user = "test_user"  # Set a valid current user

        # Properly mock subscription_socket with a MagicMock that has a close() method
        mock_socket = MagicMock()
        client.subscription_socket = mock_socket  # Assign the mock socket

        mock_send_request.return_value = "success: Logged out."

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

    @patch('client.send_request')
    def test_logout_request_error1(self, mock_send_request):
        """
        Test logout function where the logout errors out due send_request error
        """
        
        # Set up initial conditions
        client.current_user = "test_user"  # Set a valid current user

        # Properly mock subscription_socket with a MagicMock that has a close() method
        mock_socket = MagicMock()
        client.subscription_socket = mock_socket  # Assign the mock socket

        mock_send_request.return_value = None

        client.undelivered = {}

        # Call the logout function
        self.assertIsNone(client.logout(), msg=None)

    @patch('client.send_request')
    @patch("tkinter.messagebox.showerror")
    def test_logout_request_error2(self, mock_messsagebox, mock_send_request):
        """
        Test logout function where the logout errors out due logout function error in the server
        """
        
        # Set up initial conditions
        client.current_user = "test_user"  # Set a valid current user

        # Properly mock subscription_socket with a MagicMock that has a close() method
        mock_socket = MagicMock()
        client.subscription_socket = mock_socket  # Assign the mock socket

        mock_send_request.return_value = "error: Failed to log out. Username does not exist in active users."

        client.undelivered = {}

        # Call the logout function
        self.assertIsNone(client.logout(), msg=None)

if __name__ == "__main__":
    unittest.main()