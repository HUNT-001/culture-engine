import { describe, expect, it } from 'vitest'
import {
  applyLocation, applyManualCurrency, initialCurrencyState, restoreCurrencyState, type CurrencyState,
} from './budgetCurrency'

/** Feed a sequence of location edits through the reducer, like keystrokes. */
function typeInto(state: CurrencyState, ...locations: string[]): CurrencyState {
  return locations.reduce(applyLocation, state)
}

describe('automatic currency', () => {
  it('starts from the destination, else from the default', () => {
    expect(initialCurrencyState('Chennai, Tamil Nadu, India').currency).toBe('INR')
    expect(initialCurrencyState('Austin, Texas, United States').currency).toBe('USD')
    expect(initialCurrencyState('Somewhere unknown').currency).toBe('INR')
    expect(initialCurrencyState('', 'GBP').currency).toBe('GBP')
  })

  it('follows the destination when the country changes and nothing was overridden', () => {
    let s = initialCurrencyState('Chennai, Tamil Nadu, India')
    s = typeInto(s, 'Austin, Texas, United States')
    expect(s.currency).toBe('USD')
    s = typeInto(s, 'London, United Kingdom')
    expect(s.currency).toBe('GBP')
    s = typeInto(s, 'New York, USA')
    expect(s.currency).toBe('USD')
  })

  it('does not flicker while the destination is being typed, cleared and re-entered', () => {
    let s = initialCurrencyState('Chennai, Tamil Nadu, India')
    const seen = new Set<string>()
    for (const keystroke of [
      'Chennai, Tamil Nadu, Indi', 'Chennai, Tamil Nadu, Ind', 'Chennai, Tamil Nadu, ', 'Chennai', '', '   ',
      'A', 'Au', 'Aus', 'Austin', 'Austin,', 'Austin, T', 'Austin, Tex',
    ]) {
      s = applyLocation(s, keystroke)
      seen.add(s.currency)
    }
    expect([...seen]).toEqual(['INR'])        // unrecognisable text never changes the currency
    s = typeInto(s, 'Austin, Texas')
    expect(s.currency).toBe('USD')
    expect(typeInto(s, 'Austin, Texas, Unit', 'Austin, Texas, United States').currency).toBe('USD')
  })

  it('returns the very same state for an unchanged country (no needless re-render)', () => {
    const s = initialCurrencyState('Austin, Texas')
    expect(applyLocation(s, 'Houston, Texas')).toBe(s)
    expect(applyLocation(s, '')).toBe(s)
  })

  it('keeps the current currency for an ambiguous location', () => {
    const s = initialCurrencyState('Austin, Texas')
    expect(applyLocation(s, 'Georgia').currency).toBe('USD')
    expect(applyLocation(s, 'Paris').currency).toBe('USD')
  })
})

describe('manual override', () => {
  it('works, and is not overwritten by detection for the same destination', () => {
    let s = initialCurrencyState('Chennai, Tamil Nadu, India')
    s = applyManualCurrency(s, 'USD')
    expect(s).toMatchObject({ currency: 'USD', overridden: true })
    // Editing within the same country (or typing a city) must not touch the user's choice.
    s = typeInto(s, 'Chennai, Tamil Nadu, India', 'Madurai, Tamil Nadu, India', 'Madurai', '', 'Mumbai, India')
    expect(s.currency).toBe('USD')
    expect(s.overridden).toBe(true)
  })

  it('is re-evaluated when the destination moves to a different country', () => {
    let s = applyManualCurrency(initialCurrencyState('Chennai, Tamil Nadu, India'), 'USD')
    s = typeInto(s, 'London, United Kingdom')
    expect(s).toMatchObject({ currency: 'GBP', overridden: false })
  })

  it('applies to an ambiguous destination and gives way once a country is identified', () => {
    let s = initialCurrencyState('Springfield')
    s = applyManualCurrency(s, 'CAD')
    expect(typeInto(s, 'Springfield, ').currency).toBe('CAD')
    s = typeInto(s, 'Springfield, Illinois')   // IL is not read as a code; the full name is a state
    expect(s).toMatchObject({ currency: 'USD', overridden: false })
  })

  it('can choose a currency the destination would never suggest', () => {
    const s = applyManualCurrency(initialCurrencyState('Berlin, Germany'), 'CHF')
    expect(s.currency).toBe('CHF')
  })

  it('ignores unsupported codes', () => {
    const s = initialCurrencyState('Berlin, Germany')
    expect(applyManualCurrency(s, 'BTC')).toBe(s)
  })
})

describe('restoring a saved plan', () => {
  it('keeps the saved currency and treats a non-matching one as the user’s choice', () => {
    const matching = restoreCurrencyState('London, United Kingdom', 'GBP')
    expect(matching).toMatchObject({ currency: 'GBP', overridden: false })
    const custom = restoreCurrencyState('London, United Kingdom', 'USD')
    expect(custom).toMatchObject({ currency: 'USD', overridden: true })
    expect(applyLocation(custom, 'London, England').currency).toBe('USD')
  })

  it('falls back to INR for an unknown saved currency', () => {
    expect(restoreCurrencyState('Somewhere', 'XXX').currency).toBe('INR')
  })
})
