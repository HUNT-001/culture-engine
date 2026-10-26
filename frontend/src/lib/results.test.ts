import { describe, expect, it } from 'vitest'
import type { RecommendationOption, RecommendationResponse } from '../types'
import {
  confirmationGroups, coverageText, formatScore, hasRecommendations, isLive, optionName, sourceBadge,
  statusNotice,
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
    warnings: [], unresolved_interests: [], needs_confirmation: [], status: 'complete', ...partial,
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

describe('unconfirmed interests and run status', () => {
  const left = [
    { participant_id: 'p1', display_name: 'Ana', text: 'Phoenix' },
    { participant_id: 'p1', display_name: 'Ana', text: 'jazz' },
    { participant_id: 'p2', display_name: 'Ben', text: 'Pulp' },
  ]

  it('groups needs_confirmation by person, in order', () => {
    expect(confirmationGroups(response({ needs_confirmation: left }))).toEqual([
      { name: 'Ana', terms: ['Phoenix', 'jazz'] },
      { name: 'Ben', terms: ['Pulp'] },
    ])
  })

  it('falls back to the older "Name: term" strings, and tolerates a missing field', () => {
    const old = response({ unresolved_interests: ['Ana: Phoenix'] }) as Partial<RecommendationResponse>
    delete old.needs_confirmation
    expect(confirmationGroups(old as RecommendationResponse)).toEqual([{ name: 'Ana', terms: ['Phoenix'] }])
    expect(confirmationGroups(response())).toEqual([])
  })

  it('a complete run that left nothing out has no notice', () => {
    expect(statusNotice(response())).toBeNull()
  })

  it('a partial run is labelled partial, and says why when interests were left out', () => {
    expect(statusNotice(response({ status: 'partial' }))?.tone).toBe('partial')
    const n = statusNotice(response({ status: 'partial', needs_confirmation: left }))
    expect(n?.detail).toMatch(/not confirmed/)
  })

  it('never reports a run that left interests out as complete, whatever its status says', () => {
    expect(statusNotice(response({ status: 'complete', needs_confirmation: left }))?.tone).toBe('partial')
  })

  it('a run with no options is a failure notice, even if the status says otherwise', () => {
    expect(statusNotice(response({ status: 'failed', options: [], needs_confirmation: left }))?.tone).toBe('failed')
    expect(statusNotice(response({ status: 'complete', options: [] }))?.tone).toBe('failed')
  })
})
