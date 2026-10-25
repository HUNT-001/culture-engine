export type ParticipantInput = {
  participant_id: string
  display_name: string
  interests: string[]
  dislikes?: string[]
}

export type RecommendationRequest = {
  location: string
  budget_per_person?: number
  participants: ParticipantInput[]
}

export type Candidate = {
  entity_id: string
  name: string
  entity_type: string
  address?: string | null
  source: 'qloo' | 'mock'
  participant_ranks: Record<string, number>
  participant_affinities?: Record<string, number>
  combined_rank?: number | null
  verification_status: 'unverified' | 'verified' | 'ambiguous' | 'demo'
  maps_search_url?: string | null
  rank_score: number
  // Qloo's own cultural affinity signal (0–1), present only for live Qloo results.
  // Distinct from `rank_score`, which is our group-fit heuristic.
  qloo_affinity?: number | null
  // Verified interest names Qloo's explainability credited for this candidate.
  matched_interests?: string[]
  group_coverage: number
  reasons: string[]
}

export type RecommendationOption = {
  option_type: 'shared_ground' | 'cultural_bridge' | 'stretch_choice' | 'alternative'
  title: string
  candidate: Candidate
  explanation: string
  evidence_labels: string[]
}

export type RecommendationResponse = {
  run_id: string
  demo_mode: boolean
  location: string
  options: RecommendationOption[]
  warnings: string[]
  unresolved_interests: string[]
  status: 'complete' | 'partial' | 'failed'
}

// --- Group plan lifecycle (matches backend app/domain/schemas.py) ---

export type PlanCreatedResponse = {
  plan_id: string
  share_token: string
  expires_at: string
}

export type JoinPlanResponse = {
  participant_id: string
  participant_token: string
}

export type ParticipantView = {
  participant_id: string
  display_name: string
  interests: string[]
  dislikes: string[]
  has_preferences: boolean
}

export type PlanView = {
  plan_id: string
  location: string
  budget_per_person: number | null
  status: string
  expires_at: string
  max_participants: number
  participants: ParticipantView[]
  latest_recommendation: RecommendationResponse | null
}
