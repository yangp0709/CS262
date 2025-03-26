Instruction

Create new virtual environment and install necessary dependencies
```
python3 -m venv cs2620_design_exercise_4_env
source cs2620_design_exercise_4_env/bin/activate   # On macOS/Linux
cs2620_design_exercise_4_env\Scripts\activate      # On Windows

pip install -r requirements.txt
```

Assuming you are in the directory replication inside Design_Exercise4:

To run tests for replication implementation, run
```
pytest tests/
```

To run one of three servers on the terminal for the replication implementation, run
```
python3 server.py --id <server_id> --all_ips <IP1,IP2,IP3>

# Example setup
python3 server.py --id 1 --all_ips 10.350.166.253,10.260.77.254,127.0.0.0 # Machine 1
python3 server.py --id 2 --all_ips 10.350.166.253,10.260.77.254,127.0.0.0 # Machine 2
python3 server.py --id 3 --all_ips 10.350.166.253,10.260.77.254,127.0.0.0 # Machine 3
```
where <server_id> is uniquely one of [1,2,3] (lower takes precedence in being leader) and <IP1,IP2,IP3> are the IPs of server machines.

To run the client on the terminal for replication implementation, run
```
python3 client.py --all_ips <IP1,IP2,IP3>

# Example setup
python3 client.py --id 1 --all_ips 127.0.0.1,127.0.0.1,127.0.0.1 # Machine 1
python3 client.py --id 2 --all_ips 127.0.0.1,127.0.0.1,127.0.0.1 # Machine 2
python3 client.py --id 3 --all_ips 127.0.0.1,127.0.0.1,127.0.0.1 # Machine 3
```
where <IP1,IP2,IP3> are the IPs of server machines.