import { useState } from 'react'
import { ArrowUpRight, Compass, LoaderCircle, MapPin, Plus, Sparkles, Users, X } from 'lucide-react'
import { getRecommendations } from './api/client'
import type { ParticipantInput, RecommendationResponse } from './types'

const initialParticipants: ParticipantInput[] = [
  { participant_id: 'p1', display_name: 'Friend 1', interests: ['indie rock', 'anime'] },
  { participant_id: 'p2', display_name: 'Friend 2', interests: ['specialty coffee', 'illustration'] },
]

const optionNames: Record<string, string> = {
  shared_ground: 'Shared Ground',
  cultural_bridge: 'Cultural Bridge',
  stretch_choice: 'Stretch Choice',
  alternative: 'Alternative',
}

export default function App() {
  const [location, setLocation] = useState('Chennai, Tamil Nadu, India')
  const [budget, setBudget] = useState('800')
  const [participants, setParticipants] = useState<ParticipantInput[]>(initialParticipants)
  const [result, setResult] = useState<RecommendationResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  function updateParticipant(index: number, patch: Partial<ParticipantInput>) {
    setParticipants((current) => current.map((person, i) => i === index ? { ...person, ...patch } : person))
  }

  function addParticipant() {
    if (participants.length >= 4) return
    const index = participants.length + 1
    setParticipants((current) => [...current, {
      participant_id: `p${Date.now()}`,
      display_name: `Friend ${index}`,
      interests: ['music', 'films'],
    }])
  }

  function removeParticipant(index: number) {
    if (participants.length <= 2) return
    setParticipants((current) => current.filter((_, i) => i !== index))
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const payload = {
        location: location.trim(),
        ...(budget.trim() ? { budget_per_person: Number(budget) } : {}),
        participants: participants.map((person) => ({
          ...person,
          display_name: person.display_name.trim(),
          interests: person.interests.map((x) => x.trim()).filter(Boolean).slice(0, 3),
        })),
      }
      setResult(await getRecommendations(payload))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="page-shell">
      <nav className="topbar">
        <a className="brand" href="#top" aria-label="Common Thread home"><span className="brand-mark"><Compass size={20} /></span> common thread</a>
        <span className="top-note"><span className="status-dot" /> Cultural discovery for groups</span>
      </nav>

      <section className="hero" id="top">
        <div className="eyebrow"><Sparkles size={14} /> LESS SCROLLING. BETTER PLANS.</div>
        <h1>Different tastes.<br /><span>One great plan.</span></h1>
        <p className="hero-copy">Tell us what everyone loves. We'll look for the cultural thread that could turn those different interests into a shared experience.</p>
      </section>

      <section className="workspace">
        <form className="planner-card" onSubmit={submit}>
          <div className="section-heading"><div><span className="step">01</span><h2>Set the scene</h2></div><span className="small-muted">About 1 minute</span></div>
          <label className="field-label" htmlFor="location">Where are you planning?</label>
          <div className="input-with-icon"><MapPin size={17} /><input id="location" required minLength={2} maxLength={160} value={location} onChange={(e) => setLocation(e.target.value)} placeholder="City or neighbourhood" /></div>
          <label className="field-label" htmlFor="budget">Budget per person (optional)</label>
          <div className="input-with-icon budget-input"><span className="currency">₹</span><input id="budget" type="number" min="1" max="100000" value={budget} onChange={(e) => setBudget(e.target.value)} placeholder="800" /></div>

          <div className="section-heading participant-heading"><div><span className="step">02</span><h2>Who's coming?</h2></div><span className="small-muted">{participants.length}/4 people</span></div>
          <p className="helper">Add up to three interests per person. Mix categories—music, films, games, art, brands or anything supported by Qloo.</p>
          <div className="participants-list">
            {participants.map((person, index) => (
              <div className="participant" key={person.participant_id}>
                <div className="participant-top"><label className="field-label" htmlFor={`name-${index}`}>Participant {index + 1}</label>{participants.length > 2 && <button className="icon-button" type="button" aria-label="Remove participant" onClick={() => removeParticipant(index)}><X size={15} /></button>}</div>
                <input id={`name-${index}`} className="plain-input" value={person.display_name} onChange={(e) => updateParticipant(index, { display_name: e.target.value })} required maxLength={60} placeholder="Name or nickname" />
                <label className="field-label interests-label" htmlFor={`interests-${index}`}>Interests (comma-separated)</label>
                <input id={`interests-${index}`} className="plain-input" value={person.interests.join(', ')} onChange={(e) => updateParticipant(index, { interests: e.target.value.split(',').map((x) => x.trim()).filter(Boolean).slice(0, 3) })} required placeholder="e.g. indie rock, anime, coffee" />
              </div>
            ))}
          </div>
          {participants.length < 4 && <button type="button" className="add-person" onClick={addParticipant}><Plus size={15} /> Add someone else</button>}
          <button className="submit-button" type="submit" disabled={loading}>{loading ? <><LoaderCircle className="spinner" size={17} /> Finding your cultural thread…</> : <>Find our shared next thing <ArrowUpRight size={18} /></>}</button>
          <p className="privacy-note"><Users size={14} /> No account required for this prototype. Avoid entering sensitive personal information.</p>
        </form>

        <aside className="side-panel">
          {!result && !error && <div className="empty-state"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="empty-icon"><Compass size={34} strokeWidth={1.5} /></div><span className="empty-eyebrow">THE CULTURAL BRIDGE</span><h3>What connects<br />your different worlds?</h3><p>We compare everyone's cultural interests to find shared ground, unexpected links and one worthwhile wildcard.</p><div className="option-legend"><span><i className="legend-dot shared" />Shared Ground</span><span><i className="legend-dot bridge" />Cultural Bridge</span><span><i className="legend-dot stretch" />Stretch Choice</span></div></div>}
          {error && <div className="error-card"><h3>We couldn't finish that plan.</h3><p>{error}</p><p className="helper">Check that the backend is running, then try again. If deployed on a free tier, the first request may take longer while the service wakes up.</p></div>}
          {result && <div className="results-panel"><div className="results-heading"><div><span className="eyebrow">YOUR CULTURAL THREAD</span><h2>Three ways to go</h2></div><button type="button" className="text-button" onClick={() => setResult(null)}>New plan</button></div>
            {result.demo_mode && <div className="demo-banner">Demo mode — results are synthetic and are not real venue recommendations.</div>}
            {result.warnings.map((warning, i) => <p className="warning" key={i}>{warning}</p>)}
            {result.unresolved_interests.length > 0 && <p className="warning">Unresolved interests: {result.unresolved_interests.join(', ')}</p>}
            {result.options.map((option, i) => <article className={`result-card option-${option.option_type}`} key={option.candidate.entity_id}><div className="result-meta"><span className="option-index">0{i + 1}</span><span className="option-type">{optionNames[option.option_type] || 'Alternative'}</span><span className={`verification verification-${option.candidate.verification_status}`}>{option.candidate.verification_status === 'demo' ? 'DEMO' : 'NOT VERIFIED'}</span></div><h3>{option.candidate.name}</h3><p>{option.explanation}</p><div className="evidence-list">{option.evidence_labels.slice(0, 3).map((label) => <span key={label}>{label}</span>)}</div>{option.candidate.maps_search_url && <a className="map-link" href={option.candidate.maps_search_url} target="_blank" rel="noreferrer">Search on Maps <ArrowUpRight size={14} /></a>}</article>)}
            <p className="disclaimer">Cultural affinity is a discovery signal, not a guarantee of enjoyment. Check venue details before travelling.</p>
          </div>}
        </aside>
      </section>
      <footer className="footer"><span>COMMON THREAD · PROTOTYPE 0.1</span><span>Built around culture, not just proximity.</span></footer>
    </main>
  )
}
