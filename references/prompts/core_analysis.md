# Core Analysis Prompt — Base Template

> Used by `sub-core-analysis`. Produces the OS/hardware tweak plan with
> stability-vs-gain tradeoffs.

## Required Sub-Analyses

1. **Hardware profile** — CPU/GPU/RAM/storage/display/peripherals + target game.
2. **Input latency** — NVIDIA Reflex, max pre-rendered frames, VRR/G-Sync,
   BFI, polling rate, USB refresh interval, HPET/Timer resolution.
3. **CPU/GPU scheduling** — Game Mode, High-Performance power plan, background
   services, CPU affinity/priority, GPU scheduling (HAGS).
4. **Memory/storage** — XMP/EXPO profile, NVMe over SATA, page file sizing,
   standby memory trimming.
5. **Monitoring** — frame time, 1% / 0.1% lows, end-to-end input latency
   (PresentMon, FrameView, NVIDIA Reflex Latency Analyzer).
6. **Scenarios** — Best / Base / Worst FPS & latency with stability notes.

## Output

```
GAMING SYSTEM TWEAKS
- Hardware & target game: [...]
- Input latency: [Reflex, pre-render, VRR, BFI, polling]
- CPU/GPU scheduling: [Game Mode, power plan, background, affinity]
- Memory/storage: [XMP, NVMe, paging]
- Monitoring: [frame time, 1% lows, latency]
- Scenarios: Best / Base / Worst (FPS / latency, stability)
```

## Tradeoff Discipline

For every tweak, state: expected gain, risk, reversibility, and a 30-minute
stability validation step.
