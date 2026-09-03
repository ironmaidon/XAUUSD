export type Volatility = {
  atm_iv: number | null; rv20: number | null; vrp: number | null; iv_percentile: number | null
  skew_25: number | null; term_ratio: number | null; iv_change_24h: number | null
  expected_move_usd: number | null
}

export type Snapshot = {
  status: {
    mode: 'BACKTEST' | 'REPLAY' | 'PAPER' | 'LIVE'; armed: boolean
    connection: 'CONNECTED' | 'DEGRADED' | 'DISCONNECTED'; credentials_connected: boolean; btc_price: number | null
    regime: string; entry_score: number; target_expiry: string | null; dte: number | null
    heartbeat_healthy: boolean; paper_trading_active: boolean; reconciliation_status: string; volatility: Volatility
    updated_at: string
  }
  candidate: {
    structure: string | null; strikes: number[]; deltas: number[]; net_credit: number | null
    wing_width: number | null; credit_ratio: number | null; max_loss: number | null
    risk_pct: number | null; quantity: number | null; entry_score: number; eligible: boolean
    reasons: string[]; score_components: Record<string, number>
  }
  risk: {
    account_equity_inr: number; available_funds_inr: number; trade_risk_pct: number
    open_defined_risk_pct: number; margin_usage_pct: number; daily_pnl: number; weekly_pnl: number
    current_drawdown_pct: number; maximum_drawdown_pct: number; consecutive_losses: number
    kill_switches: string[]
  }
  option_chain: Record<string, unknown>[]; positions: Record<string, unknown>[]
  orders: Record<string, unknown>[]; fills: Record<string, unknown>[]
  backtests: Record<string, unknown>[]; logs: Record<string, unknown>[]
  candles: { time: number; open: number; high: number; low: number; close: number }[]
}
