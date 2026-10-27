import type { CSSProperties, ReactElement } from 'react'
import {
  ArrowUpRight, CircleAlert, Compass, Info, Link2, MapPin, Sparkles, TriangleAlert, Users, Zap,
} from 'lucide-react'
import type { RecommendationResponse } from '../types'
import {
  confirmationGroups, formatScore, hasRecommendations, optionName, sourceBadge, statusNotice,
} from '../lib/results'
import { barPercent, coverageDots } from '../lib/present'

type Props = {
  result: RecommendationResponse
  participantCount: number
  title: string
  eyebrow: string
  onReset?: () => void
  resetLabel?: string
}

// What each label means (definitions of our own labels, not claims about a venue).
const TYPE_META: Record<string, { hint: string; icon: ReactElement }> = {
  shared_ground: { hint: "Everyone's results overlap", icon: <Users size={14} /> },
  cultural_bridge: { hint: 'Connects several, not all', icon: <Link2 size={14} /> },
  stretch_choice: { hint: 'A worthwhile wildcard', icon: <Sparkles size={14} /> },
  alternative: { hint: 'Best remaining option', icon: <Compass size={14} /> },
}

/** Shared recommendation renderer for both the collaborative and quick flows.
 *  Renders only data the backend actually returned — no fabricated details. */
export default function ResultsPanel({ result, participantCount, title, eyebrow, onReset, resetLabel }: Props) {
  const badge = sourceBadge(result)
  const notice = statusNotice(result)
  const unconfirmed = confirmationGroups(result)
  return (
    <section className="results" aria-label="Recommendations">
      <div className="results-summary glass">
        <div className="results-titles">
          <span className="eyebrow">{eyebrow}</span>
          <h2>{title}</h2>
        </div>
        <div className="results-actions">
          <span className={`source-pill ${badge.live ? 'is-live' : 'is-demo'}`}>
            {badge.live ? <Zap size={13} /> : <Info size={13} />} {badge.label}
          </span>
          {onReset && (
            <button type="button" className="text-button" onClick={onReset}>{resetLabel ?? 'New plan'}</button>
          )}
        </div>
        <p className="source-detail">{badge.detail}</p>
      </div>

      {notice && (
        <div className={`notice notice-${notice.tone === 'failed' ? 'error' : 'warn'}`} role="status" data-status={notice.tone}>
          {notice.tone === 'failed' ? <CircleAlert size={17} /> : <TriangleAlert size={17} />}
          <p><strong>{notice.title}.</strong> {notice.detail}</p>
        </div>
      )}

      {unconfirmed.length > 0 && (
        <div className="leftout" role="status">
          <p className="leftout-title">Left out — not confirmed to a Qloo entity</p>
          <ul>
            {unconfirmed.map((g) => (
              <li key={g.name || g.terms.join('|')}>
                {g.name && <span className="leftout-name">{g.name}</span>}
                {g.terms.map((t) => <span className="leftout-pill" key={t}>{t}</span>)}
              </li>
            ))}
          </ul>
          <p className="leftout-help">Search and pick the entity you mean for each, then run again.</p>
        </div>
      )}

      {result.warnings.length > 0 && (
        <ul className="notes">
          {result.warnings.map((warning, i) => (
            <li key={`w-${i}`}><Info size={14} /> <span>{warning}</span></li>
          ))}
        </ul>
      )}

      {!hasRecommendations(result) ? (
        <div className="empty-results">
          <h3>No group recommendations yet.</h3>
          {unconfirmed.length === 0 && (
            <p className="helper">
              {`The backend returned no usable options (status: ${result.status}). Try broader or more mainstream interests, or a larger city.`}
            </p>
          )}
        </div>
      ) : (
        <div className="result-list">
          {result.options.map((option, i) => {
            const affinity = formatScore(option.candidate.qloo_affinity)
            const affinityBar = barPercent(option.candidate.qloo_affinity)
            const groupScore = formatScore(option.candidate.rank_score)
            const groupBar = barPercent(option.candidate.rank_score)
            const isDemoCard = option.candidate.source === 'mock' || result.demo_mode
            const meta = TYPE_META[option.option_type] ?? TYPE_META.alternative
            const covered = option.candidate.group_coverage
            const dots = coverageDots(covered, participantCount)
            const evidence = option.evidence_labels
            return (
              <article className={`result-card option-${option.option_type}`} key={option.candidate.entity_id}
                style={{ '--i': i } as CSSProperties}>
                <header className="result-top">
                  <span className="rank-num" aria-hidden="true">{String(i + 1).padStart(2, '0')}</span>
                  <div className="type-label">
                    <span className="type-name">{meta.icon}{optionName(option.option_type)}</span>
                    <span className="type-hint">{meta.hint}</span>
                  </div>
                  <span className={`verification verification-${option.candidate.verification_status}`}>
                    {isDemoCard ? 'DEMO' : 'NOT VERIFIED'}
                  </span>
                </header>

                <h3>{option.candidate.name}</h3>
                {option.candidate.address && (
                  <p className="address"><MapPin size={13} /> {option.candidate.address}</p>
                )}
                <p className="why">{option.explanation}</p>

                <dl className="metrics">
                  <div className="metric metric-coverage">
                    <dt>Group coverage</dt>
                    <dd>
                      <span className="dots" aria-hidden="true">
                        {dots.map((on, d) => <i key={d} className={on ? 'on' : ''} />)}
                      </span>
                      <span className="metric-value">
                        {participantCount > 0 ? `${covered} of ${participantCount}` : covered}
                        <small> people</small>
                      </span>
                    </dd>
                    <span className="metric-src">in each person&rsquo;s own results</span>
                  </div>
                  {affinity && (
                    <div className="metric metric-qloo" title="Qloo's own cultural affinity signal">
                      <dt>Qloo affinity</dt>
                      <dd>
                        <span className="metric-value">{affinity}</span>
                        {affinityBar !== null && <span className="bar" aria-hidden="true"><i style={{ width: `${affinityBar}%` }} /></span>}
                      </dd>
                      <span className="metric-src">Qloo&rsquo;s signal</span>
                    </div>
                  )}
                  {groupScore && (
                    <div className="metric metric-fit" title="Our deterministic group-fit heuristic">
                      <dt>Group-fit</dt>
                      <dd>
                        <span className="metric-value">{groupScore}</span>
                        {groupBar !== null && <span className="bar" aria-hidden="true"><i style={{ width: `${groupBar}%` }} /></span>}
                      </dd>
                      <span className="metric-src">our heuristic</span>
                    </div>
                  )}
                </dl>

                {option.candidate.matched_interests && option.candidate.matched_interests.length > 0 && (
                  <p className="qloo-link">
                    <Zap size={13} />
                    <span>Qloo linked this to</span>
                    {option.candidate.matched_interests.map((m) => <strong key={m} className="link-pill">{m}</strong>)}
                  </p>
                )}

                {evidence.length > 0 && (
                  <details className="evidence">
                    <summary>Evidence &amp; caveats ({evidence.length})</summary>
                    <ul>{evidence.map((label) => <li key={label}>{label}</li>)}</ul>
                  </details>
                )}

                {option.candidate.maps_search_url && (
                  <a className="map-link" href={option.candidate.maps_search_url} target="_blank" rel="noreferrer">
                    Look it up on Maps <ArrowUpRight size={14} />
                  </a>
                )}
              </article>
            )
          })}
        </div>
      )}

      <p className="disclaimer">
        <strong>Qloo affinity</strong> and the linked interests are Qloo&rsquo;s cultural signals; <strong>group
        coverage</strong> and <strong>group-fit</strong> are our own calculation, not a probability of
        enjoyment. Venue names, hours, prices and availability are not independently verified — check
        before you travel.
      </p>
    </section>
  )
}
