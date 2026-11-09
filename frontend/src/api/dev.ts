import { API_BASE } from '../config'

/** Dev tools (DEV_TOOLS): the simulated clock and the demo reset (spec §14). */

export interface ClockState {
  now: string
  offset_hours: number
  simulated: boolean
  timezone: string
}

export interface TickResult {
  clock: ClockState
  raised: number
  sent: number
  resolved: number
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${path} failed (${res.status})`)
  return res.json() as Promise<T>
}

export async function getClock(): Promise<ClockState> {
  const res = await fetch(`${API_BASE}/api/dev/clock`)
  if (!res.ok) throw new Error(`clock failed (${res.status})`)
  return res.json() as Promise<ClockState>
}

export function advanceClock(hours: number): Promise<TickResult> {
  return post<TickResult>('/api/dev/clock/advance', { hours })
}

export function clockToMorning(): Promise<TickResult> {
  return post<TickResult>('/api/dev/clock/to-morning')
}

export function resetDemo(): Promise<{ reset: boolean }> {
  return post<{ reset: boolean }>('/api/dev/reset')
}

/** Day R5: the seeded demo cases (DEMO_SEED), with the reviewers who act on each. */
export interface DemoCase {
  key: string
  title: string
  reference: string
  status: string
  first_reviewer: string | null
  final_reviewer: string | null
}

export async function listDemoCases(): Promise<DemoCase[]> {
  const res = await fetch(`${API_BASE}/api/dev/demo-cases`)
  if (!res.ok) throw new Error(`demo cases failed (${res.status})`)
  return res.json() as Promise<DemoCase[]>
}
