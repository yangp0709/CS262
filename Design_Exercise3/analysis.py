import os
import re
import statistics

event_pattern = re.compile(r"system time ([0-9]+\.[0-9]+).*logical clock (\d+)")
queue_pattern = re.compile(r"queue length (\d+)")

def parse_log_file(filepath):
    """
    Parse a log file returning:
      - tick_rate (from header line "TICK RATE: X")
      - list of events: each is a dict with 'time', 'clock', 'queue' (if any), and raw line.
    """
    events = []
    tick_rate = None
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            # Check header
            if line.startswith("TICK RATE:"):
                try:
                    tick_rate = int(line.split(":")[1].strip())
                except Exception:
                    tick_rate = None
            else:
                match = event_pattern.search(line)
                if match:
                    system_time = float(match.group(1))
                    clock = int(match.group(2))
                    q_match = queue_pattern.search(line)
                    queue_length = int(q_match.group(1)) if q_match else None
                    events.append({
                        "time": system_time,
                        "clock": clock,
                        "queue": queue_length,
                        "line": line
                    })
    return tick_rate, events

def analyze_vm_events(events):
    """
    Compute the jump sizes between consecutive clock values for a VM.
    Returns: avg_jump, max_jump, and a list of all jumps.
    """
    jumps = []
    prev_clock = None
    for ev in events:
        if prev_clock is not None:
            jumps.append(ev["clock"] - prev_clock)
        prev_clock = ev["clock"]
    avg_jump = statistics.mean(jumps) if jumps else 0
    max_jump = max(jumps) if jumps else 0
    return avg_jump, max_jump, jumps

def analyze_experiment(sim_folder):
    """
    For a given simulation folder, reads all log files (assumes filenames log_1.txt, log_2.txt, etc.),
    computes per-VM stats and cross-VM drift.
    """
    vm_data = {}
    for fname in os.listdir(sim_folder):
        if fname.startswith("log_") and fname.endswith(".txt"):
            vm_id = fname.split("_")[1].split(".")[0]
            filepath = os.path.join(sim_folder, fname)
            tick_rate, events = parse_log_file(filepath)
            avg_jump, max_jump, jumps = analyze_vm_events(events)
            vm_data[vm_id] = {
                "tick_rate": tick_rate,
                "events": events,
                "avg_jump": avg_jump,
                "max_jump": max_jump,
                "num_events": len(events)
            }
    all_events = []
    for vm_id, data in vm_data.items():
        for ev in data["events"]:
            ev["vm_id"] = vm_id
            all_events.append(ev)
    all_events.sort(key=lambda x: x["time"])
    # Compute drift differences: if two consecutive events from different VMs occur within 0.1 sec, record their clock difference.
    drift_diffs = []
    for i in range(1, len(all_events)):
        if all_events[i]["vm_id"] != all_events[i-1]["vm_id"]:
            dt = all_events[i]["time"] - all_events[i-1]["time"]
            if dt < 0.1:
                diff = abs(all_events[i]["clock"] - all_events[i-1]["clock"])
                drift_diffs.append(diff)
    avg_drift = statistics.mean(drift_diffs) if drift_diffs else None

    return vm_data, avg_drift

def analyze_queue_stats(events):
    # Get all queue length values
    queue_lengths = [ev["queue"] for ev in events if ev.get("queue") is not None]
    if queue_lengths:
        max_queue = max(queue_lengths)
    else:
        max_queue = 0
    return max_queue


def main():
    sim_dirs = [d for d in os.listdir(".") if d.startswith("simulation_") and os.path.isdir(d)]
    sim_dirs.sort()
    for sim in sim_dirs:
        print(f"Analysis for {sim}:")
        vm_data, avg_drift = analyze_experiment(sim)
        
        for vm_id, data in sorted(vm_data.items()):
            max_queue = analyze_queue_stats(data["events"])
            print(f"  VM {vm_id}:")
            print(f"    Tick Rate: {data['tick_rate']}")
            print(f"    Total events: {data['num_events']}")
            print(f"    Average clock jump: {data['avg_jump']:.2f}")
            print(f"    Maximum clock jump: {data['max_jump']}")
            print(f"    Maximum queue length: {max_queue}")

        if avg_drift is not None:
            print(f"  Average cross-VM drift (for events <0.1 sec apart): {avg_drift:.2f}")
        else:
            print("  Not enough close events to compute cross-VM drift.")
        print("-" * 40)

if __name__ == "__main__":
    main()
