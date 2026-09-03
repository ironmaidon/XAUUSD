# Risk Model

The risk engine's non-negotiable invariant is that position quantity derives from maximum defined loss and account equity—not available margin.

M5 structures are intrinsically defined-risk: a vertical cannot be built without an outward protective wing, and an iron condor cannot be built without both wings. Leg ordering places protective buys before short sells for future execution-provider use.

## M6 sizing and limits

Maximum loss per contract is structure maximum loss × contract size × settlement conversion. Quantity is the exchange-step-rounded floor of account-equity risk budget divided by this maximum loss, capped by liquidity; available margin is never an input. A result below exchange minimum quantity is `NO_TRADE`.

New entries are blocked at the configured open-risk, daily-loss, weekly-loss, and structure-count limits. Drawdown and consecutive-full-stop triggers latch the kill switch. A healthy later snapshot cannot clear a latched switch; a future authenticated manual reset workflow is required.
