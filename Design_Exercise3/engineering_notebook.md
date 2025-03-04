# Code Link: https://github.com/yangp0709/CS262/tree/main/Design_Exercise3

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

# Experiments

Experiments were conducted to analyze the effects of various clock rate VM combinations and internal event probabilities. For more details about each individual experiment run, go to experiments/clock_rate_experiments/clock_rate_experiments.md for clock rate experiments and experiments/internal_event_probability_experiments/internal_event_probability_experiments.md for internal event probability experiments. 

## Comparative Analysis Across Clock Rate Experiments

Below is a analysis of each experiment based on the clock‐rate settings. Each experiment corresponds to a .txt file in clock_rate_experiments, where the name of the .txt file is the combination of VM clock rates. These experiments are ran for 1 minute, are standardized to run with the default internal event probability of 70%, have the stats for SEND + INTERNAL vs. RECEIVE from the first simulation listed below, and have the average stats across 5 simulations for each experiment.

| **Experiment**                           | **Setup**                                   | **Total Events**                | **Avg. Clock Jump**                  | **Max Clock Jump**                   | **Max Queue Length** | **SEND + INTERNAL vs. RECEIVE**                     |
|-------------------------------------------|---------------------------------------------|---------------------------------|-------------------------------------|-------------------------------------|----------------------|-----------------------------------------------------|
| **Uniform Threes (3_3_3.txt)**           | All VMs at 3 ticks/sec                      | 190–194                         | 1.03–1.04                           | 2–4                                 | 2–4                  | VM1: 137 vs. 55, VM2: 142 vs. 50, VM3: 141 vs. 53  |
| **Uniform Ones (1_1_1.txt)**             | All VMs at 1 tick/sec                      | 63–67                           | 1.06–1.18                           | 2                                   | 0–1                  | VM1: 47 vs. 17, VM2: 45 vs. 19, VM3: 52 vs. 14     |
| **Minor Variation (1_1_3.txt)**          | Two VMs at 1 tick/sec, one at 3            | 60 (slow), 190–200 (fast)       | 3.1–3.25 (slow), 1.00 (fast)       | 10–19 (slow), 1 (fast)             | 2–3 (slow)           | VM1: 21 vs. 40, VM2: 24 vs. 38, VM3: 190 vs. 7     |
| **Mixed Extremes (1_1_6.txt)**           | Two VMs at 1 tick/sec, one at 6            | 60 (slow), 390–410 (fast)       | 4.4–6 (slow), 1.00 (fast)          | 20–28 (slow)                        | 9–33 (slow)          | VM1: 2 vs. 58, VM2: 1 vs. 59, VM3: 397 vs. 0       |
| **Low Dominant, Middle Majority (1_3_3.txt)** | One VM at 1 tick/sec, two at 3         | 60 (slow), 190–200 (mid)        | 3–3.3 (slow), 1.03–1.07 (mid)      | 10–13 (slow), 3–4 (mid)            | 6–14 (slow)          | VM1: 2 vs. 58, VM2: 149 vs. 43, VM3: 176 vs. 20    |
| **Ascending Order (1_3_5.txt)**          | One VM at 1 tick/sec, one at 3, one at 5   | 60 (slow), 190–200 (mid), 320–330 (fast) | 3.8–4.0 (slow), 1.6–1.7 (mid), 1.00 (fast) | 14–21 (slow), 10–12 (mid), 1 (fast) | 24–28 (slow)        | VM1: 1 vs. 59, VM2: 138 vs. 52, VM3: 302 vs. 26    |
| **Low vs High (1_6_6.txt)**              | One VM at 1 tick/sec, two at 6            | 60 (slow), 390–400 (fast)       | 3–3.5 (slow), 1.02–1.04 (fast)     | 12+ (slow), 3–4 (fast)             | 64–76 (slow)         | VM1: 1 vs. 59, VM2: 350 vs. 52, VM3: 322 vs. 69    |
| **Uniform Sixes (6_6_6.txt)**            | All VMs at 6 ticks/sec                      | 380–390                         | 1.05–1.07                           | 4–8                                 | 1–7                  | VM1: 289 vs. 97, VM2: 281 vs. 102, VM3: 278 vs. 104 |


- **Impact of Tick Rate on Event Volume:**  
  The total number of events processed by a VM is directly tied to its tick rate. Uniform fast machines (6_6_6) achieve roughly six times the event count of the uniform slow ones (1_1_1). In mixed experiments (such as 1_1_6 and 1_3_5), the high-rate machines accumulate hundreds of events while the low-rate machines process only a few dozen.

- **SEND + INTERNAL vs. RECEIVE Ratio:**  
  - A high ratio of RECEIVE events to SEND + INTERNAL events indicates that a VM is receiving far more messages than it is generating when idle. This is typical for slower VMs in mixed environments, which leads to longer queue lengths.  
  - Conversely, when the ratio is more balanced, as in uniform experiments, VMs process messages in a timely manner, keeping queue lengths minimal and clock jumps small.

- **Effects on Queue Length and Clock Jumps:**  
  - **Longer Queues:**  
    A VM that receives many messages without generating many SEND or INTERNAL events (typically a slow VM) will experience longer queue lengths. When it eventually processes these messages, the resulting clock jumps can be much larger due to the clock update rule.  
  - **Shorter Queues:**  
    VMs that maintain a balanced ratio (common in uniform or high-speed setups) have shorter queues, resulting in smaller, more consistent clock jumps.

- **Logical Clock Behavior:**  
  VMs running at higher speeds maintain nearly constant, minimal clock jumps (usually a jump of 1 per event), reflecting a steady progression. In contrast, slower VMs that rarely process their queue are forced to catch up when they do update—resulting in much larger average and maximum clock jumps. This phenomenon is particularly noticeable in experiments with extreme disparities (e.g., Mixed Extremes and Low vs High).

- **Queue Length Dynamics:**  
  When there is a significant difference in processing speeds, the slower VMs experience substantial message backlog, with maximum queue lengths far exceeding those of their faster counterparts. In the uniform experiments (Uniform Ones or Uniform Sixes), queues remain consistently short, indicating that the message arrival rate and processing rate are well matched.

- **Cross-VM Drift:**  
  The average cross-VM drift (the difference in logical clock values when events occur almost simultaneously) is lowest in uniform setups and tends to spike in mixed experiments. High drift values in experiments like 1_1_6 and 1_6_6 indicate that fast machines rapidly advance their clocks, leaving slower machines far behind.

- **General Trends:**  
  - **Uniform experiments** (either all slow or all fast) lead to balanced, predictable behavior with steady logical clock increments and short queues.  
  - **Mixed experiments** show a clear imbalance: the slower machines are overwhelmed by messages from faster ones, leading to larger, more abrupt clock adjustments and increased queue lengths.  
  - **Gradient experiments** (e.g., Ascending Order with 1, 3, and 5) illustrate how even moderate differences in clock rates can lead to significantly different performance outcomes among VMs.

---


## Comparative Analysis Across Internal Event Probability Experiments

Each experiment was run with a different probability for a VM to choose an internal event when no messages are pending. These experiments are ran for 1 minute and have the average stats across 5 simulations for each experiment.

**Clarification:**  
- When a VM has a message in its queue, it always logs a **receive** event.  
- Only when the queue is empty does the VM decide between performing a **send** event or an **internal** event.  
- The _internal event probability_ is the chance that the VM chooses an **internal** event instead of a **send** event when the queue is empty.

In all experiments, three virtual machines (VMs) run at different tick rates:  
- **VM 1:** Tick rate 1 (slow)  
- **VM 2:** Tick rate 3 (medium)  
- **VM 3:** Tick rate 5 (fast)  

| **Experiment** | **Internal Event Probability** | **Total Events**                          | **Avg. Clock Jump**                       | **Max Clock Jump**                     | **Max Queue Length**                 |
|--------------|-----------------------------|-------------------------------------------|-------------------------------------------|-------------------------------------------|-------------------------------------------|
| **25.txt**  | 25%                         | VM1: 60–61, VM2: 181–198, VM3: 364–383   | VM1: 2.2–2.5, VM2: 1.81–2.11, VM3: 1.00  | VM1: 8–10, VM2: 6–8, VM3: 1–2           | VM1: 90–112, VM2: 3–8, VM3: 1–3       |
| **40.txt**  | 40%                         | VM1: 60, VM2: 189–199, VM3: 350–360      | VM1: 2.24–2.58, VM2: 1.82–1.94, VM3: 1.00–1.04  | VM1: 7–12, VM2: 6–8, VM3: 1–4          | VM1: 67–88, VM2: 3, VM3: 1–2         |
| **50.txt**  | 50%                         | VM1: 60–61, VM2: 194–202, VM3: 338–347   | VM1: 2.64–2.97, VM2: 1.68–1.71, VM3: 1.00  | VM1: 8–13, VM2: 7–9, VM3: 1           | VM1: 56–72, VM2: 3, VM3: 1–4         |
| **70.txt**  | 70%                         | VM1: 60, VM2: 190, VM3: 328–333          | VM1: 3.63–4.03, VM2: 1.64–1.70, VM3: 1.00  | VM1: 8–18, VM2: 9–12, VM3: 1           | VM1: 24–28, VM2: 2–4, VM3: 1         |
| **80.txt**  | 80%                         | VM1: 60, VM2: 192–196, VM3: 313–321      | VM1: 4.90–5.17, VM2: 1.53–1.65, VM3: 1.00  | VM1: 28–32, VM2: 12–19, VM3: 1          | VM1: 2–7, VM2: 2, VM3: 1–2           |

- **Total Events Processed:**  
  In every experiment, the fast VM (tick 5) consistently processes many more events (typically 330–380 events) compared to the slow VM (tick 1, around 60 events) and the medium VM (tick 3, around 180–200 events). The internal event probability does not significantly affect the overall event count on each VM because the tick rate remains the dominant factor.

- **Average Clock Jump:**  
  - **VM 1 (Tick 1):**  
    As the internal event probability increases from 25% to 80%, the average clock jump on the slow VM increases from approximately 2.2–2.5 (at 25%) to around 4.9–5.2 (at 80%). This reflects that a higher probability of internal events causes the VM to perform more internal (non-send) actions when idle, leading to larger clock adjustments when a message is eventually received.  
  - **VM 2 (Tick 3) and VM 3 (Tick 5):**  
    Their average clock jumps remain relatively constant (around 1.7 for VM 2 and 1.0 for VM 3) regardless of the internal event probability, reflecting their more frequent processing and consistent pace.

- **Maximum Clock Jump:**  
  The maximum clock jump for VM 1 increases considerably with higher internal event probabilities—from single-digit values at lower probabilities (8–10) to very high values (up to 28–32) at 80%. In contrast, VM 3’s maximum clock jump remains almost unaffected, and VM 2 shows only modest increases.

- **Maximum Queue Length:**  
  The slow VM (VM 1) experiences very high maximum queue lengths at lower internal event probabilities (up to 112 at 25%) but sees a dramatic reduction at higher probabilities (dropping to as low as 2–7 at 80%). This makes sense as when more send events are sent, the faster VMs will send more than the slow VMs and inundate the slow VM's message queues. The medium and fast VMs maintain low queue lengths across all experiments. At high internal event probabilities, the fast VMs send less messages overall such that the slow VM has a smaller message backlog to handle.

- **Overall Trends:**  
  - **Slow VM (Tick 1):** Highly sensitive to the internal event probability, showing increased clock jumps and reduced queue lengths at higher probabilities.  
  - **Medium VM (Tick 3):** Exhibits minor variations, with average clock jumps remaining stable and consistently low queue lengths.  
  - **Fast VM (Tick 5):** Largely unaffected by changes in internal event probability, maintaining a steady event rate, constant minimal clock jumps, and very short queues.

- **Main Conclusion about the Effect of Internal Event Probability**
  - The internal event probability appears to be a balance between a lower avg clock jump or a smaller message queue buildup for the slower VMs in a network. 
  
  - **High Internal Event Probability = Higher Avg Clock Jumps and Less Message Buildup for slower VMs:** Higher clock rate VMs do more internal events than slower VMs, so, in our logical clock implementation, a higher internal event probability leads to a larger discrepancy between slow and fast VMs and a higher avg clock jump for the slow VM. However, with less messages sent, the slower VMs have significantly less build up of messages in their queue. 
  
  - **Low Internal Event Probability = Lower Avg Clock Jumps and More Message Buildup for slower VMs:** Lower internal event probability leads to more sends, which gives slower VMs more chances to catch up to faster neighboring VMs and, consequently, a lower avg clock jump. However, the faster VMs send messages significantly more than the slower VMs, causing slow VM message queues to be filled significantly more. 

  - **Cross-VM Drift:**  
  The average cross-VM drift (the difference in logical clock values between nearly simultaneous events) tends to decrease as the internal event probability increases. Lower drift at high probabilities implies that although the slow VM’s clock jumps are larger, they help it catch up with the fast VMs more quickly, reducing the temporal gap for near-simultaneous events.

---
