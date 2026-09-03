import type { Snapshot } from './types'

export async function getSnapshot(signal?: AbortSignal): Promise<Snapshot> {
  const response = await fetch('/api/snapshot', { signal })
  if (!response.ok) throw new Error(`Dashboard API returned ${response.status}`)
  return response.json() as Promise<Snapshot>
}

type Environment = 'production' | 'testnet'

async function post<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method: 'POST',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const payload = await response.json() as { detail?: string }
  if (!response.ok) throw new Error(payload.detail ?? `Dashboard API returned ${response.status}`)
  return payload as T
}

export function connectDelta(environment: Environment, apiKey: string, apiSecret: string) {
  return post<{ connected: boolean; message: string }>('/api/settings/connect', {
    environment, api_key: apiKey, api_secret: apiSecret,
  })
}

export function startPaperTrading() {
  return post<{ active: boolean; message: string }>('/api/paper/start')
}
