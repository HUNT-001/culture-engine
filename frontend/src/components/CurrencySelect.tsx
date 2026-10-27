import { ChevronDown } from 'lucide-react'
import { CURRENCIES, currencyName } from '../lib/currency'

type Props = { id: string; value: string; onChange: (code: string) => void }

/** A native <select> (keyboard + screen-reader behaviour for free) drawn as a small code chip.
 *  The chip shows the ISO code; the open list shows "CODE — name". */
export default function CurrencySelect({ id, value, onChange }: Props) {
  return (
    <span className="currency-select">
      <span className="currency-code" aria-hidden="true">{value}<ChevronDown size={12} /></span>
      <select id={id} aria-label="Budget currency" value={value} onChange={(e) => onChange(e.target.value)}>
        {CURRENCIES.map((c) => <option key={c.code} value={c.code}>{c.code} — {c.name}</option>)}
      </select>
      <span className="sr-only" role="status">Budget in {currencyName(value)} ({value})</span>
    </span>
  )
}
