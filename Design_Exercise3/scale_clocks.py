import asyncio
import random
import time
import json
import os
import argparse

class VirtualMachine:
    def __init__(self, vm_id, port, neighbors, sim_folder, tick_rate_override = None, events_max_random_number = 10):
        self.vm_id = vm_id
        self.port = port
        self.neighbors = neighbors  # dict of neighbor_id: port
        self.logical_clock = 0
        self.tick_rate = tick_rate_override if tick_rate_override is not None else random.randint(1, 6)
        self.events_max_random_number = events_max_random_number
        self.msg_queue = asyncio.Queue()
        self.server = None
        self.server_task = None
        self.neighbor_writers = {}
        log_path = os.path.join(sim_folder, f"log_{self.vm_id}.txt")
        self.log_file = open(log_path, "a")
        self.log_file.write(f"TICK RATE: {self.tick_rate}\n \n")
        self.log_file.flush()
        print('TICKRATE', self.vm_id, ':', self.tick_rate) #TODO DELETE

    async def start_server(self):
        self.server = await asyncio.start_server(
            self.handle_connection, 
            '127.0.0.1', 
            self.port,
            reuse_address=True,
            reuse_port=True
        )
        print(f"VM {self.vm_id} listening on port {self.port}")
        self.server_task = asyncio.create_task(self.server.serve_forever())


    async def handle_connection(self, reader, writer):
        while True:
            data = await reader.readline()
            if not data:
                break
            try:
                msg = json.loads(data.decode().strip())
            except Exception as e:
                print(f"VM {self.vm_id} error parsing message: {e}")
                continue
            await self.msg_queue.put(msg)
        writer.close()
        await writer.wait_closed()

    async def connect_to_neighbors(self):
        for neighbor_id, neighbor_port in self.neighbors.items():
            while True:
                try:
                    reader, writer = await asyncio.open_connection('127.0.0.1', neighbor_port)
                    self.neighbor_writers[neighbor_id] = writer
                    print(f"VM {self.vm_id} connected to VM {neighbor_id} on port {neighbor_port}")
                    break
                except Exception:
                    await asyncio.sleep(1)

    async def tick_loop(self):
        counter = 0
        while True:
            if counter == self.tick_rate:
                counter = 0
                await asyncio.sleep(1 - (time.time() - counter_start_time))
                print(time.time() - counter_start_time) # expecting 1 as check
                self.log_file.write(('ONE SECOND\n \n')) #TODO DELETE
            else:
                if counter == 0:
                  counter_start_time = time.time()
                counter += 1

                if not self.msg_queue.empty():
                    msg = await self.msg_queue.get()
                    recv_clock = msg.get("clock", 0)
                    sender_id = msg.get("sender")
                    # Lamport clock update: max(local, received) + 1
                    self.logical_clock = max(self.logical_clock, recv_clock) + 1
                    log_entry = (f"RECEIVE from {sender_id}: system time {time.time():.2f}, "
                                f"queue length {self.msg_queue.qsize()}, logical clock {self.logical_clock}\n")
                    self.log_file.write(log_entry)
                    self.log_file.flush()
                else:
                    event = random.randint(1, self.events_max_random_number)
                    if event == 1:
                        self.log_file.write(('EVENT 1\n')) #TODO DELETE
                        # Send to one neighbor (pick first in list)
                        neighbor_id = list(self.neighbors.keys())[0]
                        await self.send_message(neighbor_id)
                    elif event == 2:
                        self.log_file.write(('EVENT 2\n')) #TODO DELETE
                        # Send to the other neighbor (pick second in list)
                        neighbor_id = list(self.neighbors.keys())[1]
                        await self.send_message(neighbor_id)
                    elif event == 3:
                        self.log_file.write(('EVENT 3\n')) #TODO DELETE
                        # Send to both neighbors
                        for neighbor_id in self.neighbors.keys():
                            await self.send_message(neighbor_id)
                    else:
                        self.log_file.write(('EVENT ELSE\n')) #TODO DELETE
                        # Internal event: update clock and log
                        self.logical_clock += 1
                        log_entry = f"INTERNAL: system time {time.time():.2f}, logical clock {self.logical_clock}\n"
                        self.log_file.write(log_entry)
                        self.log_file.flush()

    async def send_message(self, neighbor_id):
        writer = self.neighbor_writers.get(neighbor_id)
        if writer is None:
            return
        self.logical_clock += 1
        msg = {"sender": self.vm_id, "clock": self.logical_clock}
        data = json.dumps(msg) + "\n"
        writer.write(data.encode())
        await writer.drain()
        log_entry = f"SEND to {neighbor_id}: system time {time.time():.2f}, logical clock {self.logical_clock}\n"
        self.log_file.write(log_entry)
        self.log_file.flush()

async def run_experiment(exp_num, manual=False, clock_speeds=None, events_max_random_number=10):
    sim_folder = f"simulation_{exp_num}"
    if not os.path.exists(sim_folder):
        os.makedirs(sim_folder)
    ports = {1: 8001, 2: 8002, 3: 8003}
    machines = {}

    # Remove old log files in the simulation folder.
    for vm_id in ports:
        log_filename = os.path.join(sim_folder, f"log_{vm_id}.txt")
        if os.path.exists(log_filename):
            os.remove(log_filename)
            print(f"Deleted {log_filename}")

    # Create VMs with neighbors.
    for vm_id in ports:
        neighbors = {other_id: port for other_id, port in ports.items() if other_id != vm_id}
        tick_rate_override = clock_speeds[vm_id - 1] if (manual and clock_speeds) else None
        print("events_max_random_number", events_max_random_number)
        machines[vm_id] = VirtualMachine(vm_id, ports[vm_id], neighbors, sim_folder, tick_rate_override, events_max_random_number)

    # Start servers and connect to neighbors.
    await asyncio.gather(*(vm.start_server() for vm in machines.values()))
    await asyncio.gather(*(vm.connect_to_neighbors() for vm in machines.values()))
    tick_tasks = [asyncio.create_task(vm.tick_loop()) for vm in machines.values()]
    await asyncio.sleep(60)

    # Cancel tick tasks.
    for task in tick_tasks:
        task.cancel()
    print(f"Experiment {exp_num} finished")

    # Close servers and connections.
    for vm in machines.values():
        # Cancel the serve_forever task if it exists.
        if vm.server_task is not None:
            vm.server_task.cancel()
            try:
                await asyncio.wait_for(vm.server_task, timeout=2)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
        if vm.server:
            vm.server.close()
            try:
                await asyncio.wait_for(vm.server.wait_closed(), timeout=2)
            except asyncio.TimeoutError:
                print(f"Timeout closing server for VM {vm.vm_id}")
        for writer in vm.neighbor_writers.values():
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), timeout=2)
            except asyncio.TimeoutError:
                print(f"Timeout closing writer for VM {vm.vm_id}")
        vm.log_file.close()


async def main(manual=False, clock_speeds=None, events_max_random_number=10):
    for i in range(1, 6):
        await run_experiment(i, manual, clock_speeds, events_max_random_number)
        await asyncio.sleep(5)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Scale Clocks Simulation")
    parser.add_argument("--manual", "--m", action="store_true",
                        help="Enable manual mode to specify VM clock speeds and internal event probability")
    parser.add_argument("--clock_speeds", "--c", type=str, default="",
                        help="Comma-separated list of three clock speeds (e.g., '1,3,5')")
    parser.add_argument("--events_max_random_number", "--max", type=int, default=10,
                        help="The maximum random number for events, default is randint(1, 10)")
    args = parser.parse_args()

    manual = args.manual
    clock_speeds = None
    if manual:
        if args.clock_speeds:
            try:
                clock_speeds = [int(x.strip()) for x in args.clock_speeds.split(",")]
                if len(clock_speeds) != 3:
                    raise ValueError("Please provide exactly three clock speeds.")
            except Exception as e:
                print("Error parsing clock speeds:", e)
                exit(1)
        else:
            print("Manual mode enabled but no clock speeds provided. Exiting.")
            exit(1)

    try:
        asyncio.run(main(manual, clock_speeds, args.events_max_random_number))
    except KeyboardInterrupt:
        print("Shutting down...")
            
        