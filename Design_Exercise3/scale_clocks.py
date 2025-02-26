import asyncio
import random
import time
import json
import os

class VirtualMachine:
    def __init__(self, vm_id, port, neighbors):
        self.vm_id = vm_id
        self.port = port
        self.neighbors = neighbors  # dict of neighbor_id: port
        self.logical_clock = 0
        self.tick_rate = random.randint(1, 6)
        self.msg_queue = asyncio.Queue()
        self.neighbor_writers = {}
        self.log_file = open(f"log_{self.vm_id}.txt", "a")
        print('TICKRATE', self.vm_id, ':', self.tick_rate) #TODO DELETE

    async def start_server(self):
        server = await asyncio.start_server(self.handle_connection, '127.0.0.1', self.port)
        print(f"VM {self.vm_id} listening on port {self.port}")
        asyncio.create_task(server.serve_forever())

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
                self.log_file.write(('ONE SECOND\n')) #TODO DELETE
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
                    event = random.randint(1, 10)
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

async def main():
    # Define ports for three machines.
    ports = {1: 8001, 2: 8002, 3: 8003}
    machines = {}

    # if there are preexisting log files, delete them
    for vm_id in ports:
        log_filename = f"log_{vm_id}.txt"
        if os.path.exists(log_filename):
            os.remove(log_filename)
            print(f"Deleted {log_filename}")

    # Each VM's neighbors: all other VMs.
    for vm_id in ports:
        neighbors = {other_id: port for other_id, port in ports.items() if other_id != vm_id}
        machines[vm_id] = VirtualMachine(vm_id, ports[vm_id], neighbors)

    # Start each VM's server.
    await asyncio.gather(*(vm.start_server() for vm in machines.values()))
    # Connect to neighbor VMs.
    await asyncio.gather(*(vm.connect_to_neighbors() for vm in machines.values()))
    # Run tick loops concurrently.
    await asyncio.gather(*(vm.tick_loop() for vm in machines.values()))

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down...")
            
        