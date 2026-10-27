import { useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, ArrowDown, Info, LoaderCircle, Users, Zap } from 'lucide-react'
import { getHealth } from './api/client'
import CollaborativePlanner from './components/CollaborativePlanner'
import QuickPlanner from './components/QuickPlanner'
import ThreadArt, { ThreadMark } from './components/ThreadArt'

type Mode = 'unknown' | 'live' | 'demo' | 'offline'
type Flow = 'collaborative' | 'quick'

const BEATS = [
  { n: '1', title: 'Add what you love', text: 'A band, a film, a cuisine — each person brings their own.' },
  { n: '2', title: 'Confirm what you mean', text: 'You pick the exact Qloo entity. Nothing is guessed.' },
  { n: '3', title: 'See where tastes meet', text: 'Shared ground, bridges and a stretch pick, with the signals behind them.' },
]

export default function App() {
  const [mode, setMode] = useState<Mode>('unknown')
  const [flow, setFlow] = useState<Flow>('collaborative')
  const stageRef = useRef<HTMLElement>(null)

  // Proactively surface whether the backend is in live or demo mode.
  useEffect(() => {
    let active = true
    getHealth()
      .then((health) => { if (active) setMode(health.demo_mode ? 'demo' : 'live') })
      .catch(() => { if (active) setMode('offline') })
    return () => { active = false }
  }, [])

  const setModeFromResult = (demo: boolean) => setMode(demo ? 'demo' : 'live')

  function start(next: Flow) {
    setFlow(next)
    const reduce = typeof window.matchMedia === 'function'
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches
    stageRef.current?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' })
  }

  const modePill = useMemo(() => {
    switch (mode) {
      case 'live': return { cls: 'mode-live', icon: <Zap size={12} />, text: 'Live Qloo' }
      case 'demo': return { cls: 'mode-demo', icon: <Info size={12} />, text: 'Demo mode' }
      case 'offline': return { cls: 'mode-offline', icon: <AlertTriangle size={12} />, text: 'Backend offline' }
      default: return { cls: 'mode-unknown', icon: <LoaderCircle size={12} className="spinner" />, text: 'Checking…' }
    }
  }, [mode])

  return (
    <>
      <a className="skip-link" href="#planner">Skip to the planner</a>

      <header className="hero-band">
        <div className="hero-mesh" aria-hidden="true" />
        <div className="page-shell">
          <nav className="topbar" aria-label="Common Thread">
            <a className="brand" href="#top" aria-label="Common Thread home">
              <ThreadMark /> <span>common thread</span>
            </a>
            <span className={`mode-pill ${modePill.cls}`} role="status" title="Backend provider mode">
              {modePill.icon} {modePill.text}
            </span>
          </nav>

          <section className="hero" id="top">
            <div className="hero-copy-col">
              <p className="eyebrow">Qloo-powered cultural discovery for groups</p>
              <h1>Where different tastes <em>meet</em></h1>
              <p className="hero-copy">
                Everyone brings something they love. Common Thread uses Qloo's cultural graph to find
                the places where those tastes overlap, and shows the signals behind every pick.
              </p>
              <div className="hero-actions">
                <button type="button" className="btn btn-hero" onClick={() => start('collaborative')}>
                  <Users size={17} /> Start a shared plan
                </button>
                <button type="button" className="btn btn-glass" onClick={() => start('quick')}>
                  Try the Quick Planner
                </button>
              </div>
              <p className="hero-hint">Shared plans work across devices. Quick Planner keeps everyone on this screen.</p>
            </div>
            <ThreadArt />
          </section>

          <ol className="beats" aria-label="How it works">
            {BEATS.map((b) => (
              <li key={b.n}>
                <span className="beat-n" aria-hidden="true">{b.n}</span>
                <div><strong>{b.title}</strong><span>{b.text}</span></div>
              </li>
            ))}
          </ol>
        </div>
      </header>

      <main className="stage" id="planner" ref={stageRef} tabIndex={-1}>
        <div className="ambient" aria-hidden="true" />
        <div className="page-shell">
          <div className="stage-head">
            <p className="stage-kicker"><ArrowDown size={14} aria-hidden="true" /> Choose how you want to plan</p>
            <div className="flow-switch" role="tablist" aria-label="Planning mode">
              <button type="button" role="tab" aria-selected={flow === 'collaborative'}
                className={flow === 'collaborative' ? 'active' : ''} onClick={() => setFlow('collaborative')}>
                Collaborative <span>multi-device · invite friends</span>
              </button>
              <button type="button" role="tab" aria-selected={flow === 'quick'}
                className={flow === 'quick' ? 'active' : ''} onClick={() => setFlow('quick')}>
                Quick <span>same device · one screen</span>
              </button>
            </div>
          </div>

          {flow === 'collaborative'
            ? <CollaborativePlanner onMode={setModeFromResult} />
            : <QuickPlanner onMode={setModeFromResult} />}
        </div>
      </main>

      <footer className="footer">
        <div className="page-shell footer-inner">
          <span>COMMON THREAD · PROTOTYPE 0.1</span>
          <span>Where different tastes meet. Built on Qloo's cultural graph.</span>
        </div>
      </footer>
    </>
  )
}
