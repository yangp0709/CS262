Instruction

Create new virtual environment
```
python -m venv cs2620_design_exercise_1_env
source cs2620_design_exercise_1_env/bin/activate   # On macOS/Linux
cs2620_design_exercise_1_env\Scripts\activate      # On Windows
```

Assuming you are in the directory Design_Exercise1:

To run tests for custom wire protocol implementation, 
```
pytest custom_wire_protocol_implementation/tests/
```

To run tests for json implementation,
```
pytest json_implementation/tests/
```

To run the server on the terminal for custom wire protocol implementation,
```
python custom_wire_protocol_implementation/server.py
```

To run the server on the terminal for json implementation,
```
python json_implementation/server.py
```

To run the client on the terminal for custom wire protocol implementation,
```
python custom_wire_protocol_implementation/client.py
```

To run the client on the terminal for json implementation,
```
python json_implementation/client.py
```

