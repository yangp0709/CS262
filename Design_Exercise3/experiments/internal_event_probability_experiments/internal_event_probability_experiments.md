# Analysis of Internal Event Probability Experiments

Each experiment was run with a different probability for a VM to choose an internal event when no messages are pending. These experiments are ran for 1 minute and have the average stats across 5 simulations for each experiment.

**Clarification:**  
- When a VM has a message in its queue, it always logs a **receive** event.  
- Only when the queue is empty does the VM decide between performing a **send** event or an **internal** event.  
- The _internal event probability_ is the chance that the VM chooses an **internal** event instead of a **send** event when the queue is empty.

In all experiments, three virtual machines (VMs) run at different tick rates:  
- **VM 1:** Tick rate 1 (slow)  
- **VM 2:** Tick rate 3 (medium)  
- **VM 3:** Tick rate 5 (fast)  

Below is an analysis for each internal event probability setting, followed by a comparative discussion.

---

## 25% Internal Event Probability (**25.txt**)

- **Total Events:**  
  - VM 1 (tick 1): ~60–61 events  
  - VM 2 (tick 3): ~181–198 events  
  - VM 3 (tick 5): ~364–383 events  

- **Average Clock Jump:**  
  - VM 1: ~2.2–2.5  
  - VM 2: ~1.81–2.11  
  - VM 3: Constant at 1.00

- **Maximum Clock Jump:**  
  - VM 1: Ranges from 8 up to 10  
  - VM 2: Between 6 and 8  
  - VM 3: Very low (1 or 2)

- **Maximum Queue Length:**  
  - VM 1: Very high (approximately 90–112)  
  - VM 2: Low (around 3–8)  
  - VM 3: Minimal (1–3)

- **Observations:**  
  With a 25% internal event probability, the slow VM (tick 1) processes few events relative to the faster VMs. Its low rate of choosing send/internal (when idle) combined with many receive events leads to moderate clock jumps but a very large message backlog. The medium and fast VMs remain efficient with nearly constant clock increments. With the lowest internal event probability of all experiments, the slow VM has the smallest average clock jump of all experiments, as a lower internal event probability allows more sends, giving the slow VM more chances to catch up to faster neighboring VMs.

---

## 40% Internal Event Probability (**40.txt**)

- **Total Events:**  
  - VM 1: ~60 events  
  - VM 2: ~189–199 events  
  - VM 3: ~350–360 events

- **Average Clock Jump:**  
  - VM 1: ~2.24–2.58  
  - VM 2: ~1.82–1.94  
  - VM 3: ~1.00–1.04

- **Maximum Clock Jump:**  
  - VM 1: Between 7 and 12  
  - VM 2: Mostly 6–8  
  - VM 3: Very low (1–4)

- **Maximum Queue Length:**  
  - VM 1: High (67–88)  
  - VM 2: Low (around 3)  
  - VM 3: Minimal (1–2)

- **Observations:**  
  Increasing the internal event probability to 40% slightly raises the average clock jump for the slow VM while keeping its total events nearly constant. The maximum queue lengths remain high for VM 1 but similar to the 25% case. VM 2 and VM 3 continue to exhibit steady and efficient processing. 

---

## 50% Internal Event Probability (**50.txt**)

- **Total Events:**  
  - VM 1: ~60–61 events  
  - VM 2: ~194–202 events  
  - VM 3: ~338–347 events

- **Average Clock Jump:**  
  - VM 1: ~2.64 to 2.97  
  - VM 2: Around 1.68–1.71  
  - VM 3: Constant at 1.00

- **Maximum Clock Jump:**  
  - VM 1: Approximately 8–13  
  - VM 2: Approximately 7–9  
  - VM 3: Remains at 1

- **Maximum Queue Length:**  
  - VM 1: Moderately lower than lower probabilities (around 56–72)  
  - VM 2: Remains low (around 3)  
  - VM 3: Low (1–4)

- **Observations:**  
  At 50% internal probability, VM 1 shows a noticeable increase in its average clock jump compared to lower probabilities. The fast VM continues to be highly efficient, and queue lengths for VM 1 decrease slightly relative to the 25%–40% settings.

---

## 70% Internal Event Probability (**70.txt**)

- **Total Events:**  
  - VM 1: ~60 events  
  - VM 2: ~190 events  
  - VM 3: ~328–333 events

- **Average Clock Jump:**  
  - VM 1: Increases to ~3.63–4.03  
  - VM 2: Around ~1.64–1.70  
  - VM 3: Steady at 1.00

- **Maximum Clock Jump:**  
  - VM 1: Increases significantly (8–18)  
  - VM 2: Ranges around 9–12  
  - VM 3: Remains very low (1)

- **Maximum Queue Length:**  
  - VM 1: Drops to much lower values (approximately 24–28)  
  - VM 2: Very low (around 2–4)  
  - VM 3: Minimal (1)

- **Observations:**  
  With a 70% probability, the slow VM processes nearly the same number of total events, but its average and maximum clock jumps increase markedly. The reduction in maximum queue length for VM 1 suggests that when internal events are favored, it clears its message backlog more frequently even though each clock update is larger.

---

## 80% Internal Event Probability (**80.txt**)

- **Total Events:**  
  - VM 1: ~60 events  
  - VM 2: ~192–196 events  
  - VM 3: ~313–321 events

- **Average Clock Jump:**  
  - VM 1: Further increases to ~4.90–5.17  
  - VM 2: Increases to ~1.53–1.65  
  - VM 3: Remains at ~1.00

- **Maximum Clock Jump:**  
  - VM 1: Peaks very high (up to 28–32)  
  - VM 2: Ranges between 12–19  
  - VM 3: Very low (1–1)

- **Maximum Queue Length:**  
  - VM 1: Drops dramatically (as low as 2–7)  
  - VM 2: Remains low (around 2)  
  - VM 3: Minimal (1–2)

- **Observations:**  
  At an 80% internal event probability, VM 1 exhibits the highest average and maximum clock jumps observed, indicating it is performing many internal events (when idle) before processing a receive event. With an increasing internal event probability, more internal events are performed by the faster VMs than the slower VMs, leading to a larger clock discrepancy between the fast and slow VMs. However, its maximum queue lengths are very low, suggesting that the frequent internal processing prevents message accumulation. The medium and fast VMs continue to show steady performance. 

---

## Comparative Analysis Across Experiments

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
  The slow VM (VM 1) experiences very high maximum queue lengths at lower internal event probabilities (up to 112 at 25%) but sees a dramatic reduction at higher probabilities (dropping to as low as 2–7 at 80%). This makes sense as when more send events are sent, the faster VMs will send more than the slow VMs and inundate the slow VM's message queues. The medium and fast VMs maintain low queue lengths across all experiments.

- **Overall Trends:**  
  - **Slow VM (Tick 1):** Highly sensitive to the internal event probability, showing increased clock jumps and reduced queue lengths at higher probabilities.  
  - **Medium VM (Tick 3):** Exhibits minor variations, with average clock jumps remaining stable and consistently low queue lengths.  
  - **Fast VM (Tick 5):** Largely unaffected by changes in internal event probability, maintaining a steady event rate, constant minimal clock jumps, and very short queues.

- **Main Conclusion about the Effect of Internal Event Probability**
  - The internal event probability appears to be a balance between a lower avg clock jump or a smaller message queue buildup for the slower VMs in a network. 
  
  - **High Internal Event Probability = Higher Avg Clock Jumps and Less Message Buildup for slower VMs:** Higher clock rate VMs do more internal events than slower VMs, so, in our logical clock implementation, a higher internal event probability leads to a larger discrepancy between slow and fast VMs and a higher avg clock jump for the slow VM. However, with less messages sent, the slower VMs have significantly less build up of messages in their queue. 
  
  - **Low Internal Event Probability = Lower Avg Clock Jumps and More Message Buildup for slower VMs:** Lower internal event probability leads to more sends, which gives slower VMs more chances to catch up ot faster neighboring VMs and, consequently, a lower avg clock jump. However, the faster VMs send messages significantly more than the slower VMs, causing slow VM message queues to be filled significantly more. 

  - **Cross-VM Drift:**  
  The average cross-VM drift (the difference in logical clock values between nearly simultaneous events) tends to decrease as the internal event probability increases. Lower drift at high probabilities implies that although the slow VM’s clock jumps are larger, they help it catch up with the fast VMs more quickly, reducing the temporal gap for near-simultaneous events.

---
