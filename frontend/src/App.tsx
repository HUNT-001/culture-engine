import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Compass, Info, LoaderCircle, Sparkles, Zap } from 'lucide-react'
import { getHealth } from './api/client'
import CollaborativePlanner from './components/CollaborativePlanner'
import QuickPlanner from './components/QuickPlanner'

type Mode = 'unknown' | 'live' | 'demo' | 'offline'
type Flow = 'collaborative' | 'quick'

export default function App() {
  const [mode, setMode] = useState<Mode>('unknown')
  const [flow, setFlow] = useState<Flow>('collaborative')

  // Proactively surface whether the backend is in live or demo mode.
  useEffect(() => {
    let active = true
    getHealth()
      .then((health) => { if (active) setMode(health.demo_mode ? 'demo' : 'live') })
      .catch(() => { if (active) setMode('offline') })
    return () => { active = false }
  }, [])

  const setModeFromResult = (demo: boolean) => setMode(demo ? 'demo' : 'live')

  const modePill = useMemo(() => {
    switch (mode) {
      case 'live': return { cls: 'mode-live', icon: <Zap size={12} />, text: 'Live Qloo' }
      case 'demo': return { cls: 'mode-demo', icon: <Info size={12} />, text: 'Demo mode' }
      case 'offline': return { cls: 'mode-offline', icon: <AlertTriangle size={12} />, text: 'Backend offline' }
      default: return { cls: 'mode-unknown', icon: <LoaderCircle size={12} className="spinner" />, text: 'Checking…' }
    }
  }, [mode])

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

      <section className="hero" id="top">
        <div className="eyebrow"><Sparkles size={14} /> LESS SCROLLING. BETTER PLANS.</div>
        <h1>Different tastes.<br /><span>One great plan.</span></h1>
        <p className="hero-copy">
          Tell us what everyone loves. Common Thread uses Qloo's cultural graph to find the thread
          that turns different interests into one shared experience.
        </p>
        <div className="flow-switch" role="tablist" aria-label="Planning mode">
          <button type="button" role="tab" aria-selected={flow === 'collaborative'}
            className={flow === 'collaborative' ? 'active' : ''} onClick={() => setFlow('collaborative')}>
            Collaborative <span>multi-device</span>
          </button>
          <button type="button" role="tab" aria-selected={flow === 'quick'}
            className={flow === 'quick' ? 'active' : ''} onClick={() => setFlow('quick')}>
            Quick <span>same device</span>
          </button>
        </div>
      </section>

      {flow === 'collaborative'
        ? <CollaborativePlanner onMode={setModeFromResult} />
        : <QuickPlanner onMode={setModeFromResult} />}

      <footer className="footer">
        <span>COMMON THREAD · PROTOTYPE 0.1</span>
        <span>Built around culture, not just proximity.</span>
      </footer>
    </main>
  )
}
