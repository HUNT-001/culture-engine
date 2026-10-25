import { describe, expect, it } from 'vitest'
import type { RecommendationOption, RecommendationResponse } from '../types'
import {
  coverageText, formatScore, hasRecommendations, isLive, optionName, sourceBadge,
} from './results'

function option(partial: Partial<RecommendationOption['candidate']> = {}): RecommendationOption {
  return {
    option_type: 'shared_ground',
    title: 'Shared Ground',
    explanation: 'x',
    evidence_labels: [],
    candidate: {
      entity_id: 'e1', name: 'Place', entity_type: 'urn:entity:place', source: 'qloo',
      participant_ranks: {}, verification_status: 'unverified', rank_score: 0.5, group_coverage: 2,
      reasons: [], ...partial,
    },
  }
}

function response(partial: Partial<RecommendationResponse> = {}): RecommendationResponse {
  return {
    run_id: 'r1', demo_mode: false, location: 'Austin', options: [option()],
    warnings: [], unresolved_interests: [], status: 'complete', ...partial,
  }
}

describe('live vs mock distinction', () => {
  it('isLive is true only when demo_mode is false', () => {
    expect(isLive({ demo_mode: false })).toBe(true)
    expect(isLive({ demo_mode: true })).toBe(false)
  })
  it('sourceBadge labels live and demo distinctly', () => {
    expect(sourceBadge({ demo_mode: false })).toMatchObject({ live: true, label: 'Live Qloo' })
    expect(sourceBadge({ demo_mode: true })).toMatchObject({ live: false, label: 'Demo / mock' })
  })
})

describe('formatScore', () => {
  it('formats numbers to two decimals', () => {
    expect(formatScore(0.8798)).toBe('0.88')
    expect(formatScore(1)).toBe('1.00')
  })
  it('returns null for missing/invalid values (never invents a score)', () => {
    expect(formatScore(null)).toBeNull()
    expect(formatScore(undefined)).toBeNull()
    expect(formatScore(NaN)).toBeNull()
  })
})

describe('result helpers', () => {
  it('optionName maps known types and falls back to Alternative', () => {
    expect(optionName('cultural_bridge')).toBe('Cultural Bridge')
    expect(optionName('something_else')).toBe('Alternative')
  })
  it('hasRecommendations reflects the options array', () => {
    expect(hasRecommendations(response())).toBe(true)
    expect(hasRecommendations(response({ options: [] }))).toBe(false)
  })
  it('coverageText reads real coverage without inventing totals', () => {
    expect(coverageText(option({ group_coverage: 1 }), 3)).toBe('Appears in 1/3 participant result set')
    expect(coverageText(option({ group_coverage: 2 }), 3)).toBe('Appears in 2/3 participant result sets')
  })
})
