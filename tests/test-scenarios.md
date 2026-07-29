# test-scenarios.md — Skill 204: gaming-os-hardware-tweaking

Five concrete end-to-end scenarios. Each lists inputs, expected steps, and applicable quality gates. The scenarios exercise all universal gates U1–U6 and the domain gates G1, G2, G3, G4, plus all verdict categories.

---

## Scenario 1: Standard analysis (object in scope)
- **Input:** a typical Gaming System Optimization & Input Latency Tuning case with complete inputs.
- **Expected:** sub-gather-requirements → sub-evidence-collector → sub-core-analysis → sub-knowledge-updater → sub-advisor → quality gate.
- **Gates:** U1–U6 + G1, G2, G3, G4.
- **Verdict target:** Optimized & Stable.

## Scenario 2: Minimal-input analysis (defaults)
- **Input:** terse request with minimal data.
- **Expected:** defaults applied with explicit assumption statement; never fabricate missing values.

## Scenario 3: Comparison scenario
- **Input:** compare two objects/cases within the domain.
- **Expected:** side-by-side scorecard + evidence-based winner; sub-core-analysis applied to both.
- **Gates:** U3 (evidence hierarchy), U6, G1, G.

## Scenario 4: Risk / feasibility or conflict scenario
- **Input:** assess risk of a borderline case, or resolve conflicting signals/actions.
- **Expected:** multi-scenario (best/base/worst) risk output with stated precedence where conflicts exist.
- **Gates:** U2 (disclosure), G1, G2, G3, G4.

## Scenario 5: Degraded-mode scenario
- **Input:** primary sources unreachable OR a required input variable missing.
- **Expected:** fallback chain + LIMITATION notice (degradation Level 2–3); no fabricated values; verdict maps to Inconclusive when the missing input is decisive.
- **Gates:** U2, graceful-degradation levels, G1, G2, G3, G4.

### Gate coverage matrix

| Gate | S1 | S2 | S3 | S4 | S5 |
|------|----|----|----|----|----|
| G1 | ✓ | ✓ | ✓ | ✓ | ✓ |
| G2 | ✓ | ✓ | ✓ | ✓ | ✓ |
| G3 | ✓ | ✓ | ✓ | ✓ | ✓ |
| G4 | ✓ | ✓ | ✓ | ✓ | ✓ |
| U1–U6 | ✓ | ✓ | ✓ | ✓ | ✓ |

### Verdict coverage
Optimized & Stable, Conditional (risky tweaks), Low-Performance Hardware, Inconclusive.
