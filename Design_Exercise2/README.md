Instruction

Create new virtual environment and install necessary dependencies
```
python -m venv cs2620_design_exercise_2_env
source cs2620_design_exercise_2_env/bin/activate   # On macOS/Linux
cs2620_design_exercise_2_env\Scripts\activate      # On Windows

pip install -r requirements.txt
```

Assuming you are in the directory Design_Exercise2:

To run tests for gRPC implementation, run
```
pytest grpc_implementation/tests/
```

To run the server on the terminal for gRPC implementation, run
```
python grpc_implementation/server.py
```
and input the desired host and port.

To run the server on the terminal for gRPC implementation, run
```
python grpc_implementation/client.py
```
and input the desired host and port.
