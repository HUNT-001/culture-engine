import { useEffect, useState } from 'react'
import { ArrowUpRight, Compass, LoaderCircle, MapPin, Plus, RotateCcw, Users, X } from 'lucide-react'
import { getRecommendations } from '../api/client'
import type { RecommendationResponse } from '../types'
import {
  buildPayload, MAX_PARTICIPANTS, MIN_PARTICIPANTS, newParticipantId,
  validatePlan, type DraftParticipant,
} from '../lib/plan'
import { clearPlan, loadPlan, newPlanRef, savePlan, type SavedPlan } from '../lib/storage'
import ResultsPanel from './ResultsPanel'

function freshGroup(): DraftParticipant[] {
  return [
    { participant_id: newParticipantId(), display_name: 'You', interestsText: 'indie rock, modern art' },
    { participant_id: newParticipantId(), display_name: 'Friend', interestsText: 'specialty coffee, indie films' },
  ]
}

type Props = { onMode: (demo: boolean) => void }

/** Same-device "quick" flow against the stateless POST /api/recommendations endpoint. */
export default function QuickPlanner({ onMode }: Props) {
  const [location, setLocation] = useState('Chennai, Tamil Nadu, India')
  const [budget, setBudget] = useState('800')
  const [participants, setParticipants] = useState<DraftParticipant[]>(freshGroup)
  const [planRef, setPlanRef] = useState<string>(() => newPlanRef())
  const [result, setResult] = useState<RecommendationResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [validationErrors, setValidationErrors] = useState<string[]>([])
  const [savedPlan, setSavedPlan] = useState<SavedPlan | null>(null)

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
    setParticipants((current) =>
      current.length <= MIN_PARTICIPANTS ? current : current.filter((_, i) => i !== index))
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
      onMode(response.demo_mode)
      const toSave: SavedPlan = { planRef, savedAt: new Date().toISOString(), location, budget, participants, result: response }
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
    setLocation(savedPlan.location); setBudget(savedPlan.budget); setParticipants(savedPlan.participants)
    setPlanRef(savedPlan.planRef); setResult(savedPlan.result); setError(''); setValidationErrors([])
  }
  function discardSaved() { clearPlan(); setSavedPlan(null) }
  function startNewPlan() { setResult(null); setError(''); setValidationErrors([]); setPlanRef(newPlanRef()) }

  const showResumeBar = savedPlan && savedPlan.result && savedPlan.planRef !== planRef && !result

  return (
    <>
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

      <section className="workspace">
        <form className="planner-card" onSubmit={submit} noValidate>
          <div className="section-heading">
            <div><span className="step">01</span><h2>Set the scene</h2></div>
            <span className="small-muted">Plan {planRef}</span>
          </div>
          <label className="field-label" htmlFor="q-location">Where are you planning?</label>
          <div className="input-with-icon">
            <MapPin size={17} />
            <input id="q-location" value={location} maxLength={160}
              onChange={(e) => setLocation(e.target.value)} placeholder="City or neighbourhood" />
          </div>
          <label className="field-label" htmlFor="q-budget">Budget per person (optional)</label>
          <div className="input-with-icon budget-input">
            <span className="currency">₹</span>
            <input id="q-budget" type="number" min="1" max="100000" value={budget}
              onChange={(e) => setBudget(e.target.value)} placeholder="800" />
          </div>

          <div className="section-heading participant-heading">
            <div><span className="step">02</span><h2>Build your group</h2></div>
            <span className="small-muted">{participantCount}/{MAX_PARTICIPANTS} people</span>
          </div>
          <p className="helper">
            Everyone is added here in one session on this device. For a multi-device plan, switch to
            Collaborative above.
          </p>
          <div className="participants-list">
            {participants.map((person, index) => (
              <div className="participant" key={person.participant_id}>
                <div className="participant-top">
                  <label className="field-label" htmlFor={`q-name-${index}`}>Participant {index + 1}</label>
                  {participantCount > MIN_PARTICIPANTS && (
                    <button className="icon-button" type="button" aria-label={`Remove participant ${index + 1}`}
                      onClick={() => removeParticipant(index)}><X size={15} /></button>
                  )}
                </div>
                <input id={`q-name-${index}`} className="plain-input" value={person.display_name} maxLength={60}
                  onChange={(e) => updateParticipant(index, { display_name: e.target.value })}
                  placeholder="Name or nickname" />
                <label className="field-label interests-label" htmlFor={`q-interests-${index}`}>
                  Interests (comma-separated)
                </label>
                <input id={`q-interests-${index}`} className="plain-input" value={person.interestsText}
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
            <ResultsPanel
              result={result}
              participantCount={participantCount}
              eyebrow={`YOUR CULTURAL THREAD · ${planRef}`}
              title="Three ways to go"
              onReset={startNewPlan}
              resetLabel="New plan"
            />
          )}
        </aside>
      </section>
    </>
  )
}
