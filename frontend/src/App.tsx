import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle, ArrowUpRight, Compass, Info, LoaderCircle, MapPin,
  Plus, RotateCcw, Sparkles, Users, X, Zap,
} from 'lucide-react'
import { getHealth, getRecommendations } from './api/client'
import type { RecommendationResponse } from './types'
import {
  buildPayload, MAX_PARTICIPANTS, MIN_PARTICIPANTS, newParticipantId,
  validatePlan, type DraftParticipant,
} from './lib/plan'
import {
  clearPlan, loadPlan, newPlanRef, savePlan, type SavedPlan,
} from './lib/storage'
import {
  coverageText, formatScore, hasRecommendations, optionName, sourceBadge,
} from './lib/results'

function freshGroup(): DraftParticipant[] {
  return [
    { participant_id: newParticipantId(), display_name: 'You', interestsText: 'indie rock, modern art' },
    { participant_id: newParticipantId(), display_name: 'Friend', interestsText: 'specialty coffee, indie films' },
  ]
}

type Mode = 'unknown' | 'live' | 'demo' | 'offline'

export default function App() {
  const [location, setLocation] = useState('Chennai, Tamil Nadu, India')
  const [budget, setBudget] = useState('800')
  const [participants, setParticipants] = useState<DraftParticipant[]>(freshGroup)
  const [planRef, setPlanRef] = useState<string>(() => newPlanRef())

  const [result, setResult] = useState<RecommendationResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [validationErrors, setValidationErrors] = useState<string[]>([])

  const [mode, setMode] = useState<Mode>('unknown')
  const [savedPlan, setSavedPlan] = useState<SavedPlan | null>(null)

  // Proactively surface whether the backend is in live or demo mode.
  useEffect(() => {
    let active = true
    getHealth()
      .then((health) => { if (active) setMode(health.demo_mode ? 'demo' : 'live') })
      .catch(() => { if (active) setMode('offline') })
    return () => { active = false }
  }, [])

  // Offer to restore a previously saved plan from this device.
  useEffect(() => { setSavedPlan(loadPlan()) }, [])

  const participantCount = participants.length

  function updateParticipant(index: number, patch: Partial<DraftParticipant>) {
    setParticipants((current) => current.map((p, i) => (i === index ? { ...p, ...patch } : p)))
  }
  function addParticipant() {
    setParticipants((current) =>
      current.length >= MAX_PARTICIPANTS
        ? current
        : [...current, { participant_id: newParticipantId(), display_name: '', interestsText: '' }])
  }
  function removeParticipant(index: number) {
    setParticipants((current) => (current.length <= MIN_PARTICIPANTS ? current : current.filter((_, i) => i !== index)))
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    const check = validatePlan(location, budget, participants)
    setValidationErrors(check.errors)
    if (!check.ok) return

    setLoading(true)
    setResult(null)
    try {
      const response = await getRecommendations(buildPayload(location, budget, participants))
      setResult(response)
      setMode(response.demo_mode ? 'demo' : 'live')
      const toSave: SavedPlan = {
        planRef, savedAt: new Date().toISOString(), location, budget,
        participants, result: response,
      }
      savePlan(toSave)
      setSavedPlan(toSave)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  function resumeSaved() {
    if (!savedPlan) return
    setLocation(savedPlan.location)
    setBudget(savedPlan.budget)
    setParticipants(savedPlan.participants)
    setPlanRef(savedPlan.planRef)
    setResult(savedPlan.result)
    setError('')
    setValidationErrors([])
  }
  function discardSaved() {
    clearPlan()
    setSavedPlan(null)
  }
  function startNewPlan() {
    setResult(null)
    setError('')
    setValidationErrors([])
    setPlanRef(newPlanRef())
  }

  const modePill = useMemo(() => {
    switch (mode) {
      case 'live': return { cls: 'mode-live', icon: <Zap size={12} />, text: 'Live Qloo' }
      case 'demo': return { cls: 'mode-demo', icon: <Info size={12} />, text: 'Demo mode' }
      case 'offline': return { cls: 'mode-offline', icon: <AlertTriangle size={12} />, text: 'Backend offline' }
      default: return { cls: 'mode-unknown', icon: <LoaderCircle size={12} className="spinner" />, text: 'Checking…' }
    }
  }, [mode])

  const showResumeBar = savedPlan && savedPlan.result && savedPlan.planRef !== planRef && !result

  return (
    <main className="page-shell">
      <nav className="topbar">
        <a className="brand" href="#top" aria-label="Common Thread home">
          <span className="brand-mark"><Compass size={20} /></span> common thread
        </a>
        <span className={`mode-pill ${modePill.cls}`} title="Backend provider mode">
          {modePill.icon} {modePill.text}
        </span>
      </nav>

      {showResumeBar && (
        <div className="resume-bar" role="status">
          <span>
            <RotateCcw size={14} /> Saved plan <strong>{savedPlan!.planRef}</strong> from{' '}
            {new Date(savedPlan!.savedAt).toLocaleString()} is on this device.
          </span>
          <span className="resume-actions">
            <button type="button" className="text-button" onClick={resumeSaved}>Resume</button>
            <button type="button" className="text-button muted" onClick={discardSaved}>Discard</button>
          </span>
        </div>
      )}

      <section className="hero" id="top">
        <div className="eyebrow"><Sparkles size={14} /> LESS SCROLLING. BETTER PLANS.</div>
        <h1>Different tastes.<br /><span>One great plan.</span></h1>
        <p className="hero-copy">
          Tell us what everyone loves. Common Thread uses Qloo's cultural graph to find the thread
          that turns different interests into one shared experience.
        </p>
      </section>

      <section className="workspace">
        <form className="planner-card" onSubmit={submit} noValidate>
          <div className="section-heading">
            <div><span className="step">01</span><h2>Set the scene</h2></div>
            <span className="small-muted">Plan {planRef}</span>
          </div>
          <label className="field-label" htmlFor="location">Where are you planning?</label>
          <div className="input-with-icon">
            <MapPin size={17} />
            <input id="location" value={location} maxLength={160}
              onChange={(e) => setLocation(e.target.value)} placeholder="City or neighbourhood" />
          </div>
          <label className="field-label" htmlFor="budget">Budget per person (optional)</label>
          <div className="input-with-icon budget-input">
            <span className="currency">₹</span>
            <input id="budget" type="number" min="1" max="100000" value={budget}
              onChange={(e) => setBudget(e.target.value)} placeholder="800" />
          </div>

          <div className="section-heading participant-heading">
            <div><span className="step">02</span><h2>Build your group</h2></div>
            <span className="small-muted">{participantCount}/{MAX_PARTICIPANTS} people</span>
          </div>
          <p className="helper">
            Add each friend and up to three interests apiece — music, films, games, art, brands, anything
            Qloo knows. Everyone is added here in one session.
          </p>
          <div className="participants-list">
            {participants.map((person, index) => (
              <div className="participant" key={person.participant_id}>
                <div className="participant-top">
                  <label className="field-label" htmlFor={`name-${index}`}>Participant {index + 1}</label>
                  {participantCount > MIN_PARTICIPANTS && (
                    <button className="icon-button" type="button" aria-label={`Remove participant ${index + 1}`}
                      onClick={() => removeParticipant(index)}><X size={15} /></button>
                  )}
                </div>
                <input id={`name-${index}`} className="plain-input" value={person.display_name} maxLength={60}
                  onChange={(e) => updateParticipant(index, { display_name: e.target.value })}
                  placeholder="Name or nickname" />
                <label className="field-label interests-label" htmlFor={`interests-${index}`}>
                  Interests (comma-separated)
                </label>
                <input id={`interests-${index}`} className="plain-input" value={person.interestsText}
                  onChange={(e) => updateParticipant(index, { interestsText: e.target.value })}
                  placeholder="e.g. indie rock, anime, coffee" />
              </div>
            ))}
          </div>
          {participantCount < MAX_PARTICIPANTS && (
            <button type="button" className="add-person" onClick={addParticipant}>
              <Plus size={15} /> Add someone else
            </button>
          )}

          <div className="invite-note">
            <Info size={13} />
            <span>
              This prototype builds your group in one session — there's no account or shareable invite link
              yet, so add everyone's interests here before generating.
            </span>
          </div>

          {validationErrors.length > 0 && (
            <ul className="validation-errors" role="alert">
              {validationErrors.map((message) => <li key={message}>{message}</li>)}
            </ul>
          )}

          <button className="submit-button" type="submit" disabled={loading}>
            {loading
              ? <><LoaderCircle className="spinner" size={17} /> Finding your cultural thread…</>
              : <>Find our shared next thing <ArrowUpRight size={18} /></>}
          </button>
          <p className="privacy-note">
            <Users size={14} /> No account required. Avoid entering sensitive personal information.
          </p>
        </form>

        <aside className="side-panel">
          {!result && !error && (
            <div className="empty-state">
              <div className="orbit orbit-one" /><div className="orbit orbit-two" />
              <div className="empty-icon"><Compass size={34} strokeWidth={1.5} /></div>
              <span className="empty-eyebrow">THE CULTURAL BRIDGE</span>
              <h3>What connects<br />your different worlds?</h3>
              <p>We compare everyone's cultural interests to find shared ground, unexpected links and one worthwhile wildcard.</p>
              <div className="option-legend">
                <span><i className="legend-dot shared" />Shared Ground — everyone overlaps</span>
                <span><i className="legend-dot bridge" />Cultural Bridge — several connect</span>
                <span><i className="legend-dot stretch" />Stretch Choice — one worthwhile wildcard</span>
              </div>
            </div>
          )}

          {error && (
            <div className="error-card">
              <h3>We couldn't finish that plan.</h3>
              <p>{error}</p>
              <p className="helper">Fix the issue above and try again. Your inputs are still here.</p>
            </div>
          )}

          {result && (
            <div className="results-panel">
              <div className="results-heading">
                <div>
                  <span className="eyebrow">YOUR CULTURAL THREAD · {planRef}</span>
                  <h2>Three ways to go</h2>
                </div>
                <button type="button" className="text-button" onClick={startNewPlan}>New plan</button>
              </div>

              {(() => {
                const badge = sourceBadge(result)
                return (
                  <div className={`source-badge ${badge.live ? 'is-live' : 'is-demo'}`}>
                    {badge.live ? <Zap size={14} /> : <Info size={14} />}
                    <div><strong>{badge.label}</strong><span>{badge.detail}</span></div>
                  </div>
                )
              })()}

              {result.warnings.map((warning, i) => <p className="warning" key={`w-${i}`}>{warning}</p>)}
              {result.unresolved_interests.length > 0 && (
                <p className="warning">
                  We couldn't confidently match these interests to Qloo, so they were left out:{' '}
                  <strong>{result.unresolved_interests.join(', ')}</strong>. Try a more specific or
                  better-known name.
                </p>
              )}

              {!hasRecommendations(result) ? (
                <div className="empty-results">
                  <h3>No group recommendations yet.</h3>
                  <p className="helper">
                    The backend returned no usable options (status: {result.status}). Try broader or
                    more mainstream interests, or a larger city.
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
                      <p className="score-note">
                        <strong>Qloo affinity</strong> is Qloo's cultural signal; <strong>Group-fit</strong> is
                        our ranking heuristic — not a probability of enjoyment.
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
          )}
        </aside>
      </section>

      <footer className="footer">
        <span>COMMON THREAD · PROTOTYPE 0.1</span>
        <span>Built around culture, not just proximity.</span>
      </footer>
    </main>
  )
}
