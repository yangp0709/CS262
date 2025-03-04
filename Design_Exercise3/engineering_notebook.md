# Design Decisions and Features

## Asynchronous Design
The implementation leverages Python’s asyncio library to handle concurrent tasks efficiently. This is crucial for a distributed system where multiple virtual machines (VMs) run simultaneously and communicate over a network.
- asyncio.start_server() is used to create a non-blocking server for handling incoming connections.
- asyncio.open_connection() is used for outgoing connections to neighbors, ensuring non-blocking communication.
- asyncio.Queue() is employed for message passing, allowing incoming messages to be processed asynchronously.

## Logical Clock Mechanism
Each VM maintains a Lamport logical clock to establish event ordering:
- The clock starts at zero and increments with every internal or external event.
- Upon receiving a message, the clock updates using max(local, received) + 1.
- This ensures causality between events, a key requirement for distributed systems.

## Tick Rate and Event Handling
The tick rate controls how frequently a VM processes events:
- Each VM has a randomly assigned tick rate (1–6) unless overridden manually.
- The tick_loop() function executes at the tick rate, handling only tick rate number of the following events per second:
    - Processing messages from the queue.
    - Generating internal events (logical clock updates).
    - Sending messages to neighbors based on a probability model.

## Event Generation Model
To simulate randomness in event occurrences, a maximum random number (events_max_random_number, whose default is 10) is used:
- If the generated random number is 1, a message is sent to one neighbor.
- If 2, a message is sent to another neighbor.
- If 3, messages are sent to all neighbors.
- Otherwise, an internal event occurs, updating the logical clock.

## Logging
Logging is implemented for system behavior analysis:
- Each VM logs events to a dedicated file (log_vm_id.txt).
- The log includes system time, logical clock values, and event types (send/receive/internal).

## Startup and Shutdown
The system ensures a robust startup and teardown process:
- Each VM waits for connections to neighbors before proceeding.
- If a neighbor is unavailable, the VM retries until successful.
- Upon termination, tasks are canceled gracefully, and resources (servers, connections, log files) are cleaned up properly.

## Experimentation
The system allows multiple experiments with configurable parameters:
- run_experiment() executes simulations with five sequential experiments.
- Arguments such as manual mode and clock_speeds allow controlled testing, and events_max_random_number helps adjust the internal event probability.
- Old log files are removed before each experiment to ensure clean results.
- Through analysis.py, we analyze experimental results in the log files:
    - `parse_log_file(filepath)`: Reads a log file and parses each line. It extracts the tick rate, event details like system time, clock, queue length, and event type (SEND, RECEIVE, or INTERNAL).
    - `analyze_vm_events(events)`: Analyzes the event list for each VM to compute clock jumps (difference between consecutive clock values) and returns average and maximum jumps.
    - `analyze_experiment(sim_folder)`: Iterates through log files in the given folder, parses them, computes per-VM stats (tick rate, clock jumps, and event counts), and compares clock drifts across different VMs by checking events that occur within 0.1 seconds of each other.
    - `analyze_queue_stats(events)`: Computes the maximum queue length from the event data.
    - `count_event_types(events)`: Counts the number of SEND, INTERNAL, and RECEIVE events and computes the proportion of SEND events to the total SEND + INTERNAL events.

## Error Handling
- Try-except blocks prevent crashes due to message parsing errors.
- Connection attempts retry until successful, preventing failures due to startup order.
- Timeout handling ensures resources do not hang indefinitely during shutdown.

---