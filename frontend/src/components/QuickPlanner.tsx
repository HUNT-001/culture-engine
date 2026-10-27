import { useEffect, useState } from 'react'
import { ArrowUpRight, LoaderCircle, MapPin, Plus, RotateCcw, ShieldCheck, X } from 'lucide-react'
import { getRecommendations } from '../api/client'
import type { RecommendationResponse } from '../types'
import { MAX_PARTICIPANTS, MIN_PARTICIPANTS, newParticipantId } from '../lib/plan'
import {
  buildInterestPayload, newRow, rowsFromSaved, validateInterestRows, type InterestRow,
} from '../lib/interests'
import { budgetFields, currencySymbol, DEFAULT_CURRENCY } from '../lib/currency'
import { useBudgetCurrency } from '../lib/budgetCurrency'
import { initials } from '../lib/present'
import { clearPlan, loadPlan, newPlanRef, savePlan, type SavedPlan } from '../lib/storage'
import CurrencySelect from './CurrencySelect'
import InterestPicker from './InterestPicker'
import ResultsPanel from './ResultsPanel'
import Stepper from './Stepper'
import ThreadArt from './ThreadArt'

type QuickParticipant = { participant_id: string; display_name: string; rows: InterestRow[] }

function freshGroup(): QuickParticipant[] {
  return [
    { participant_id: newParticipantId(), display_name: 'You', rows: [newRow('indie rock'), newRow('modern art')] },
    { participant_id: newParticipantId(), display_name: 'Friend', rows: [newRow('specialty coffee'), newRow('indie films')] },
  ]
}

type Props = { onMode: (demo: boolean) => void }

export default function QuickPlanner({ onMode }: Props) {
  const [location, setLocation] = useState('Chennai, Tamil Nadu, India')
  const [budget, setBudget] = useState('800')
  const budgetCurrency = useBudgetCurrency(location)
  const [participants, setParticipants] = useState<QuickParticipant[]>(freshGroup)
  const [planRef, setPlanRef] = useState<string>(() => newPlanRef())
  const [result, setResult] = useState<RecommendationResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [validationErrors, setValidationErrors] = useState<string[]>([])
  const [savedPlan, setSavedPlan] = useState<SavedPlan | null>(null)

  useEffect(() => { setSavedPlan(loadPlan()) }, [])

  const participantCount = participants.length

  function updateParticipant(index: number, patch: Partial<QuickParticipant>) {
    setParticipants((cur) => cur.map((p, i) => (i === index ? { ...p, ...patch } : p)))
  }
  function addParticipant() {
    setParticipants((cur) => cur.length >= MAX_PARTICIPANTS ? cur
      : [...cur, { participant_id: newParticipantId(), display_name: '', rows: [newRow()] }])
  }
  function removeParticipant(index: number) {
    setParticipants((cur) => cur.length <= MIN_PARTICIPANTS ? cur : cur.filter((_, i) => i !== index))
  }

  function validate(): string[] {
    const errors: string[] = []
    const loc = location.trim()
    if (loc.length < 2) errors.push('Enter a location (at least 2 characters).')
    if (budget.trim()) {
      const n = Number(budget)
      if (!Number.isFinite(n) || n <= 0) errors.push('Budget must be a positive number, or leave it blank.')
      else if (n > 100000) errors.push('Budget looks too large (max 100000).')
    }
    if (participantCount < MIN_PARTICIPANTS) errors.push(`Add at least ${MIN_PARTICIPANTS} participants.`)
    participants.forEach((p, i) => {
      const label = p.display_name.trim() || `Participant ${i + 1}`
      if (!p.display_name.trim()) errors.push(`Participant ${i + 1} needs a name.`)
      for (const message of validateInterestRows(p.rows)) {
        errors.push(message.startsWith('Add at least') ? `${label} needs at least one interest.` : `${label}: ${message}`)
      }
    })
    return errors
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    const errs = validate()
    setValidationErrors(errs)
    if (errs.length) return
    setLoading(true)
    setResult(null)
    try {
      const builtParticipants = participants.map((p) => {
        const { interests, resolved_interests } = buildInterestPayload(p.rows)
        return { participant_id: p.participant_id, display_name: p.display_name.trim(), interests, resolved_interests }
      })
      const payload = {
        location: location.trim(),
        ...budgetFields(budget, budgetCurrency.currency),
        participants: builtParticipants,
      }
      const response = await getRecommendations(payload)
      setResult(response)
      onMode(response.demo_mode)
      const toSave: SavedPlan = {
        planRef, savedAt: new Date().toISOString(), location, budget, currency: budgetCurrency.currency,
        participants: builtParticipants.map((p) => ({
          participant_id: p.participant_id, display_name: p.display_name,
          interests: p.interests, resolved_interests: p.resolved_interests,
        })),
        result: response,
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
    setLocation(savedPlan.location); setBudget(savedPlan.budget)
    budgetCurrency.restore(savedPlan.location, savedPlan.currency ?? DEFAULT_CURRENCY)
    setParticipants(savedPlan.participants.map((p) => ({
      participant_id: p.participant_id || newParticipantId(),
      display_name: p.display_name,
      rows: rowsFromSaved(p.interests, p.resolved_interests),
    })))
    setPlanRef(savedPlan.planRef); setResult(savedPlan.result); setError(''); setValidationErrors([])
  }
  function discardSaved() { clearPlan(); setSavedPlan(null) }
  function startNewPlan() { setResult(null); setError(''); setValidationErrors([]); setPlanRef(newPlanRef()) }

  const showResumeBar = savedPlan && savedPlan.result && savedPlan.planRef !== planRef && !result

  // Progress is derived from existing state only: nothing here changes behaviour.
  const groupReady = participants.every((p) => p.display_name.trim() && validateInterestRows(p.rows).length === 0)
  const step = result ? 4 : groupReady ? 3 : 2

  return (
    <>
      <Stepper label="Quick planner progress" current={step}
        steps={['Set the scene', 'Build the group', 'Confirm interests', 'Your results']} />

      {showResumeBar && (
        <div className="notice notice-info" role="status">
          <RotateCcw size={16} />
          <p>
            Saved plan <strong>{savedPlan!.planRef}</strong> from {new Date(savedPlan!.savedAt).toLocaleString()} is on this device.
          </p>
          <span className="notice-actions">
            <button type="button" className="text-button" onClick={resumeSaved}>Resume</button>
            <button type="button" className="text-button muted" onClick={discardSaved}>Discard</button>
          </span>
        </div>
      )}

      <section className="workspace">
        <form className="card planner-card" onSubmit={submit} noValidate>
          <div className="section-heading">
            <div><span className="step">01</span><h2>Set the scene</h2></div>
            <span className="small-muted">Plan {planRef}</span>
          </div>
          <label className="field-label" htmlFor="q-location">Where are you planning?</label>
          <div className="input-with-icon">
            <MapPin size={17} />
            <input id="q-location" value={location} maxLength={160}
              onChange={(e) => { setLocation(e.target.value); budgetCurrency.onLocationChange(e.target.value) }}
              placeholder="City or neighbourhood" />
          </div>
          <label className="field-label" htmlFor="q-budget">Budget per person (optional)</label>
          <div className="input-with-icon budget-input">
            <span className="currency" aria-hidden="true">{currencySymbol(budgetCurrency.currency)}</span>
            <input id="q-budget" type="number" min="1" max="100000" value={budget}
              onChange={(e) => setBudget(e.target.value)} placeholder="800" />
            <CurrencySelect id="q-currency" value={budgetCurrency.currency} onChange={budgetCurrency.setCurrency} />
          </div>

          <div className="section-heading participant-heading">
            <div><span className="step">02</span><h2>Build your group</h2></div>
            <span className="small-muted">{participantCount}/{MAX_PARTICIPANTS} people</span>
          </div>
          <p className="helper">
            Add each friend and their interests. Search and pick the Qloo entity you mean for every
            interest — nothing is matched automatically, so each one needs your confirmation.
          </p>
          <div className="participants-list">
            {participants.map((person, index) => (
              <div className="participant" key={person.participant_id}>
                <div className="participant-top">
                  <span className="avatar" data-tone={index % 4} aria-hidden="true">{initials(person.display_name)}</span>
                  <label className="field-label" htmlFor={`q-name-${index}`}>Participant {index + 1}</label>
                  {participantCount > MIN_PARTICIPANTS && (
                    <button className="icon-button" type="button" aria-label={`Remove participant ${index + 1}`}
                      onClick={() => removeParticipant(index)}><X size={15} /></button>
                  )}
                </div>
                <input id={`q-name-${index}`} className="input" value={person.display_name} maxLength={60}
                  onChange={(e) => updateParticipant(index, { display_name: e.target.value })}
                  placeholder="Name or nickname" />
                <div className="field-label interests-label" id={`q-interests-${index}`}>Interests</div>
                <div role="group" aria-labelledby={`q-interests-${index}`}>
                  <InterestPicker idPrefix={`q-${index}`} rows={person.rows}
                    onChange={(rows) => updateParticipant(index, { rows })} />
                </div>
              </div>
            ))}
          </div>
          {participantCount < MAX_PARTICIPANTS && (
            <button type="button" className="add-link" onClick={addParticipant}>
              <Plus size={15} /> Add someone else
            </button>
          )}

          {validationErrors.length > 0 && (
            <ul className="validation-errors" role="alert">
              {validationErrors.map((message) => <li key={message}>{message}</li>)}
            </ul>
          )}

          <button className="btn btn-primary btn-block" type="submit" disabled={loading}>
            {loading
              ? <><LoaderCircle className="spinner" size={17} /> Finding your cultural thread…</>
              : <>Find our shared next thing <ArrowUpRight size={18} /></>}
          </button>
          <p className="privacy-note">
            <ShieldCheck size={14} /> No account required. Avoid entering sensitive personal information.
          </p>
        </form>

        <aside className="side-panel" aria-live="polite">
          {loading && (
            <div className="empty-state is-loading" role="status">
              <ThreadArt variant="compact" />
              <span className="eyebrow">Weaving your threads</span>
              <h3>Looking for where<br />your tastes meet…</h3>
              <p>Asking Qloo what each person's interests connect to, then comparing the results.</p>
            </div>
          )}
          {!result && !error && !loading && (
            <div className="empty-state">
              <ThreadArt variant="compact" />
              <span className="eyebrow">The cultural bridge</span>
              <h3>What connects<br />your different worlds?</h3>
              <p>We compare everyone's cultural interests to find shared ground, unexpected links and one worthwhile wildcard.</p>
              <ul className="option-legend">
                <li><i className="legend-dot shared" /><span><strong>Shared Ground</strong> everyone overlaps</span></li>
                <li><i className="legend-dot bridge" /><span><strong>Cultural Bridge</strong> several connect</span></li>
                <li><i className="legend-dot stretch" /><span><strong>Stretch Choice</strong> one worthwhile wildcard</span></li>
              </ul>
            </div>
          )}
          {error && (
            <div className="notice notice-error error-card" role="alert">
              <div>
                <h3>We couldn't finish that plan.</h3>
                <p>{error}</p>
                <p className="helper">Fix the issue and try again. Your inputs are still here.</p>
              </div>
            </div>
          )}
          {result && (
            <ResultsPanel result={result} participantCount={participantCount}
              eyebrow={`YOUR CULTURAL THREAD · ${planRef}`} title="Three ways to go"
              onReset={startNewPlan} resetLabel="New plan" />
          )}
        </aside>
      </section>
    </>
  )
}
