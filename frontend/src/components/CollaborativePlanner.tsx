import { useCallback, useEffect, useState } from 'react'
import {
  AlertTriangle, ArrowUpRight, Check, CircleAlert, ClipboardCopy, Compass, Copy, Eye, EyeOff, KeyRound,
  LoaderCircle, LogOut, MapPin, RefreshCw, Users,
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
import { budgetFields, currencySymbol, DEFAULT_CURRENCY, formatMoney } from '../lib/currency'
import { useBudgetCurrency } from '../lib/budgetCurrency'
import { initials } from '../lib/present'
import { clearSession, loadSession, saveSession, type DeviceSession } from '../lib/session'
import { cleanCode, formatInviteText, hoursUntil, validateJoinInput } from '../lib/invite'
import CurrencySelect from './CurrencySelect'
import InterestPicker from './InterestPicker'
import ResultsPanel from './ResultsPanel'
import Stepper from './Stepper'
import ThreadArt from './ThreadArt'

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

/** A read-only credential with its own copy button. A secret (the share code) is masked until
 *  the user chooses to reveal it; copying never needs it on screen. Nothing is logged or put
 *  in a URL, and the value stays in component state only. */
function CredentialField({ id, label, value, secret = false }: {
  id: string; label: string; value: string; secret?: boolean
}) {
  const [shown, setShown] = useState(!secret)
  const [copied, setCopied] = useState(false)
  async function copy() {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true); setTimeout(() => setCopied(false), 2000)
    } catch { /* clipboard blocked: reveal the value and copy it by hand */ setShown(true) }
  }
  return (
    <div className="credential">
      <label className="field-label" htmlFor={id}>{label}</label>
      <div className="credential-row">
        <input id={id} className="input mono" readOnly autoComplete="off" spellCheck={false}
          value={shown ? value : '•'.repeat(Math.min(Math.max(value.length, 8), 24))}
          onFocus={(e) => { if (shown) e.currentTarget.select() }} />
        {secret && (
          <button type="button" className="chip-button" aria-pressed={shown}
            aria-label={`${shown ? 'Hide' : 'Show'} ${label.toLowerCase()}`} onClick={() => setShown((s) => !s)}>
            {shown ? <EyeOff size={14} /> : <Eye size={14} />}<span>{shown ? 'Hide' : 'Show'}</span>
          </button>
        )}
        <button type="button" className={`chip-button${copied ? ' is-done' : ''}`}
          aria-label={`Copy ${label.toLowerCase()}`} onClick={copy}>
          {copied ? <Check size={14} /> : <Copy size={14} />}<span>{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <span className="sr-only" role="status">{copied ? `${label} copied` : ''}</span>
    </div>
  )
}

export default function CollaborativePlanner({ onMode }: Props) {
  const [session, setSession] = useState<DeviceSession | null>(null)
  const [plan, setPlan] = useState<PlanView | null>(null)
  const [screen, setScreen] = useState<'choose' | 'create' | 'join'>('choose')

  // Create form
  const [location, setLocation] = useState('Chennai, Tamil Nadu, India')
  const [budget, setBudget] = useState('')
  const budgetCurrency = useBudgetCurrency(location)
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
      const created = await createPlan({ location: location.trim(), ...budgetFields(budget, budgetCurrency.currency) })
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
    } catch { /* clipboard blocked; reveal the share code above and copy it manually */ }
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

  // Progress is derived from existing state only; it changes no behaviour.
  const stepIndex = !session ? 0
    : !session.participant ? 1
      : !me?.has_preferences ? 2
        : latest ? 4 : 3
  const steps = ['Create or join', 'Add yourself', 'Your interests', 'Group results']

  // --- Expired state ---
  if (expired) {
    return (
      <section className="workspace single">
        <div className="card planner-card">
          <div className="state-block">
            <AlertTriangle size={30} className="state-icon warn" />
            <h2>This plan has expired</h2>
            <p className="helper">Plans last 24 hours. Start a fresh one to keep going.</p>
            <button className="btn btn-primary" type="button" onClick={leavePlan}>Start a new plan</button>
          </div>
        </div>
      </section>
    )
  }

  // --- Pre-plan: choose / create / join ---
  if (!session) {
    return (
      <>
        <Stepper label="Collaborative plan progress" steps={steps} current={stepIndex} />
        <section className="workspace">
          <div className="card planner-card">
            {screen === 'choose' && (
              <>
                <div className="section-heading"><div><span className="step">01</span><h2>Start together</h2></div></div>
                <p className="helper">
                  Create a plan and invite friends on their own devices, or join a plan someone shared with you.
                </p>
                <div className="choice-grid">
                  <button type="button" className="choice-card choice-primary" onClick={() => { setScreen('create'); setFieldErrors([]); setError('') }}>
                    <span className="choice-icon"><Compass size={20} /></span>
                    <strong>Start a new plan</strong>
                    <span>Pick a place; get a share code for your friends.</span>
                    <span className="choice-go" aria-hidden="true">Begin <ArrowUpRight size={14} /></span>
                  </button>
                  <button type="button" className="choice-card" onClick={() => { setScreen('join'); setFieldErrors([]); setError('') }}>
                    <span className="choice-icon"><Users size={20} /></span>
                    <strong>Join a plan</strong>
                    <span>Paste the Plan ID and share code you were sent.</span>
                    <span className="choice-go" aria-hidden="true">Join <ArrowUpRight size={14} /></span>
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
                    onChange={(e) => { setLocation(e.target.value); budgetCurrency.onLocationChange(e.target.value) }}
                    placeholder="City or neighbourhood" />
                </div>
                <label className="field-label" htmlFor="c-budget">Budget per person (optional)</label>
                <div className="input-with-icon budget-input">
                  <span className="currency" aria-hidden="true">{currencySymbol(budgetCurrency.currency)}</span>
                  <input id="c-budget" type="number" min="1" max="100000" value={budget}
                    onChange={(e) => setBudget(e.target.value)} placeholder="e.g. 800" />
                  <CurrencySelect id="c-currency" value={budgetCurrency.currency} onChange={budgetCurrency.setCurrency} />
                </div>
                {fieldErrors.length > 0 && (
                  <ul className="validation-errors" role="alert">{fieldErrors.map((m) => <li key={m}>{m}</li>)}</ul>
                )}
                <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
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
                <input id="j-id" className="input" value={joinPlanId} autoComplete="off"
                  onChange={(e) => setJoinPlanId(e.target.value)} placeholder="e.g. 7f3a1b2c-…" />
                <label className="field-label interests-label" htmlFor="j-token">Share code</label>
                <input id="j-token" className="input" value={joinToken} autoComplete="off"
                  onChange={(e) => setJoinToken(e.target.value)} placeholder="Paste the private share code" />
                {fieldErrors.length > 0 && (
                  <ul className="validation-errors" role="alert">{fieldErrors.map((m) => <li key={m}>{m}</li>)}</ul>
                )}
                <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
                  {busy ? <><LoaderCircle className="spinner" size={17} /> Finding plan…</> : <>Join plan <ArrowUpRight size={17} /></>}
                </button>
              </form>
            )}
            {error && <p className="notice notice-warn"><CircleAlert size={16} /> <span>{error}</span></p>}
          </div>
          <aside className="side-panel preplan-aside">
            <div className="empty-state">
              <ThreadArt variant="compact" />
              <span className="eyebrow">A shared plan</span>
              <h3>Everyone brings<br />their own thread</h3>
              <p>Share the Plan ID and code privately. Each friend adds what they love from their own device.</p>
              <ul className="option-legend">
                <li><i className="legend-dot shared" /><span><strong>Create</strong> a plan and invite friends</span></li>
                <li><i className="legend-dot bridge" /><span><strong>Confirm</strong> each interest to a Qloo entity</span></li>
                <li><i className="legend-dot stretch" /><span><strong>Generate</strong> the group&rsquo;s shared picks</span></li>
              </ul>
            </div>
          </aside>
        </section>
      </>
    )
  }

  // --- Plan view ---
  const hoursLeft = plan ? hoursUntil(plan.expires_at) : null
  return (
    <>
      <Stepper label="Collaborative plan progress" steps={steps} current={stepIndex} />
      <section className="workspace">
        <div className="card planner-card">
          <div className="section-heading">
            <div><span className="step">★</span><h2>Your plan</h2></div>
            <button type="button" className="text-button muted" onClick={leavePlan}><LogOut size={13} /> Leave</button>
          </div>

          {plan ? (
            <>
              <div className="plan-facts">
                <span className="fact"><MapPin size={13} /> {plan.location}</span>
                {plan.budget_per_person != null && (
                  <span className="fact">
                    Budget: {formatMoney(plan.budget_per_person, plan.budget_currency ?? DEFAULT_CURRENCY)} per person
                  </span>
                )}
                <span className="fact">Status: {plan.status}</span>
                {hoursLeft !== null && <span className="fact">Expires in ~{hoursLeft}h</span>}
              </div>

              <div className="invite-card glass">
                <div className="invite-head">
                  <span className="invite-icon"><KeyRound size={16} /></span>
                  <div>
                    <strong>Invite friends</strong>
                    <p>Share these over a trusted channel (message/DM), not a public post. The share code is private
                      and is never put in a link.</p>
                  </div>
                </div>
                <CredentialField id="plan-id" label="Plan ID" value={plan.plan_id} />
                <CredentialField id="share-code" label="Share code" value={session.shareToken} secret />
                <button type="button" className="add-link" onClick={copyInvite}>
                  {copied ? <><Check size={15} /> Copied invite</> : <><ClipboardCopy size={15} /> Copy both as an invite message</>}
                </button>
              </div>

              <div className="section-heading participant-heading">
                <div><span className="step">✓</span><h2>Your preferences</h2></div>
              </div>
              {!session.participant ? (
                <form onSubmit={handleJoinAsSelf} noValidate>
                  <p className="helper">Add yourself to this plan to contribute your cultural interests.</p>
                  <label className="field-label" htmlFor="self-name">Your name</label>
                  <input id="self-name" className="input" value={displayName} maxLength={60}
                    onChange={(e) => setDisplayName(e.target.value)} placeholder="Name or nickname" />
                  {fieldErrors.length > 0 && (
                    <ul className="validation-errors" role="alert">{fieldErrors.map((m) => <li key={m}>{m}</li>)}</ul>
                  )}
                  <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
                    {busy ? <><LoaderCircle className="spinner" size={17} /> Joining…</> : <>Join as myself</>}
                  </button>
                </form>
              ) : (
                <form onSubmit={handleSavePrefs} noValidate>
                  <p className="helper">
                    You're in as <strong>{session.participant.displayName}</strong>.
                    {me?.has_preferences ? ' Your saved interests are below — edit any time.' : ' Add up to three interests.'}
                  </p>
                  <div className="field-label" id="pref-interests-label">Interests</div>
                  <div role="group" aria-labelledby="pref-interests-label">
                    <InterestPicker idPrefix="pref" rows={interestRows} onChange={setInterestRows} />
                  </div>
                  <label className="field-label interests-label" htmlFor="pref-dislikes">Dislikes (optional)</label>
                  <input id="pref-dislikes" className="input" value={dislikesText}
                    onChange={(e) => setDislikesText(e.target.value)} placeholder="Exact names to exclude" />
                  {fieldErrors.length > 0 && (
                    <ul className="validation-errors" role="alert">{fieldErrors.map((m) => <li key={m}>{m}</li>)}</ul>
                  )}
                  <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
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
              <div className="readiness">
                <span className="dots" aria-hidden="true">
                  {plan.participants.map((p) => <i key={p.participant_id} className={p.has_preferences ? 'on' : ''} />)}
                </span>
                <p className="helper">
                  {readyCount}/{plan.participants.length} participant(s) have added interests.
                  {canGenerate ? ' Ready to generate.' : ' At least two are needed before generating.'}
                </p>
              </div>
              {pendingConfirmation.length > 0 && (
                <p className="notice notice-warn" role="status">
                  <CircleAlert size={16} />
                  <span>
                    Not yet confirmed to a Qloo entity, so they would be left out:{' '}
                    {pendingConfirmation.map((p) => `${p.name}: ${p.terms.join(', ')}`).join('; ')}.
                    Each person confirms their own interests by updating their preferences.
                  </span>
                </p>
              )}
              <button className="btn btn-primary btn-block" type="button" onClick={handleGenerate} disabled={busy || !canGenerate}>
                {busy ? <><LoaderCircle className="spinner" size={17} /> Working…</> : <>Generate group recommendations <ArrowUpRight size={17} /></>}
              </button>
              {error && <p className="notice notice-warn"><CircleAlert size={16} /> <span>{error}</span></p>}
            </>
          ) : (
            <div className="state-block">
              <LoaderCircle className="spinner" size={26} />
              <p className="helper">Loading your plan…</p>
              {error && <p className="notice notice-warn"><CircleAlert size={16} /> <span>{error}</span></p>}
            </div>
          )}
        </div>

        <aside className="side-panel" aria-live="polite">
          {plan && (
            <div className="group-card glass">
              <div className="results-heading">
                <div><span className="eyebrow">The group</span><h2>Who's in</h2></div>
                <span className="small-muted">{plan.participants.length}/{plan.max_participants}</span>
              </div>
              {plan.participants.length === 0 ? (
                <p className="helper">No one has joined yet. Share the invite to get started.</p>
              ) : (
                <ul className="roster">
                  {plan.participants.map((p, i) => {
                    const pending = new Set(unconfirmedSavedInterests(p.interests, p.resolved_interests).map((t) => t.trim().toLowerCase()))
                    return (
                      <li className="roster-row" key={p.participant_id}>
                        <span className="avatar" data-tone={i % 4} aria-hidden="true">{initials(p.display_name)}</span>
                        <div className="roster-main">
                          <span className="roster-name">
                            {p.display_name}
                            {session.participant?.participantId === p.participant_id && <em> (you)</em>}
                          </span>
                          {p.has_preferences ? (
                            <span className="roster-tags">
                              {p.interests.map((t) => pending.has(t.trim().toLowerCase())
                                ? <span className="tag tag-pending" key={t}><CircleAlert size={11} /> {t}<span className="sr-only"> — needs confirmation</span></span>
                                : <span className="tag tag-ok" key={t}><Check size={11} strokeWidth={3} /> {t}</span>)}
                            </span>
                          ) : <span className="chip-waiting">no interests yet</span>}
                        </div>
                      </li>
                    )
                  })}
                </ul>
              )}
              {pendingConfirmation.length > 0 && (
                <p className="legend-note"><span className="tag tag-pending"><CircleAlert size={11} /> amber</span> interests still need their owner to confirm a Qloo entity.</p>
              )}
            </div>
          )}

          {latest
            ? <ResultsPanel result={latest} participantCount={plan?.participants.length ?? 0}
                eyebrow="YOUR CULTURAL THREAD" title="Three ways to go" />
            : plan && (
              <div className="empty-state compact">
                <ThreadArt variant="compact" />
                <h3>No recommendations yet</h3>
                <p>Once two people add interests, generate your group's cultural thread.</p>
              </div>
            )}
        </aside>
      </section>
    </>
  )
}
