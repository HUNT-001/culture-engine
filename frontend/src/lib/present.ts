// Pure presentation helpers. They only reshape values the backend already returned
// (type labels, initials, score bars); they never invent or infer data.

/** "urn:entity:artist" -> "Artist", "urn:tag:genre:media" -> "Tag · Genre media". */
export function friendlyType(entityType?: string | null): string | null {
  if (!entityType) return null
  const raw = entityType.trim()
  if (!raw || raw.toLowerCase() === 'unknown') return null
  const words = (s: string) => s.replace(/[:_-]+/g, ' ').trim()
  const capitalise = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s)
  if (raw.startsWith('urn:tag:')) return `Tag · ${capitalise(words(raw.slice('urn:tag:'.length)))}`
  if (raw.startsWith('urn:entity:')) return capitalise(words(raw.slice('urn:entity:'.length)))
  return capitalise(words(raw))
}

/** Up to two initials for an avatar; "?" when there is no usable name. */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return Array.from(parts[0])[0].toUpperCase()
  return (Array.from(parts[0])[0] + Array.from(parts[parts.length - 1])[0]).toUpperCase()
}

/** A 0–1 score as a 0–100 bar width, or null when the value is absent / not a finite number. */
export function barPercent(value: number | null | undefined): number | null {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null
  return Math.round(Math.min(1, Math.max(0, value)) * 100)
}

/** One flag per participant: true where that participant's results include the option. */
export function coverageDots(covered: number, total: number): boolean[] {
  const size = Math.max(total, covered, 0)
  const filled = Math.min(Math.max(covered, 0), size)
  return Array.from({ length: size }, (_, i) => i < filled)
}
