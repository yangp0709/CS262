import tkinter as tk
from tkinter import ttk

# Define tkinter objects used in the UI

root = tk.Tk()

# Login Frame
login_frame = tk.Frame(root)

username_entry_var = tk.StringVar()
username_entry = ttk.Combobox(login_frame, textvariable=username_entry_var, width=20)

password_entry = tk.Entry(login_frame, show="*", width=22)

# Chat Frame
chat_frame = tk.Frame(root)
chat_label = tk.Label(chat_frame, text="Chat")

new_conversation_entry_var = tk.StringVar()
new_conversation_entry = ttk.Combobox(chat_frame, textvariable=new_conversation_entry_var, width=30)

conversation_list = tk.Listbox(chat_frame, height=10, width=40)
