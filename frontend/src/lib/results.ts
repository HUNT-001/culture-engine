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
