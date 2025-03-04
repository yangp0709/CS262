# Experiment Analyses for the Asynchronous Distributed System

Below is a analysis of each experiment based on the clock‐rate settings. Each experiment corresponds to a .txt file in clock_rate_experiments, where the name of the .txt file is the combination of VM clock rates. These experiments are ran for 1 minute, are standardized to run with the default internal event probability of 70%, have the stats for SEND + INTERNAL vs. RECEIVE from the first simulation listed below, and have the average stats across 5 simulations for each experiment.

---

## Experiment Analyses

### 1. Uniform Threes (**3_3_3.txt**)
- **Setup:** All three virtual machines run at a clock rate of 3 ticks per second.
- **Total Events:** Each VM processes roughly 190–194 events per run.
- **Average Clock Jump:** Very low (around 1.03–1.04), meaning that logical clock increments are mostly steady.
- **Maximum Clock Jump:** Between 2 and 3 (occasionally 4), indicating minimal variation.
- **Maximum Queue Length:** Ranges between 2 and 4.
- **SEND + INTERNAL vs. RECEIVE:**  
  - **VM 1:** 137 SEND + INTERNAL events vs. 55 RECEIVE events  
  - **VM 2:** 142 vs. 50  
  - **VM 3:** 141 vs. 53  
  In this balanced scenario, the active events (SEND + INTERNAL) are roughly 2.6–2.8 times the RECEIVE events, which keeps the message queues short and the clock updates minimal.
  
*Conclusion:* With uniform medium speed and balanced event generation, the system is balanced. All VMs perform a similar number of operations, and the ratio of generated events to received messages keeps queue lengths short and clock increments steady.

---

### 2. Uniform Ones (**1_1_1.txt**)
- **Setup:** All VMs run slowly with a tick rate of 1.
- **Total Events:** Total event counts are much lower (about 63–67 events per run) compared to faster machines.
- **Average Clock Jump:** Slightly higher (around 1.06–1.18) but still modest.
- **Maximum Clock Jump:** Limited to a value of 2.
- **Maximum Queue Length:** Almost negligible (0–1), as the slow pace gives ample time for message processing.
- **SEND + INTERNAL vs. RECEIVE:**  
  - **VM 1:** 47 SEND + INTERNAL events vs. 17 RECEIVE events  
  - **VM 2:** 45 vs. 19  
  - **VM 3:** 52 vs. 14  
  The lower overall event counts maintain balanced ratios and very short queues, ensuring that even though the SEND + INTERNAL numbers are low, they are sufficient to process incoming messages promptly.

  
*Conclusion:* When all VMs are slow, the overall event load is light, and message queues remain short. The slight increase in average clock jump is consistent with the low frequency of events.

---

### 3. Minor Variation (**1_1_3.txt**)
- **Setup:** Two VMs run at 1 tick per second and one at 3.
- **Total Events:** The slow (tick 1) VMs process around 60 events per run, while the faster (tick 3) VM handles nearly 190–200 events.
- **Average Clock Jump:** Slow VMs exhibit much larger average jumps (around 3.1–3.25), compared to a steady jump of 1.00 in the faster VM.
- **Maximum Clock Jump:** The slow VMs sometimes show jumps as high as 10–19; the fast VM remains almost constant (max jump of 1).
- **Maximum Queue Length:** Slow VMs occasionally have queue lengths up to 2–3, reflecting a backlog from receiving messages from the faster machine.
- **SEND + INTERNAL vs. RECEIVE:**  
  - **VM 1 (tick 1):** 21 SEND + INTERNAL vs. 40 RECEIVE events  
  - **VM 2 (tick 1):** 24 vs. 38  
  - **VM 3 (tick 3):** 190 vs. 7  
  Here the slow VMs generate very few active events while receiving many messages (ratio less than 1:1), causing moderate queue buildups and forcing larger clock jumps when they process their backlog. In contrast, the fast VM sends actively (190 vs. only 7 receives) since it rarely receives messages due to the other two machines always reading and never sending. This keeps the fast VM's clock stable.
  
*Conclusion:* In this mixed setting, the disparity is clear. The slow machines lag behind—accumulating a backlog that forces larger clock jumps—while the faster machine, generating many events, maintains minimal clock variation.

---

### 4. Mixed Extremes (**1_1_6.txt**)
- **Setup:** Two VMs are very slow (tick 1) and one is very fast (tick 6).
- **Total Events:** Slow VMs record roughly 60 events, whereas the fast VM logs around 390–410 events.
- **Average Clock Jump:** Slow VMs show very high average jumps (ranging from about 4.4 to over 6), while the fast VM maintains a near-constant jump of 1.00.
- **Maximum Clock Jump:** The slow machines experience extreme jumps (max values up to 20–28), reflecting abrupt updates when they finally process their backlog.
- **Maximum Queue Length:** Slow VMs have substantially higher queue lengths (from 9 up to 33), as they are quickly overwhelmed by incoming messages.
- **SEND + INTERNAL vs. RECEIVE:**  
  - **VM 1 (tick 1):** 2 SEND + INTERNAL vs. 58 RECEIVE events  
  - **VM 2 (tick 1):** 1 vs. 59  
  - **VM 3 (tick 6):** 397 vs. 0  
  The fast VM is extremely active, generating 397 events and receiving no messages in return, while the slow VMs are flooded with 58–59 RECEIVE events but generate almost no active events. This dramatic imbalance causes the slow VMs to have very long queues and, when they do process the backlog, to experience huge clock jumps.

  
*Conclusion:* This “Mixed Extremes” scenario starkly illustrates how a high-speed machine can inundate slower ones. The imbalance between generated and received events in slow VMs leads to large clock adjustments and significant queue buildup, while the fast VM remains efficient and steady.

---

### 5. Low Dominant, Middle Majority (**1_3_3.txt**)
- **Setup:** One slow VM (tick 1) and two VMs with a moderate rate (tick 3).
- **Total Events:** The slow VM’s event count is around 60, whereas the moderate VMs handle close to 190–200 events.
- **Average Clock Jump:** The slow VM’s average jump is around 3–3.3, while the moderate VMs are near 1.03–1.07.
- **Maximum Clock Jump:** The slow machine occasionally jumps as high as 10–13, compared to a maximum of about 3–4 in the moderate machines.
- **Maximum Queue Length:** The slow VM can reach up to 6 (or even 14 in some runs), while the moderate ones generally keep queues at 1–2.
- **SEND + INTERNAL vs. RECEIVE:**  
  - **VM 1 (tick 1):** 2 SEND + INTERNAL vs. 58 RECEIVE events  
  - **VM 2 (tick 3):** 149 vs. 43  
  - **VM 3 (tick 3):** 176 vs. 20  
  The slow VM’s extremely low number of active events (only 2) versus a high number of RECEIVE events (58) forces a heavy message backlog and erratic clock adjustments. In contrast, the moderate VMs maintain a better balance, which results in smaller queues and steadier clocks.
  
*Conclusion:* With one low-speed machine among moderate-speed peers, the slower VM lags and shows a larger, more erratic clock progression due to a high ratio of RECEIVE events to its own event generation. The moderate machines, however, maintain a balanced ratio, leading to efficient processing.

---

### 6. Ascending Order (**1_3_5.txt**)
- **Setup:** A gradient of speeds: one VM at tick 1, one at tick 3, and one at tick 5.
- **Total Events:** The fastest (tick 5) processes around 320–330 events, the moderate (tick 3) around 190–200, and the slow (tick 1) about 60.
- **Average Clock Jump:** The slow VM shows average jumps in the 3.8–4.0 range, the moderate one a bit higher (around 1.6–1.7), and the fastest remains stable at 1.00.
- **Maximum Clock Jump:** The slow VM reaches maximum jumps between 14 and 21, the moderate machine shows up to around 10–12, while the fastest has almost no jumps (max of 1).
- **Maximum Queue Length:** The slow machine can accumulate very high queues (up to 24–28), while the other VMs keep theirs low.
- **SEND + INTERNAL vs. RECEIVE:**  
  - **VM 1 (tick 1):** 1 SEND + INTERNAL vs. 59 RECEIVE events  
  - **VM 2 (tick 3):** 138 vs. 52  
  - **VM 3 (tick 5):** 302 vs. 26  
  The slow VM’s nearly negligible active event generation (only 1) compared to 59 receives results in a huge imbalance and long queue lengths, leading to large clock jumps. The moderate and fast VMs show more balanced ratios, which helps them process messages without significant backlog.
  
*Conclusion:* This setup clearly demonstrates a speed gradient. The faster machines not only process more events but also maintain very steady clock updates, while the slow VM is overwhelmed—resulting in larger clock adjustments and significantly longer message queues as shown by the slow VM's high ration of RECEIVE to SEND + INTERNAL events.

---

### 7. Low vs High (**1_6_6.txt**)
- **Setup:** One very slow VM (tick 1) and two very fast VMs (tick 6).
- **Total Events:** The slow VM logs around 60 events, and the fast VMs each log approximately 390–400 events.
- **Average Clock Jump:** Slow VMs average jumps around 3–3.5, whereas fast VMs remain near 1.02–1.04.
- **Maximum Clock Jump:** The slow machine sometimes jumps dramatically (up to 12 or more), while the fast ones are capped at around 3–4.
- **Maximum Queue Length:** The slow VM faces extremely high queues (in some runs, up to 64–76), while the fast VMs maintain very short queues (mostly 2–3).
- **SEND + INTERNAL vs. RECEIVE:**  
  - **VM 1 (tick 1):** 1 SEND + INTERNAL vs. 59 RECEIVE events  
  - **VM 2 (tick 6):** 350 vs. 52  
  - **VM 3 (tick 6):** 322 vs. 69  
  The slow VM is overwhelmed with 59 RECEIVE events and generates almost no active events, while the fast VMs maintain a high level of active event generation. This imbalance creates huge queues in the slow VM, forcing dramatic clock jumps when it processes the backlog.
  
*Conclusion:* The disparity here is even more pronounced. The fast VMs process events rapidly and steadily, while the slow VM becomes a bottleneck, reflected by large clock jumps and heavy queuing.

---

### 8. Uniform Sixes (**6_6_6.txt**)
- **Setup:** All three VMs run at the maximum tick rate of 6.
- **Total Events:** Each VM processes a very high number of events—roughly 380–390 per run.
- **Average Clock Jump:** All VMs have very stable and low average jumps (around 1.05–1.07).
- **Maximum Clock Jump:** Maximum jumps are only slightly higher, typically in the 4–8 range.
- **Maximum Queue Length:** Queues remain very short (1–7), indicating efficient processing.
- **SEND + INTERNAL vs. RECEIVE:**  
  - **VM 1:** 289 SEND + INTERNAL vs. 97 RECEIVE events  
  - **VM 2:** 281 vs. 102  
  - **VM 3:** 278 vs. 104  
  In this balanced, high-speed scenario, each VM generates roughly 2.8–2.9 times as many active events as it receives, which keeps message queues minimal and clock adjustments steady.
  
*Conclusion:* When all machines are fast and balanced, the ratio of active event generation to incoming messages is nearly equal across VMs. This leads to efficient processing, minimal queue buildup, and stable logical clock behavior.

---

## Comparative Analysis Across Experiments

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


