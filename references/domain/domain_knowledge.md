# Domain Knowledge Base — Gaming System Optimization & Input Latency Tuning

> Curated, citable domain knowledge used for RAG grounding of the agent
> harness. This file complements `SECOND-KNOWLEDGE-BRAIN.md` (which is
> auto-updated by the crawl pipeline) with stable, human-curated references
> and decision rules. Tier labels follow the evidence hierarchy defined in
> `references/prompts/system_base.md`.

---

## 1. Input Latency — Core Concepts

**End-to-end input latency** = click-to-photon time, the sum of:

```
sensor polling → OS USB stack → game thread → render queue → GPU → display scanout
```

| Component | Typical contribution | Tuning lever |
|-----------|----------------------|--------------|
| Mouse/KB polling | 1 ms @ 1000 Hz | Raise polling rate; lower USB interval. |
| OS USB stack | 0.5–1 ms | Timer resolution, interrupt coalescing. |
| Game thread | 2–16 ms | Max pre-rendered frames, Reflex. |
| Render queue | 1–4 frames | Reflex / Low Latency mode. |
| GPU render | frame-time dependent | Frame caps, GPU scheduling. |
| Display scanout | 1/refresh Hz | VRR, BFI, refresh rate, scan mode. |

**Key methods** (Tier 1/2 cited):
- NVIDIA Reflex (lowers render-queue latency) — Tier 2 (NVIDIA docs).
- Variable Refresh Rate (G-Sync/FreeSync) — Tier 2 (VESA / vendor docs).
- Black Frame Insertion (BFI) — Tier 3 (Blur Busters).
- High polling rate (1000–8000 Hz) — Tier 2/3 (vendor + Blur Busters).

---

## 2. CPU/GPU Scheduling — Decision Rules

- **Game Mode (Windows):** enable for foreground game prioritization. Tier 2
  (Microsoft Game Mode docs).
- **Power plan:** `High Performance` / `Ultimate Performance` for desktops;
  avoid on laptops unless thermals allow. Reversible.
- **HAGS (Hardware-Accelerated GPU Scheduling):** enable on Turing+ with
  driver ≥ 451.48; disable if stuttering observed. Tier 2 (NVIDIA WDDM).
- **CPU affinity/priority:** avoid manual affinity for modern games; use
  Process Lasso only for problematic titles. Tier 4.
- **Background services:** disable non-essential overlays/launchers during
  competitive play. Tier 3.

---

## 3. Memory & Storage — Decision Rules

- **XMP / EXPO:** enable the rated profile after a memory stability test
  (TM5 / Karhu). Reversible. Tier 2 (JEDEC / vendor).
- **NVMe vs SATA:** NVMe for the OS and the active game; SATA acceptable for
  bulk storage. Tier 2.
- **Page file:** leave system-managed on SSD; do not disable. Tier 2
  (Microsoft docs).
- **Standby memory:** trim only when leakage is observed (ISLC); not routine.
  Tier 3/4.

---

## 4. Monitoring — Required Metrics

- **Frame time (ms)** — distribution, not just average.
- **1% / 0.1% lows** — perceptible stutter severity.
- **Average FPS** — secondary to frame-time consistency.
- **End-to-end input latency** — NVIDIA Reflex Latency Analyzer or
  high-speed-camera methods. Tier 1 (research) / Tier 2 (vendor).

Tools: PresentMon, FrameView, CapFrameX, MSI Afterburner/RTSS.

---

## 5. Stability-vs-Gain Tradeoff Matrix

| Tweak | Expected gain | Risk | Reversible | Validation |
|-------|----------------|------|-----------|------------|
| Reflex On + Low latency | −5 to −20 ms | none | yes | benchmark |
| Max pre-rendered frames = 1 | −2 to −6 ms | stutter on weak CPU | yes | 30-min run |
| VRR + frame cap = refresh−3 | tear/stutter gone | input lag if VRR off | yes | visual |
| 1000 Hz polling | −0.5 ms | CPU load ↑ (negligible) | yes | n/a |
| 8000 Hz polling | −0.875 ms | CPU/interrupt contention | yes | stress test |
| HAGS On | varies | stutter on some titles | yes | per-game test |
| XMP/EXPO | +5–15% avg FPS | instability if not tested | yes | TM5 ≥ 3 cycles |
| Aggressive power plan | +3–8% | thermals/noise/laptop battery | yes | thermal monitor |
| Manual CPU affinity | rare | worse perf if wrong | yes | per-game |
| BFI On | blur reduction | brightness loss, flicker | yes | visual |

---

## 6. Citable Authoritative Sources (Tier 1/2)

| Source | Tier | Access |
|--------|------|--------|
| NVIDIA Reflex documentation | 2 | https://www.nvidia.com/reflex |
| Microsoft Game Mode / WDDM docs | 2 | https://learn.microsoft.com |
| VESA DisplayPort/VRR specs | 2 | https://vesa.org |
| Blur Busters (community reference) | 3 | https://blurbusters.com |
| IEEE TVCG (latency research) | 1 | DOI-cited |
| ACM CHI (input latency) | 1 | DOI-cited |
| Entertainment Computing (Elsevier) | 1 | DOI-cited |

---

## 7. Language Handling

- Detect Vietnamese via diacritics (`àáảãạăâđèéêìíòóôơùúưý`) and common words
  (`tối ưu`, `độ trễ`, `hệ thống`).
- Default to English when unclear; ask the user to confirm.
- Translate report section labels per the table in `skills/main.md`.

---

## 8. Knowledge-Gap Flagging

When the harness finds no Tier 1/2 source for a claim:
1. Flag the gap in the output (`[gap: <topic>]`).
2. Emit a `knowledge_lookup` tool call to query the knowledge brain.
3. If still missing, queue the topic for the crawl pipeline
   (`tools/knowledge_updater.py --keywords "<topic>"`).
