import { Check } from 'lucide-react'

type Props = {
  steps: string[]
  /** Zero-based index of the step the user is on; a value >= steps.length means "all done". */
  current: number
  label?: string
}

/** Compact progress indicator. Pure presentation: callers derive `current` from existing state. */
export default function Stepper({ steps, current, label = 'Progress' }: Props) {
  return (
    <ol className="stepper" aria-label={label}>
      {steps.map((step, i) => {
        const state = i < current ? 'done' : i === current ? 'current' : 'todo'
        return (
          <li key={step} className={`stepper-item is-${state}`} aria-current={state === 'current' ? 'step' : undefined}>
            <span className="stepper-dot" aria-hidden="true">
              {state === 'done' ? <Check size={13} strokeWidth={3} /> : i + 1}
            </span>
            <span className="stepper-label">
              {step}
              {state === 'done' && <span className="sr-only"> (done)</span>}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
