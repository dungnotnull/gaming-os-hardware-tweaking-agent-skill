# Advisory Synthesis Prompt — Base Template

> Used by `sub-advisor`. Synthesizes prior steps into a risk-disclosed
> conclusion. Disclosure must precede the conclusion.

## Required Output Sections

1. **Disclosure / Limitations** (before the verdict).
2. **Verdict** — exactly one of:
   `Optimized & Stable | Conditional (risky tweaks) | Low-Performance Hardware | Inconclusive`.
3. **Scenarios** — Best / Base / Worst with quantitative ranges.
4. **Key Risks** — stability, thermals, compatibility, reversibility.
5. **Evidence Chain** — every claim → source (tier-labeled).
6. **Recommended Actions** — ordered, with magnitude + safety limits.
7. **Post-Execution Gate Checklist** — `U1✓ … G4 | Limitations: …`.

## Rules

- Never invent a verdict outside the four declared categories.
- If evidence is insufficient, emit `Inconclusive` and queue a knowledge gap.
