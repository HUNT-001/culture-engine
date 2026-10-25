import { ArrowUpRight, Info, Zap } from 'lucide-react'
import type { RecommendationResponse } from '../types'
import { coverageText, formatScore, hasRecommendations, optionName, sourceBadge } from '../lib/results'

type Props = {
  result: RecommendationResponse
  participantCount: number
  title: string
  eyebrow: string
  onReset?: () => void
  resetLabel?: string
}

/** Shared recommendation renderer for both the collaborative and quick flows.
 *  Renders only data the backend actually returned — no fabricated details. */
export default function ResultsPanel({ result, participantCount, title, eyebrow, onReset, resetLabel }: Props) {
  const badge = sourceBadge(result)
  return (
    <div className="results-panel">
      <div className="results-heading">
        <div>
          <span className="eyebrow">{eyebrow}</span>
          <h2>{title}</h2>
        </div>
        {onReset && (
          <button type="button" className="text-button" onClick={onReset}>{resetLabel ?? 'New plan'}</button>
        )}
      </div>

      <div className={`source-badge ${badge.live ? 'is-live' : 'is-demo'}`}>
        {badge.live ? <Zap size={14} /> : <Info size={14} />}
        <div><strong>{badge.label}</strong><span>{badge.detail}</span></div>
      </div>

      {result.warnings.map((warning, i) => <p className="warning" key={`w-${i}`}>{warning}</p>)}
      {result.unresolved_interests.length > 0 && (
        <p className="warning">
          We couldn't confidently match these interests to Qloo, so they were left out:{' '}
          <strong>{result.unresolved_interests.join(', ')}</strong>. Try a more specific or better-known name.
        </p>
      )}

      {!hasRecommendations(result) ? (
        <div className="empty-results">
          <h3>No group recommendations yet.</h3>
          <p className="helper">
            The backend returned no usable options (status: {result.status}). Try broader or more mainstream
            interests, or a larger city.
          </p>
        </div>
      ) : (
        result.options.map((option, i) => {
          const affinity = formatScore(option.candidate.qloo_affinity)
          const groupScore = formatScore(option.candidate.rank_score)
          const isDemoCard = option.candidate.source === 'mock' || result.demo_mode
          return (
            <article className={`result-card option-${option.option_type}`} key={option.candidate.entity_id}>
              <div className="result-meta">
                <span className="option-index">0{i + 1}</span>
                <span className="option-type">{optionName(option.option_type)}</span>
                <span className={`verification verification-${option.candidate.verification_status}`}>
                  {isDemoCard ? 'DEMO' : 'NOT VERIFIED'}
                </span>
              </div>
              <h3>{option.candidate.name}</h3>
              {option.candidate.address && <p className="address">{option.candidate.address}</p>}
              <p>{option.explanation}</p>

              <div className="score-row">
                {affinity && (
                  <span className="score-chip chip-qloo" title="Qloo's own cultural affinity signal">
                    Qloo affinity {affinity}
                  </span>
                )}
                {groupScore && (
                  <span className="score-chip chip-heuristic" title="Our deterministic group-fit heuristic">
                    Group-fit {groupScore}
                  </span>
                )}
                <span className="score-chip chip-coverage">{coverageText(option, participantCount)}</span>
              </div>

              {option.candidate.matched_interests && option.candidate.matched_interests.length > 0 && (
                <p className="qloo-link">
                  <Zap size={12} /> Qloo linked this to{' '}
                  <strong>{option.candidate.matched_interests.join(', ')}</strong>
                </p>
              )}

              <p className="score-note">
                <strong>Qloo affinity</strong> and the linked interests are Qloo's cultural signals;{' '}
                <strong>Group-fit</strong> and coverage are our own calculation — not a probability of enjoyment.
              </p>

              {option.evidence_labels.length > 0 && (
                <div className="evidence-list">
                  {option.evidence_labels.map((label) => <span key={label}>{label}</span>)}
                </div>
              )}

              {option.candidate.maps_search_url && (
                <a className="map-link" href={option.candidate.maps_search_url} target="_blank" rel="noreferrer">
                  Look it up on Maps <ArrowUpRight size={14} />
                </a>
              )}
            </article>
          )
        })
      )}

      <p className="disclaimer">
        Cultural affinity is a discovery signal, not a guarantee of enjoyment. Venue names, hours and
        availability are not independently verified — check before you travel.
      </p>
    </div>
  )
}
