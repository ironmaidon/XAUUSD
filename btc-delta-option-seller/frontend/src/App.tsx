import { useEffect, useMemo, useState } from 'react'
import { Activity, BookOpen, CandlestickChart, ClipboardList, FileClock, Gauge, Logs, Settings, ShieldCheck, Wifi, WifiOff } from 'lucide-react'
import { connectDelta, getSnapshot, refreshBtcMarket, startPaperTrading } from './api'
import type { Snapshot } from './types'
import { PriceChart } from './PriceChart'

const routes = ['Overview', 'Option Chain', 'Strategy', 'Positions', 'Orders', 'Risk', 'Backtests', 'Settings', 'Logs'] as const
type Route = typeof routes[number]

const icons = [Activity, BookOpen, CandlestickChart, Gauge, ClipboardList, ShieldCheck, FileClock, Settings, Logs]

const empty: Snapshot = {
  status: { mode: 'PAPER', armed: false, connection: 'DISCONNECTED', credentials_connected: false, btc_price: null, regime: 'AMBIGUOUS', entry_score: 0, target_expiry: null, dte: null, heartbeat_healthy: false, paper_trading_active: false, reconciliation_status: 'NOT_REQUIRED_PAPER', updated_at: new Date().toISOString(), volatility: { atm_iv: null, rv20: null, vrp: null, iv_percentile: null, skew_25: null, term_ratio: null, iv_change_24h: null, expected_move_usd: null } },
  candidate: { structure: null, strikes: [], deltas: [], net_credit: null, wing_width: null, credit_ratio: null, max_loss: null, risk_pct: null, quantity: null, entry_score: 0, eligible: false, reasons: ['NO_EVALUATION'], score_components: {} },
  risk: { account_equity_inr: 0, available_funds_inr: 0, trade_risk_pct: 0, open_defined_risk_pct: 0, margin_usage_pct: 0, daily_pnl: 0, weekly_pnl: 0, current_drawdown_pct: 0, maximum_drawdown_pct: 0, consecutive_losses: 0, kill_switches: [] },
  option_chain: [], positions: [], orders: [], fills: [], backtests: [], logs: [], candles: [],
}

const number = (value: number | null, digits = 2) => value == null ? '—' : value.toLocaleString('en-IN', { maximumFractionDigits: digits })
const percent = (value: number | null) => value == null ? '—' : `${number(value, 2)}%`

function Metric({ label, value, tone }: { label: string; value: string; tone?: 'good' | 'warn' | 'bad' }) {
  return <div className={`metric ${tone ?? ''}`}><span>{label}</span><strong>{value}</strong></div>
}

function DataTable({ rows, emptyText }: { rows: Record<string, unknown>[]; emptyText: string }) {
  const columns = rows.length ? Object.keys(rows[0]).slice(0, 8) : []
  if (!rows.length) return <div className="empty"><div className="empty-ring" />{emptyText}</div>
  return <div className="table-wrap"><table><thead><tr>{columns.map(column => <th key={column}>{column.replaceAll('_', ' ')}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{columns.map(column => <td key={column}>{String(row[column] ?? '—')}</td>)}</tr>)}</tbody></table></div>
}

function Overview({ data }: { data: Snapshot }) {
  const v = data.status.volatility
  return <>
    <section className="metrics top-metrics">
      <Metric label="Mode" value={data.status.mode} tone="warn" />
      <Metric label="Arm status" value={data.status.armed ? 'ARMED' : 'DISARMED'} tone={data.status.armed ? 'bad' : 'good'} />
      <Metric label="Connection" value={data.status.connection} tone={data.status.connection === 'CONNECTED' ? 'good' : 'bad'} />
      <Metric label="BTC price" value={data.status.btc_price ? `$${number(data.status.btc_price, 0)}` : 'Awaiting feed'} />
      <Metric label="Regime" value={data.status.regime} />
      <Metric label="Entry score" value={`${number(data.status.entry_score, 0)} / 100`} />
      <Metric label="Target expiry" value={data.status.target_expiry ? new Date(data.status.target_expiry).toLocaleDateString('en-IN') : '—'} />
      <Metric label="DTE" value={number(data.status.dte, 1)} />
    </section>
    <div className="grid-main">
      <section className="panel chart-panel">
        <header><div><p className="eyebrow">BTCUSD · 4H</p><h2>Market structure</h2></div><span className="tag">Confirmed candles</span></header>
        <PriceChart candles={data.candles} />
      </section>
      <section className="panel candidate">
        <header><div><p className="eyebrow">Current evaluation</p><h2>Trade candidate</h2></div><span className={`decision ${data.candidate.eligible ? 'pass' : 'fail'}`}>{data.candidate.eligible ? 'PASS' : 'NO TRADE'}</span></header>
        <div className="candidate-name">{data.candidate.structure ?? 'No structure selected'}</div>
        <div className="candidate-grid"><Metric label="Net credit" value={number(data.candidate.net_credit)} /><Metric label="Max loss" value={number(data.candidate.max_loss)} /><Metric label="Quantity" value={number(data.candidate.quantity)} /><Metric label="Risk" value={percent(data.candidate.risk_pct)} /></div>
        <div className="reason"><span>Decision reason</span><strong>{data.candidate.reasons.join(' · ')}</strong></div>
      </section>
    </div>
    <section className="panel"><header><div><p className="eyebrow">Volatility surface</p><h2>Premium context</h2></div></header><div className="metrics vol-grid">
      <Metric label="ATM IV" value={percent(v.atm_iv == null ? null : v.atm_iv * 100)} /><Metric label="RV20" value={percent(v.rv20 == null ? null : v.rv20 * 100)} /><Metric label="VRP" value={number(v.vrp)} /><Metric label="IV percentile" value={percent(v.iv_percentile)} /><Metric label="25Δ skew" value={percent(v.skew_25)} /><Metric label="Term ratio" value={number(v.term_ratio)} /><Metric label="IV 24h change" value={percent(v.iv_change_24h)} /><Metric label="Expected move" value={v.expected_move_usd ? `$${number(v.expected_move_usd, 0)}` : '—'} />
    </div></section>
  </>
}

function RiskPage({ data }: { data: Snapshot }) {
  const r = data.risk
  return <section className="panel"><header><div><p className="eyebrow">Capital preservation</p><h2>Portfolio risk</h2></div><span className={`decision ${r.kill_switches.length ? 'fail' : 'pass'}`}>{r.kill_switches.length ? 'BREACH' : 'WITHIN LIMITS'}</span></header><div className="metrics risk-grid"><Metric label="Account equity" value={`₹${number(r.account_equity_inr, 0)}`} /><Metric label="Available funds" value={`₹${number(r.available_funds_inr, 0)}`} /><Metric label="Trade risk" value={percent(r.trade_risk_pct)} /><Metric label="Open defined risk" value={percent(r.open_defined_risk_pct)} /><Metric label="Margin usage" value={percent(r.margin_usage_pct)} /><Metric label="Daily P&L" value={`₹${number(r.daily_pnl, 0)}`} /><Metric label="Weekly P&L" value={`₹${number(r.weekly_pnl, 0)}`} /><Metric label="Current drawdown" value={percent(r.current_drawdown_pct)} /><Metric label="Max drawdown" value={percent(r.maximum_drawdown_pct)} /><Metric label="Consecutive losses" value={String(r.consecutive_losses)} /><Metric label="Heartbeat" value={data.status.heartbeat_healthy ? 'HEALTHY' : 'INACTIVE'} tone={data.status.heartbeat_healthy ? 'good' : 'warn'} /><Metric label="Reconciliation" value={data.status.reconciliation_status} /></div></section>
}

function SettingsPage({ data, onSnapshot }: { data: Snapshot; onSnapshot: (value: Snapshot) => void }) {
  const [environment, setEnvironment] = useState<'production' | 'testnet'>('production')
  const [apiKey, setApiKey] = useState('')
  const [apiSecret, setApiSecret] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('Credentials are kept in server memory only and are cleared on restart.')
  const connected = data.status.credentials_connected

  async function connect() {
    setBusy(true)
    try {
      const result = await connectDelta(environment, apiKey.trim(), apiSecret.trim())
      setApiKey(''); setApiSecret(''); setMessage(result.message)
      onSnapshot(await getSnapshot())
    } catch (reason) { setMessage(reason instanceof Error ? reason.message : 'Connection failed') }
    finally { setBusy(false) }
  }

  async function startPaper() {
    setBusy(true)
    try {
      const result = await startPaperTrading(); setMessage(result.message); onSnapshot(await getSnapshot())
    } catch (reason) { setMessage(reason instanceof Error ? reason.message : 'Could not start paper trading') }
    finally { setBusy(false) }
  }

  return <section className="panel settings-panel"><header><div><p className="eyebrow">Session-only configuration</p><h2>Delta Exchange connection</h2></div><span className={`decision ${connected ? 'pass' : 'fail'}`}>{connected ? 'CONNECTED' : 'NOT CONNECTED'}</span></header><div className="settings-form"><label>Environment<select value={environment} onChange={event => setEnvironment(event.target.value as 'production' | 'testnet')} disabled={busy}><option value="production">Delta India production</option><option value="testnet">Delta India testnet</option></select></label><label>API key<input type="password" autoComplete="off" value={apiKey} onChange={event => setApiKey(event.target.value)} placeholder="Enter API key" disabled={busy} /></label><label>API secret<input type="password" autoComplete="off" value={apiSecret} onChange={event => setApiSecret(event.target.value)} placeholder="Enter API secret" disabled={busy} /></label><div className="settings-actions"><button className="primary" onClick={connect} disabled={busy || !apiKey.trim() || !apiSecret}>{busy ? 'Working…' : 'Connect'}</button><button onClick={startPaper} disabled={busy || !connected || data.status.paper_trading_active}>{data.status.paper_trading_active ? 'Paper trading active' : 'Start paper trading'}</button></div></div><div className="notice"><ShieldCheck /> {message} Live orders cannot be armed from this dashboard.</div></section>
}

function App() {
  const [route, setRoute] = useState<Route>('Overview')
  const [data, setData] = useState<Snapshot>(empty)
  const [error, setError] = useState(false)
  useEffect(() => { const controller = new AbortController(); getSnapshot(controller.signal).then(value => { setData(value); setError(false) }).catch(() => setError(true)); return () => controller.abort() }, [])
  useEffect(() => {
    const controller = new AbortController()
    const refresh = () => refreshBtcMarket(controller.signal)
      .then(value => { setData(value); setError(false) })
      .catch(() => getSnapshot(controller.signal)
        .then(value => { setData(value); setError(false) })
        .catch(() => setError(true)))
    refresh()
    const interval = window.setInterval(refresh, 3000)
    return () => { controller.abort(); window.clearInterval(interval) }
  }, [])
  const content = useMemo(() => {
    if (route === 'Overview') return <Overview data={data} />
    if (route === 'Risk') return <RiskPage data={data} />
    const mapping: Partial<Record<Route, Record<string, unknown>[]>> = { 'Option Chain': data.option_chain, Positions: data.positions, Orders: data.orders, Backtests: data.backtests, Logs: data.logs }
    if (route === 'Strategy') return <section className="panel"><header><div><p className="eyebrow">Signal audit</p><h2>Strategy evaluation</h2></div></header><div className="reason"><span>Current decision</span><strong>{data.candidate.reasons.join(' · ')}</strong></div><div className="score-bars">{Object.entries(data.candidate.score_components).map(([name, score]) => <div key={name}><span>{name.replaceAll('_', ' ')}</span><div><i style={{ width: `${score}%` }} /></div><strong>{number(score)}</strong></div>)}</div></section>
    if (route === 'Settings') return <SettingsPage data={data} onSnapshot={setData} />
    return <section className="panel"><header><div><p className="eyebrow">{route}</p><h2>{route}</h2></div><span className="tag">Live updates</span></header><DataTable rows={mapping[route] ?? []} emptyText={`No ${route.toLowerCase()} available`} /></section>
  }, [route, data])
  return <div className="shell"><aside><div className="brand"><span className="brand-mark">Δ</span><div><strong>BTC Option Seller</strong><small>Delta India · V1</small></div></div><nav>{routes.map((item, index) => { const Icon = icons[index]; return <button key={item} className={route === item ? 'active' : ''} onClick={() => setRoute(item)}><Icon size={17} />{item}</button> })}</nav><div className="safety"><ShieldCheck size={18} /><div><strong>Defined risk only</strong><span>Live execution disabled</span></div></div></aside><main><header className="page-head"><div><p className="eyebrow">Operations console</p><h1>{route}</h1></div><div className="connection">{error ? <WifiOff size={16} /> : <Wifi size={16} />}<span>{error ? 'Backend offline' : 'Snapshot connected'}</span><i /></div></header>{error && <div className="api-warning">Dashboard backend is offline. Displaying safe empty state; no actions are available.</div>}{content}<footer>BTC Delta Exchange Option Seller V1 · Research software, not investment advice</footer></main></div>
}

export default App
