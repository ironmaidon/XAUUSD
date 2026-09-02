import type { Snapshot } from './types'

export async function getSnapshot(signal?: AbortSignal): Promise<Snapshot> {
  const response = await fetch('/api/snapshot', { signal })
  if (!response.ok) throw new Error(`Dashboard API returned ${response.status}`)
  return response.json() as Promise<Snapshot>
}
