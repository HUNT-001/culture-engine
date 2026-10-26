import { useCallback, useEffect, useState } from 'react'
import {
  AlertTriangle, ArrowUpRight, Check, ClipboardCopy, Compass, Info, LoaderCircle,
  LogOut, MapPin, RefreshCw, Users,
} from 'lucide-react'
import {
  ApiError, createPlan, getPlan, joinPlan, runPlanRecommendations, setPreferences,
} from '../api/client'
import type { PlanView, RecommendationResponse } from '../types'
import { normalizeInterests } from '../lib/plan'
import {
  buildInterestPayload, newRow, rowsFromSaved, unconfirmedSavedInterests, validateInterestRows,
  type InterestRow,
} from '../lib/interests'
import { clearSession, loadSession, saveSession, type DeviceSession } from '../lib/session'
import { cleanCode, formatInviteText, hoursUntil, validateJoinInput } from '../lib/invite'
import InterestPicker from './InterestPicker'
import ResultsPanel from './ResultsPanel'

type Props = { onMode: (demo: boolean) => void }

/** Translate an error (API or otherwise) into a user-facing message. */
function describeError(err: unknown): string {
  if (err instanceof ApiError) {
    switch (err.status) {
      case 0: return err.message // network
      case 401: return 'Your access code is missing. Re-enter the plan to continue.'
      case 404: return 'That plan code is invalid, or the plan no longer exists.'
      case 410: return 'This plan has expired. Plans last 24 hours — start a new one.'
      default: return err.message // 409 / 422 / 500 carry a useful server detail
    }
  }
  return err instanceof Error ? err.message : 'Something went wrong. Please try again.'
}

export default function CollaborativePlanner({ onMode }: Props) {
  const [session, setSession] = useState<DeviceSession | null>(null)
  const [plan, setPlan] = useState<PlanView | null>(null)
  const [screen, setScreen] = useState<'choose' | 'create' | 'join'>('choose')

  // Create form
  const [location, setLocation] = useState('Chennai, Tamil Nadu, India')
  const [budget, setBudget] = useState('')
  // Join form
  const [joinPlanId, setJoinPlanId] = useState('')
  const [joinToken, setJoinToken] = useState('')
  // Self + prefs forms
  const [displayName, setDisplayName] = useState('')
  const [interestRows, setInterestRows] = useState<InterestRow[]>([newRow()])
  const [dislikesText, setDislikesText] = useState('')

  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [expired, setExpired] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<string[]>([])
  const [runResult, setRunResult] = useState<RecommendationResponse | null>(null)
  const [copied, setCopied] = useState(false)

  const refreshPlan = useCallback(async (s: DeviceSession) => {
    try {
      const fresh = await getPlan(s.planId, s.shareToken)
      setPlan(fresh)
      setExpired(false)
      if (fresh.latest_recommendation) onMode(fresh.latest_recommendation.demo_mode)
    } catch (err) {
      if (err instanceof ApiError && err.status === 410) { setExpired(true); setPlan(null) }
      else setError(describeError(err))
    }
  }, [onMode])

  // Restore a session-scoped plan on load (tokens live only in sessionStorage).
  useEffect(() => {
    const restored = loadSession()
    if (restored) { setSession(restored); void refreshPlan(restored) }
  }, [refreshPlan])

  // Prefill the prefs editor from the server's saved values for this participant.
  useEffect(() => {
    if (!plan || !session?.participant) return
    const me = plan.participants.find((p) => p.participant_id === session.participant!.participantId)
    if (me && me.has_preferences) {
      setInterestRows(rowsFromSaved(me.interests, me.resolved_interests))
      setDislikesText(me.dislikes.join(', '))
    }
  }, [plan, session])

  function persist(next: DeviceSession) { saveSession(next); setSession(next) }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setError(''); setFieldErrors([])
    const errs: string[] = []
    if (location.trim().length < 2) errs.push('Enter a location (at least 2 characters).')
    if (budget.trim()) {
      const n = Number(budget)
      if (!Number.isFinite(n) || n <= 0) errs.push('Budget must be a positive number, or leave it blank.')
      else if (n > 100000) errs.push('Budget looks too large (max 100000).')
    }
    if (errs.length) { setFieldErrors(errs); return }
    setBusy(true)
    try {
      const body: { location: string; budget_per_person?: number } = { location: location.trim() }
      if (budget.trim()) body.budget_per_person = Number(budget)
      const created = await createPlan(body)
      const next: DeviceSession = { planId: created.plan_id, shareToken: created.share_token }
      persist(next)
      await refreshPlan(next)
    } catch (err) { setError(describeError(err)) } finally { setBusy(false) }
  }

  async function handleJoin(e: React.FormEvent) {
    e.preventDefault()
    setError(''); setExpired(false)
    const errs = validateJoinInput(joinPlanId, joinToken)
    setFieldErrors(errs)
    if (errs.length) return
    setBusy(true)
    try {
      const planId = cleanCode(joinPlanId)
      const shareToken = cleanCode(joinToken)
      const fetched = await getPlan(planId, shareToken) // validates credential
      const next: DeviceSession = { planId, shareToken }
      persist(next)
      setPlan(fetched)
      if (fetched.latest_recommendation) onMode(fetched.latest_recommendation.demo_mode)
    } catch (err) { setError(describeError(err)) } finally { setBusy(false) }
  }

  async function handleJoinAsSelf(e: React.FormEvent) {
    e.preventDefault()
    if (!session) return
    setError(''); setFieldErrors([])
    if (!displayName.trim()) { setFieldErrors(['Enter your name so the group knows who you are.']); return }
    setBusy(true)
    try {
      const joined = await joinPlan(session.planId, session.shareToken, displayName.trim())
      const next: DeviceSession = {
        ...session,
        participant: {
          participantId: joined.participant_id,
          participantToken: joined.participant_token,
          displayName: displayName.trim(),
        },
      }
      persist(next)
      await refreshPlan(next)
    } catch (err) { setError(describeError(err)) } finally { setBusy(false) }
  }

  async function handleSavePrefs(e: React.FormEvent) {
    e.preventDefault()
    if (!session?.participant) return
    setError(''); setFieldErrors([])
    const rowErrors = validateInterestRows(interestRows)
    if (rowErrors.length) { setFieldErrors(rowErrors); return }
    const { interests, resolved_interests } = buildInterestPayload(interestRows)
    const dislikes = normalizeInterests(dislikesText)
    setBusy(true)
    try {
      await setPreferences(session.planId, session.participant.participantId,
        session.participant.participantToken, { interests, resolved_interests, dislikes })
      await refreshPlan(session)
    } catch (err) { setError(describeError(err)) } finally { setBusy(false) }
  }

  async function handleGenerate() {
    if (!session) return
    setError(''); setRunResult(null)
    setBusy(true)
    try {
      const response = await runPlanRecommendations(session.planId, session.shareToken)
      setRunResult(response)
      onMode(response.demo_mode)
      await refreshPlan(session)
    } catch (err) { setError(describeError(err)) } finally { setBusy(false) }
  }

  function leavePlan() {
    clearSession()
    setSession(null); setPlan(null); setRunResult(null); setError(''); setExpired(false)
    setScreen('choose'); setFieldErrors([])
    setDisplayName(''); setInterestRows([newRow()]); setDislikesText('')
    setJoinPlanId(''); setJoinToken('')
  }

  async function copyInvite() {
    if (!session) return
    try {
      await navigator.clipboard.writeText(formatInviteText(session.planId, session.shareToken))
      setCopied(true); setTimeout(() => setCopied(false), 2000)
    } catch { /* clipboard blocked; the code is visible on screen to copy manually */ }
  }

  const me = plan && session?.participant
    ? plan.participants.find((p) => p.participant_id === session.participant!.participantId)
    : undefined
  const readyCount = plan ? plan.participants.filter((p) => p.has_preferences).length : 0
  const canGenerate = readyCount >= 2
  // Saved interests nobody has confirmed to a Qloo entity: the server leaves them out of a run.
  const pendingConfirmation = plan
    ? plan.participants
      .filter((p) => p.has_preferences)
      .map((p) => ({ name: p.display_name, terms: unconfirmedSavedInterests(p.interests, p.resolved_interests) }))
      .filter((p) => p.terms.length > 0)
    : []
  const latest = runResult ?? plan?.latest_recommendation ?? null

  // --- Expired state ---
  if (expired) {
    return (
      <section className="workspace single">
        <div className="planner-card">
          <div className="state-block">
            <AlertTriangle size={30} className="state-icon warn" />
            <h2>This plan has expired</h2>
            <p className="helper">Plans last 24 hours. Start a fresh one to keep going.</p>
            <button className="submit-button" type="button" onClick={leavePlan}>Start a new plan</button>
          </div>
        </div>
      </section>
    )
  }

  // --- Pre-plan: choose / create / join ---
  if (!session) {
    return (
      <section className="workspace single">
        <div className="planner-card">
          {screen === 'choose' && (
            <>
              <div className="section-heading"><div><span className="step">01</span><h2>Start together</h2></div></div>
              <p className="helper">
                Create a plan and invite friends on their own devices, or join a plan someone shared with you.
              </p>
              <div className="choice-grid">
                <button type="button" className="choice-card" onClick={() => { setScreen('create'); setFieldErrors([]); setError('') }}>
                  <Compass size={22} /><strong>Start a new plan</strong>
                  <span>Pick a place; get a share code for your friends.</span>
                </button>
                <button type="button" className="choice-card" onClick={() => { setScreen('join'); setFieldErrors([]); setError('') }}>
                  <Users size={22} /><strong>Join a plan</strong>
                  <span>Paste the Plan ID and share code you were sent.</span>
                </button>
              </div>
            </>
          )}

          {screen === 'create' && (
            <form onSubmit={handleCreate} noValidate>
              <div className="section-heading">
                <div><span className="step">01</span><h2>Create a plan</h2></div>
                <button type="button" className="text-button muted" onClick={() => setScreen('choose')}>Back</button>
              </div>
              <label className="field-label" htmlFor="c-location">Where are you planning?</label>
              <div className="input-with-icon">
                <MapPin size={17} />
                <input id="c-location" value={location} maxLength={160}
                  onChange={(e) => setLocation(e.target.value)} placeholder="City or neighbourhood" />
              </div>
              <label className="field-label" htmlFor="c-budget">Budget per person (optional)</label>
              <div className="input-with-icon budget-input">
                <span className="currency">₹</span>
                <input id="c-budget" type="number" min="1" max="100000" value={budget}
                  onChange={(e) => setBudget(e.target.value)} placeholder="e.g. 800" />
              </div>
              {fieldErrors.length > 0 && (
                <ul className="validation-errors" role="alert">{fieldErrors.map((m) => <li key={m}>{m}</li>)}</ul>
              )}
              <button className="submit-button" type="submit" disabled={busy}>
                {busy ? <><LoaderCircle className="spinner" size={17} /> Creating…</> : <>Create plan <ArrowUpRight size={17} /></>}
              </button>
            </form>
          )}

          {screen === 'join' && (
            <form onSubmit={handleJoin} noValidate>
              <div className="section-heading">
                <div><span className="step">01</span><h2>Join a plan</h2></div>
                <button type="button" className="text-button muted" onClick={() => setScreen('choose')}>Back</button>
              </div>
              <p className="helper">Enter the details your friend shared. These were sent to you directly, not as a link.</p>
              <label className="field-label" htmlFor="j-id">Plan ID</label>
              <input id="j-id" className="plain-input" value={joinPlanId}
                onChange={(e) => setJoinPlanId(e.target.value)} placeholder="e.g. 7f3a1b2c-…" />
              <label className="field-label interests-label" htmlFor="j-token">Share code</label>
              <input id="j-token" className="plain-input" value={joinToken}
                onChange={(e) => setJoinToken(e.target.value)} placeholder="Paste the private share code" />
              {fieldErrors.length > 0 && (
                <ul className="validation-errors" role="alert">{fieldErrors.map((m) => <li key={m}>{m}</li>)}</ul>
              )}
              <button className="submit-button" type="submit" disabled={busy}>
                {busy ? <><LoaderCircle className="spinner" size={17} /> Finding plan…</> : <>Join plan <ArrowUpRight size={17} /></>}
              </button>
            </form>
          )}
          {error && <p className="warning" style={{ marginTop: 14 }}>{error}</p>}
        </div>
      </section>
    )
  }

  // --- Plan view ---
  const hoursLeft = plan ? hoursUntil(plan.expires_at) : null
  return (
    <section className="workspace">
      <div className="planner-card">
        <div className="section-heading">
          <div><span className="step">★</span><h2>Your plan</h2></div>
          <button type="button" className="text-button muted" onClick={leavePlan}><LogOut size={13} /> Leave</button>
        </div>

        {plan ? (
          <>
            <div className="plan-facts">
              <span><MapPin size={13} /> {plan.location}</span>
              <span>Status: {plan.status}</span>
              {hoursLeft !== null && <span>Expires in ~{hoursLeft}h</span>}
            </div>

            <div className="invite-note">
              <Info size={13} />
              <span>Share these with friends over a trusted channel (message/DM) — not a public post. The share code is private.</span>
            </div>
            <label className="field-label">Plan ID</label>
            <input className="plain-input mono" readOnly value={plan.plan_id} onFocus={(e) => e.currentTarget.select()} />
            <label className="field-label interests-label">Share code</label>
            <input className="plain-input mono" readOnly value={session.shareToken} onFocus={(e) => e.currentTarget.select()} />
            <button type="button" className="add-person" onClick={copyInvite}>
              {copied ? <><Check size={15} /> Copied invite</> : <><ClipboardCopy size={15} /> Copy invite details</>}
            </button>

            <div className="section-heading participant-heading">
              <div><span className="step">✓</span><h2>Your preferences</h2></div>
            </div>
            {!session.participant ? (
              <form onSubmit={handleJoinAsSelf} noValidate>
                <p className="helper">Add yourself to this plan to contribute your cultural interests.</p>
                <label className="field-label" htmlFor="self-name">Your name</label>
                <input id="self-name" className="plain-input" value={displayName} maxLength={60}
                  onChange={(e) => setDisplayName(e.target.value)} placeholder="Name or nickname" />
                {fieldErrors.length > 0 && (
                  <ul className="validation-errors" role="alert">{fieldErrors.map((m) => <li key={m}>{m}</li>)}</ul>
                )}
                <button className="submit-button" type="submit" disabled={busy}>
                  {busy ? <><LoaderCircle className="spinner" size={17} /> Joining…</> : <>Join as myself</>}
                </button>
              </form>
            ) : (
              <form onSubmit={handleSavePrefs} noValidate>
                <p className="helper">
                  You're in as <strong>{session.participant.displayName}</strong>.
                  {me?.has_preferences ? ' Your saved interests are below — edit any time.' : ' Add up to three interests.'}
                </p>
                <label className="field-label">Interests</label>
                <InterestPicker idPrefix="pref" rows={interestRows} onChange={setInterestRows} />
                <label className="field-label interests-label" htmlFor="pref-dislikes">Dislikes (optional)</label>
                <input id="pref-dislikes" className="plain-input" value={dislikesText}
                  onChange={(e) => setDislikesText(e.target.value)} placeholder="Exact names to exclude" />
                {fieldErrors.length > 0 && (
                  <ul className="validation-errors" role="alert">{fieldErrors.map((m) => <li key={m}>{m}</li>)}</ul>
                )}
                <button className="submit-button" type="submit" disabled={busy}>
                  {busy ? <><LoaderCircle className="spinner" size={17} /> Saving…</> : <>{me?.has_preferences ? 'Update' : 'Save'} my preferences</>}
                </button>
              </form>
            )}

            <div className="section-heading participant-heading">
              <div><span className="step">→</span><h2>Recommendations</h2></div>
              <button type="button" className="text-button" onClick={() => void refreshPlan(session)} disabled={busy}>
                <RefreshCw size={12} /> Refresh
              </button>
            </div>
            <p className="helper">
              {readyCount}/{plan.participants.length} participant(s) have added interests.
              {canGenerate ? ' Ready to generate.' : ' At least two are needed before generating.'}
            </p>
            {pendingConfirmation.length > 0 && (
              <p className="warning" role="status">
                Not yet confirmed to a Qloo entity, so they would be left out:{' '}
                {pendingConfirmation.map((p) => `${p.name}: ${p.terms.join(', ')}`).join('; ')}.
                Each person confirms their own interests by updating their preferences.
              </p>
            )}
            <button className="submit-button" type="button" onClick={handleGenerate} disabled={busy || !canGenerate}>
              {busy ? <><LoaderCircle className="spinner" size={17} /> Working…</> : <>Generate group recommendations <ArrowUpRight size={17} /></>}
            </button>
            {error && <p className="warning" style={{ marginTop: 14 }}>{error}</p>}
          </>
        ) : (
          <div className="state-block">
            <LoaderCircle className="spinner" size={26} />
            <p className="helper">Loading your plan…</p>
            {error && <p className="warning">{error}</p>}
          </div>
        )}
      </div>

      <aside className="side-panel">
        {plan && (
          <div className="results-panel">
            <div className="results-heading">
              <div><span className="eyebrow">THE GROUP</span><h2>Who's in</h2></div>
              <span className="small-muted">{plan.participants.length}/{plan.max_participants}</span>
            </div>
            {plan.participants.length === 0 ? (
              <p className="helper">No one has joined yet. Share the invite to get started.</p>
            ) : (
              <div className="roster">
                {plan.participants.map((p) => (
                  <div className="roster-row" key={p.participant_id}>
                    <span className="roster-name">
                      {p.display_name}
                      {session.participant?.participantId === p.participant_id && <em> (you)</em>}
                    </span>
                    {p.has_preferences
                      ? (
                        <span className="chip-ready">
                          <Check size={12} /> {p.interests.join(', ')}
                          {unconfirmedSavedInterests(p.interests, p.resolved_interests).length > 0 &&
                            <em> · needs confirmation</em>}
                        </span>
                      )
                      : <span className="chip-waiting">no interests yet</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {latest
          ? <ResultsPanel result={latest} participantCount={plan?.participants.length ?? 0}
              eyebrow="YOUR CULTURAL THREAD" title="Three ways to go" />
          : plan && (
            <div className="empty-state compact">
              <div className="empty-icon"><Compass size={30} strokeWidth={1.5} /></div>
              <h3>No recommendations yet</h3>
              <p>Once two people add interests, generate your group's cultural thread.</p>
            </div>
          )}
      </aside>
    </section>
  )
}
