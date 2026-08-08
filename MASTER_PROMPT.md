# XAUUSD Strategy Development Contract

## Language

Pine Script v6.

## Final Output

One production-ready Strategy.pine file.

## Non-negotiable engineering rules

- Strategy.pine must compile after every milestone.
- No pseudocode.
- No placeholder implementations for milestone functionality.
- No repainting.
- No lookahead.
- All request.security() calls must explicitly use barmerge.lookahead_off.
- Functions must not modify persistent global variables.
- Functions calculate/return state; main execution scope updates persistent state.
- Variables that may contain na must have explicit types.
- Avoid duplicate declarations.
- Do not shadow enum names.
- Every persistent state variable has exactly one owning milestone.
- Preserve previous milestone behavior.
- Do not implement future milestones early.
- Reuse calculations from earlier modules instead of duplicating them.
- Keep drawing objects and arrays bounded.
- Prefer deterministic trading rules over subjective definitions.
- Update semantic version and changelog after every milestone.

## Frozen roadmap

M1 — Core Framework
M2 — Session & Opening Range Engine
M3 — Trend Engine
M4 — Breakout Engine
M5 — Retest Engine
M6 — Smart Money Engine
M7 — Trade Scoring Engine
M8 — Risk Management
M9 — Trade Management
M10 — Dashboard
M11 — Alerts
M12 — Final Integration, Optimization & Documentation

## State ownership

M1: Core configuration and infrastructure.

M2: Session and Opening Range state.

M3: Trend and market-structure state.

M4: Breakout state.

M5: Retest state.

M6: Smart Money / liquidity-context state.

M7: Final trade-scoring state.

M8: Risk state.

M9: Position/trade-management state.

M10: Dashboard presentation only.

M11: Alert infrastructure.

M12: Integration, optimization and documentation.

Do not change this roadmap unless explicitly instructed by the project owner.
