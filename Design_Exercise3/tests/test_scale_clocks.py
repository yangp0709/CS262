import unittest
import asyncio
import os
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scale_clocks import VirtualMachine

class TestVirtualMachine(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """
        Create 3 VMs to use in testing.
        """
        self.test_dir = tempfile.mkdtemp()

        self.vm1_port = 8001
        self.vm2_port = 8002
        self.vm3_port = 8003

        # Define neighbors: each VM has the other two as neighbors
        neighbors_1 = {2: self.vm2_port, 3: self.vm3_port}
        neighbors_2 = {1: self.vm1_port, 3: self.vm3_port}
        neighbors_3 = {1: self.vm1_port, 2: self.vm2_port}

        # Create the three VMs, with fixed tick_rate for deterministic tests
        self.vm1 = VirtualMachine(
            vm_id=1,
            port=self.vm1_port,
            neighbors=neighbors_1,
            sim_folder=self.test_dir,
            tick_rate_override=1,
            events_max_random_number=2
        )
        self.vm2 = VirtualMachine(
            vm_id=2,
            port=self.vm2_port,
            neighbors=neighbors_2,
            sim_folder=self.test_dir,
            tick_rate_override=1,
            events_max_random_number=2
        )
        self.vm3 = VirtualMachine(
            vm_id=3,
            port=self.vm3_port,
            neighbors=neighbors_3,
            sim_folder=self.test_dir,
            tick_rate_override=1,
            events_max_random_number=2
        )

    async def asyncTearDown(self):
        """
        Called after each test. Cleans up servers, tasks, and files.
        """
        # Cancel server tasks if they exist
        for vm in (self.vm1, self.vm2, self.vm3):
            if vm.server_task:
                vm.server_task.cancel()
                try:
                    await vm.server_task
                except asyncio.CancelledError:
                    pass

        # Close servers
        for vm in (self.vm1, self.vm2, self.vm3):
            if vm.server:
                vm.server.close()
                await vm.server.wait_closed()
            vm.log_file.close()

        if os.path.exists(self.test_dir):
            for fname in os.listdir(self.test_dir):
                os.remove(os.path.join(self.test_dir, fname))
            os.rmdir(self.test_dir)


    async def test_server_connection(self):
        """
        Test that each VM can start a server and connect to its neighbor.
        """
        # Start servers
        await self.vm1.start_server()
        await self.vm2.start_server()
        await self.vm3.start_server()

        # Connect neighbors
        await self.vm1.connect_to_neighbors()
        await self.vm2.connect_to_neighbors()
        await self.vm3.connect_to_neighbors()

        # Check that each VM sees the correct neighbor writers
        self.assertIn(2, self.vm1.neighbor_writers)
        self.assertIn(3, self.vm1.neighbor_writers)
        self.assertIn(1, self.vm2.neighbor_writers)
        self.assertIn(3, self.vm2.neighbor_writers)
        self.assertIn(1, self.vm3.neighbor_writers)
        self.assertIn(2, self.vm3.neighbor_writers)

    async def test_message_exchange(self):
        """
        Test sending messages among the three VMs. For example:
        1 -> 2, then 2 -> 3, then check that 3 receives it, etc.
        """
        await self.vm1.start_server()
        await self.vm2.start_server()
        await self.vm3.start_server()
        await self.vm1.connect_to_neighbors()
        await self.vm2.connect_to_neighbors()
        await self.vm3.connect_to_neighbors()

        # Send a message from vm1 to vm2
        await self.vm1.send_message(2)
        await asyncio.sleep(0.1)
        self.assertFalse(self.vm2.msg_queue.empty(), "vm2 did not receive any message from vm1.")
        msg = await self.vm2.msg_queue.get()
        self.assertEqual(msg["sender"], 1)

        # Now vm2 sends a message to vm3
        await self.vm2.send_message(3)
        await asyncio.sleep(0.1)
        self.assertFalse(self.vm3.msg_queue.empty(), "vm3 did not receive any message from vm2.")
        msg2 = await self.vm3.msg_queue.get()
        self.assertEqual(msg2["sender"], 2)

        # Additionally, vm1 sends a message to vm3
        await self.vm1.send_message(3)
        await asyncio.sleep(0.1)
        self.assertFalse(self.vm3.msg_queue.empty(), "vm3 did not receive second message from vm1.")
        msg3 = await self.vm3.msg_queue.get()
        self.assertEqual(msg3["sender"], 1)

    async def test_tick_loop_receives_message(self):
        """
        Test that the tick loop can process a received message and
        update the logical clock accordingly.
        """
        await self.vm1.start_server()
        await self.vm2.start_server()
        await self.vm3.start_server()
        await self.vm1.connect_to_neighbors()
        await self.vm2.connect_to_neighbors()
        await self.vm3.connect_to_neighbors()

        # Start the tick loops
        tick_task_1 = asyncio.create_task(self.vm1.tick_loop())
        tick_task_2 = asyncio.create_task(self.vm2.tick_loop())
        tick_task_3 = asyncio.create_task(self.vm3.tick_loop())
        await asyncio.sleep(0.5)  # allow tick loops to run

        # Send messages among them
        await self.vm1.send_message(2)
        await self.vm2.send_message(3)
        await self.vm3.send_message(1)

        # Let them process those messages
        await asyncio.sleep(1.0)

        # Cancel the loops
        for t in (tick_task_1, tick_task_2, tick_task_3):
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass

        # By now, all logical clocks should have incremented above 0
        self.assertGreater(self.vm1.logical_clock, 0, "vm1 clock did not increment after sending/receiving messages.")
        self.assertGreater(self.vm2.logical_clock, 0, "vm2 clock did not increment.")
        self.assertGreater(self.vm3.logical_clock, 0, "vm3 clock did not increment.")

    async def test_two_vms_send_to_third_after_it_shuts_down_raises_error(self):
        """
        1) Start all three VMs (so connect_to_neighbors doesn't get stuck).
        2) Connect them.
        3) Immediately shut down VM3 to simulate it disappearing.
        4) Remove references to VM3's writers from vm1 and vm2.
        5) Check that sends from vm1 or vm2 to vm3 now raise ValueError.
        """
        await self.vm1.start_server()
        await self.vm2.start_server()
        await self.vm3.start_server()
        await asyncio.gather(
            self.vm1.connect_to_neighbors(),
            self.vm2.connect_to_neighbors(),
            self.vm3.connect_to_neighbors()
        )

        # Shut down VM3's server
        if self.vm3.server_task:
            self.vm3.server_task.cancel()
            try:
                await self.vm3.server_task
            except asyncio.CancelledError:
                pass
        if self.vm3.server:
            self.vm3.server.close()
            await self.vm3.server.wait_closed()

        # Remove the neighbor-writer for 3 from vm1 and vm2
        # so that send_message(3) will see "writer is None" -> raise ValueError
        if 3 in self.vm1.neighbor_writers:
            del self.vm1.neighbor_writers[3]
        if 3 in self.vm2.neighbor_writers:
            del self.vm2.neighbor_writers[3]

        with self.assertRaises(ValueError) as ctx1:
            await self.vm1.send_message(3)
        self.assertIn("attempted to send a message to neighbor 3", str(ctx1.exception))

        with self.assertRaises(ValueError) as ctx2:
            await self.vm2.send_message(3)
        self.assertIn("attempted to send a message to neighbor 3", str(ctx2.exception))

    async def test_two_vms_running_one_missing_raises_error_in_tick_loop(self):
        """
        We want to run tick_loop on VM1 and VM2, with VM3 effectively “missing.”
        However, to avoid connect_to_neighbors from blocking forever, we do:
          1) Start all three (including VM3),
          2) Connect them,
          3) Immediately shut down VM3,
          4) Remove the neighbor writer for 3 from VM1 and VM2,
          5) Patch random.randint => 3 so that tick_loop tries 'event=3' => send to all neighbors => raises ValueError.
        """
        await self.vm1.start_server()
        await self.vm2.start_server()
        await self.vm3.start_server()
        await asyncio.gather(
            self.vm1.connect_to_neighbors(),
            self.vm2.connect_to_neighbors(),
            self.vm3.connect_to_neighbors()
        )

        # Shut down VM3
        if self.vm3.server_task:
            self.vm3.server_task.cancel()
            try:
                await self.vm3.server_task
            except asyncio.CancelledError:
                pass
        if self.vm3.server:
            self.vm3.server.close()
            await self.vm3.server.wait_closed()

        # Remove neighbor writer for 3 from VM1 and VM2 to force ValueError upon send
        if 3 in self.vm1.neighbor_writers:
            del self.vm1.neighbor_writers[3]
        if 3 in self.vm2.neighbor_writers:
            del self.vm2.neighbor_writers[3]

        # Patch random.randint => 3 so tick_loop tries sending to all neighbors
        # That means each will try send_message(3) -> raises ValueError
        with patch("random.randint", return_value=3):
            tick_task_1 = asyncio.create_task(self.vm1.tick_loop())
            tick_task_2 = asyncio.create_task(self.vm2.tick_loop())

            # We'll gather these tasks with a short timeout so we don't hang indefinitely
            # We expect ValueError to be raised as soon as the loop attempts event=3
            with self.assertRaises(ValueError) as ctx:
                await asyncio.wait_for(
                    asyncio.gather(tick_task_1, tick_task_2),
                    timeout=1.0
                )

            # Verify the exception message references neighbor 3
            self.assertIn("attempted to send a message to neighbor 3", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
