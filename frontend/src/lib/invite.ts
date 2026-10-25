// Invitation helpers. The invite is shared as text (plan ID + share code), never as a
// URL with the token embedded, so the credential never lands in a link, history, or logs.

export function cleanCode(raw: string): string {
  return raw.trim()
}

/** Plain-text invite the host can copy and send over a trusted channel. */
export function formatInviteText(planId: string, shareToken: string): string {
  return [
    'Join my Common Thread plan.',
    `Plan ID: ${planId}`,
    `Share code: ${shareToken}`,
    'Open the app, choose "Join a plan", and paste both. Keep the share code private.',
  ].join('\n')
}

/** Validate what a joiner pasted before calling the API. Returns human-readable errors. */
export function validateJoinInput(planId: string, shareToken: string): string[] {
  const errors: string[] = []
  if (!cleanCode(planId)) errors.push('Enter the Plan ID from your invite.')
  if (!cleanCode(shareToken)) errors.push('Enter the share code from your invite.')
  return errors
}

/** Hours remaining until expiry, floored at 0; null if the timestamp is unparseable. */
export function hoursUntil(expiresAtIso: string, now: Date = new Date()): number | null {
  const expires = Date.parse(expiresAtIso)
  if (Number.isNaN(expires)) return null
  return Math.max(0, Math.floor((expires - now.getTime()) / 3_600_000))
}

export function isExpired(expiresAtIso: string, now: Date = new Date()): boolean {
  const expires = Date.parse(expiresAtIso)
  if (Number.isNaN(expires)) return false
  return expires <= now.getTime()
}
