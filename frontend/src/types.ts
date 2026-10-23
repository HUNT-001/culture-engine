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
  combined_rank?: number | null
  verification_status: 'unverified' | 'verified' | 'ambiguous' | 'demo'
  maps_search_url?: string | null
  rank_score: number
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
