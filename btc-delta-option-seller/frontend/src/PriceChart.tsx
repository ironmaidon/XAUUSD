import { useEffect, useRef } from 'react'
import { CandlestickChart } from 'lucide-react'
import { CandlestickSeries, ColorType, createChart, type UTCTimestamp } from 'lightweight-charts'

type Candle = { time: number; open: number; high: number; low: number; close: number }

export function PriceChart({ candles }: { candles: Candle[] }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!ref.current || !candles.length) return
    const chart = createChart(ref.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: '#0b1115' }, textColor: '#71838c' },
      grid: { vertLines: { color: '#142027' }, horzLines: { color: '#142027' } },
      rightPriceScale: { borderColor: '#1c2930' },
      timeScale: { borderColor: '#1c2930', timeVisible: true },
    })
    const series = chart.addSeries(CandlestickSeries, { upColor: '#4dd6c8', downColor: '#f06969', borderVisible: false, wickUpColor: '#4dd6c8', wickDownColor: '#f06969' })
    series.setData(candles.map(item => ({ ...item, time: item.time as UTCTimestamp })))
    chart.timeScale().fitContent()
    return () => chart.remove()
  }, [candles])
  if (!candles.length) return <div className="chart-empty"><div className="pulse-line" /><CandlestickChart size={28} /><strong>Waiting for normalized candle stream</strong><span>EMA20, EMA50, swings and selected strikes will appear here.</span></div>
  return <div ref={ref} className="price-chart" aria-label="BTCUSD four hour candlestick chart" />
}
