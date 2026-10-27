// Pure helpers for presenting recommendation results. No invented data: every
// function reads only what the backend returned.
import type { RecommendationOption, RecommendationResponse } from '../types'

export const OPTION_NAMES: Record<string, string> = {
  shared_ground: 'Shared Ground',
  cultural_bridge: 'Cultural Bridge',
  stretch_choice: 'Stretch Choice',
  alternative: 'Alternative',
}

export function optionName(optionType: string): string {
  return OPTION_NAMES[optionType] ?? 'Alternative'
}

/** True when results came from the live Qloo API rather than the mock provider. */
export function isLive(result: Pick<RecommendationResponse, 'demo_mode'>): boolean {
  return result.demo_mode === false
}

export type SourceBadge = { live: boolean; label: string; detail: string }

export function sourceBadge(result: Pick<RecommendationResponse, 'demo_mode'>): SourceBadge {
  if (isLive(result)) {
    return {
      live: true,
      label: 'Live Qloo',
      detail: 'These venues and affinity signals come from the live Qloo API.',
    }
  }
  return {
    live: false,
    label: 'Demo / mock',
    detail: 'Synthetic demo data — these are not real venues or real Qloo signals.',
  }
}

/** Format a 0–1 score to 2 d.p., or null when the value is absent/invalid. */
export function formatScore(value: number | null | undefined): string | null {
  if (typeof value !== 'number' || Number.isNaN(value)) return null
  return value.toFixed(2)
}

export function hasRecommendations(result: RecommendationResponse): boolean {
  return Array.isArray(result.options) && result.options.length > 0
}

export function coverageText(option: RecommendationOption, participantCount: number): string {
  const covered = option.candidate.group_coverage
  const suffix = covered === 1 ? '' : 's'
  if (participantCount > 0) {
    return `Appears in ${covered}/${participantCount} participant result set${suffix}`
  }
  return `Appears in ${covered} participant result set${suffix}`
}

export type ConfirmationGroup = { name: string; terms: string[] }

/** Interests left out of the run for lack of an explicit entity confirmation, grouped by
 *  person. Reads `needs_confirmation`; falls back to the older "Name: term" strings so a
 *  run saved before that field existed still explains itself. */
export function confirmationGroups(
  result: Pick<RecommendationResponse, 'needs_confirmation' | 'unresolved_interests'>,
): ConfirmationGroup[] {
  const groups = new Map<string, string[]>()
  const add = (name: string, term: string) => groups.set(name, [...(groups.get(name) ?? []), term])
  const structured = result.needs_confirmation ?? []
  if (structured.length > 0) {
    for (const item of structured) add(item.display_name, item.text)
  } else {
    for (const line of result.unresolved_interests ?? []) {
      const at = line.indexOf(': ')
      if (at > 0) add(line.slice(0, at), line.slice(at + 2))
      else add('', line)
    }
  }
  return [...groups].map(([name, terms]) => ({ name, terms }))
}

export type StatusNotice = { tone: 'partial' | 'failed'; title: string; detail: string }

/** A visible notice whenever a run is not a complete success; null only for a complete run
 *  that left nothing out. */
export function statusNotice(result: RecommendationResponse): StatusNotice | null {
  const left = confirmationGroups(result).length > 0
  if (!hasRecommendations(result) || result.status === 'failed') {
    return {
      tone: 'failed',
      title: 'No recommendations',
      detail: left
        ? 'Nothing could be recommended because the interests below were not confirmed to a specific Qloo entity.'
        : 'The backend returned no usable options.',
    }
  }
  if (result.status === 'partial' || left) {
    return {
      tone: 'partial',
      title: 'Partial result',
      detail: left
        ? 'Some interests were left out because they were not confirmed, so this does not reflect everyone\u2019s full tastes.'
        : 'Fewer than three distinct options were found.',
    }
  }
  return null
}
