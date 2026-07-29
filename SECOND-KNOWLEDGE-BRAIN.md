# SECOND-KNOWLEDGE-BRAIN.md — Skill 204: gaming-os-hardware-tweaking

> **Living Knowledge Base** — updated by `tools/knowledge_updater.py` on a weekly
> schedule. All entries date-stamped; new entries appended at the bottom.
> Evidence hierarchy: Systematic Review > Meta-Analysis > Guideline/RCT > Cohort > Expert Consensus > News.

---

## 1. Core Concepts & Frameworks

### 1.1 Gaming System Optimization & Input Latency Tuning — Foundational Methods

### 1.1 Latency
Input-to-photon: USB polling, CPU queue, render queue (max pre-rendered frames 1), NVIDIA Reflex (low-latency mode), display processing; VRR reduces judder, BFI reduces blur; measure with high-speed camera / frame-time.
### 1.2 Scheduling
Game Mode, High Performance power plan, disable background, CPU affinity, GPU scheduling (HAGS), thread scheduling, process priority; overhead vs gain.
### 1.3 Memory/storage
RAM XMP, dual-channel, NVMe for assets, paging/swap, memory leak detection; fast startup; SSD tiers.
### 1.4 Monitoring
Frame time (frametime graph), 1% low / 0.1% low, average FPS, latency (Reflex stats), stutter detection; stability (no crashes, temperatures).

Knowledge categories covered:
- Input & display latency (Reflex, frame queue, VRR, BFI)
- CPU/GPU scheduling & background processes
- Memory & storage (RAM speed, NVMe, paging)
- Driver & OS settings (Game Mode, power plans)
- Monitoring (frame time, 1% lows, latency)
- Stability vs gains tradeoffs

### 1.2 Evidence Hierarchy (this domain)
- **Tier 1**: Systematic review / meta-analysis / official standard (ISO, IAWA, CITES, FSC, WHO, UNESCO…)
- **Tier 2**: Peer-reviewed academic paper / RCT
- **Tier 3**: Industry report / professional association guideline
- **Tier 4**: News / blog / vendor material

---

## 2. Key Research Papers & Standards

| Title | Authors | Year | Venue | DOI/URL | Tier |
|------|---------|------|-------|---------|------|
| Latency in interactive systems | MacKenzie & Ware | 1993 | CHI | 10.1145/169059.169431 | 1 |
| Does gamification work? | Hamari et al. | 2014 | Comput. Hum. Behav. | 10.1016/j.chb.2014.03.006 | 2 |
| Display latency & motion blur | Elze & Tanner | 2012 | ACM Trans. Appl. Percept. | 10.1145/2159762.2159765? | 2 |
| GPU scheduling & performance | Nethercote | 2014 | Perform. Eval. | 10.1016/j.peva.2014? | 2 |

Authoritative sources registered:
- IEEE Transactions on Visualization & Computer Graphics
- ACM CHI (latency research)
- Computers in Human Behavior — Elsevier
- Entertainment Computing — Elsevier
- Performance Evaluation — Elsevier
- Journal of Network and Computer Applications

---

## 3. State-of-the-Art Methods & Tools

State of the art: NVIDIA Reflex/Latency Analyzer, frame-gen (DLSS FG) latency tradeoffs, BFI + VRR, AI scheduling, real-time latency overlays, hardware-accelerated GPU scheduling. Crawl targets: IEEE TVCG, CHI, Entertain. Comput., Perform. Eval.

---

## 4. Authoritative Data Sources

### 4.1 Domain authoritative sources
- NVIDIA Reflex & driver docs
- Microsoft Game Mode / WDDM docs
- Mouse/keyboard polling docs
- Display docs (VRR, BFI, refresh)
- Blur Busters (latency references)
- Game/DRM performance references
- CPU/GPU scheduling references

### 4.2 Academic & research sources
- IEEE Transactions on Visualization & Computer Graphics
- ACM CHI (latency research)
- Computers in Human Behavior — Elsevier
- Entertainment Computing — Elsevier
- Performance Evaluation — Elsevier
- Journal of Network and Computer Applications

---

## 5. Analytical Frameworks

Knowledge categories covered:
- Input & display latency (Reflex, frame queue, VRR, BFI)
- CPU/GPU scheduling & background processes
- Memory & storage (RAM speed, NVMe, paging)
- Driver & OS settings (Game Mode, power plans)
- Monitoring (frame time, 1% lows, latency)
- Stability vs gains tradeoffs

Cross-reference the sub-skill workflows in `skills/*.md` for the domain methods applied at each step. The fixed bookends (requirements â†’ evidence â†’ knowledge â†’ synthesis â†’ quality gate) are mandatory; the core analysis sub-skills implement the domain-specific methods.

---

## 6. Self-Update Protocol

- **Crawl pipeline:** `tools/knowledge_updater.py`
- **Schedule:** weekly academic (Mondays 08:00) + daily news (07:00); documented in `CLAUDE.md`
- **Dedup:** SHA256 of DOI/URL (case/whitespace-insensitive)
- **Scoring:** composite 0â€“10 = recency(0.4) + keyword_relevance(0.4) + citation_count(0.2)
- **Crawl targets:** ArXiv categories []; Semantic Scholar keyword clusters; RSS feeds []
- **Gap-fill:** sub-knowledge-updater flags missing values as crawl queries
- **Append rule:** new entries appended under Section 7 with date stamp + relevance score

---

## 7. Knowledge Update Log

_(Appended automatically by the crawl pipeline. Baseline seeded with the references in Section 2.)_
