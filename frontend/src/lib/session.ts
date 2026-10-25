// Session-scoped storage for plan credentials.
//
// Security decision: tokens are held in sessionStorage (cleared when the tab closes),
// never in the URL, query string, or logs. This keeps the share/participant tokens off
// disk and out of browser history. Trade-off: closing the tab ends the session, so to
// recover a plan later the user must re-enter the plan ID + share code they saved out of
// band. Persisting tokens in localStorage would survive a tab close but would leave live
// credentials on disk indefinitely, so we deliberately do not do that by default.

export type DeviceParticipant = {
  participantId: string
  participantToken: string
  displayName: string
}

export type DeviceSession = {
  planId: string
  shareToken: string
  participant?: DeviceParticipant
}

const KEY = 'common-thread.plan-session.v1'

function isSession(value: unknown): value is DeviceSession {
  if (!value || typeof value !== 'object') return false
  const v = value as Record<string, unknown>
  if (typeof v.planId !== 'string' || typeof v.shareToken !== 'string') return false
  if (v.participant !== undefined) {
    const p = v.participant as Record<string, unknown>
    if (!p || typeof p !== 'object') return false
    if (typeof p.participantId !== 'string' || typeof p.participantToken !== 'string' ||
        typeof p.displayName !== 'string') return false
  }
  return true
}

export function saveSession(session: DeviceSession): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(session))
  } catch {
    // Storage unavailable (private mode / disabled). Saving is best-effort.
  }
}

export function loadSession(): DeviceSession | null {
  let raw: string | null = null
  try {
    raw = sessionStorage.getItem(KEY)
  } catch {
    return null
  }
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as unknown
    return isSession(parsed) ? parsed : null
  } catch {
    return null
  }
}

export function clearSession(): void {
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    // ignore
  }
}
