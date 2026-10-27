// Which currency the budget field uses: it follows the destination until the user picks one.
//
//  * The suggestion only changes when a country is identified AND it differs from the last one
//    identified. Partial typing, clearing, or an unrecognisable edit (country = null) never
//    changes anything, so the field doesn't flicker while someone types.
//  * A manual choice sticks while the destination stays in the same country. If the destination
//    moves to a different identified country, the choice is re-evaluated: the new country's
//    currency is suggested and the override is cleared.
import { useCallback, useState } from 'react'
import { DEFAULT_CURRENCY, isSupportedCurrency } from './currency'
import { currencyForCountry, detectCountry } from './destination'

export type CurrencyState = {
  currency: string
  /** Last country identified from the destination (null until one is). */
  country: string | null
  /** True once the user picked a currency themselves for this destination. */
  overridden: boolean
}

function suggestionFor(country: string | null): string | null {
  return country ? currencyForCountry(country) : null
}

/** State for a form that opens with `location`. The fallback is kept if no country is identified. */
export function initialCurrencyState(location: string, fallback: string = DEFAULT_CURRENCY): CurrencyState {
  const country = detectCountry(location)
  return { currency: suggestionFor(country) ?? fallback, country, overridden: false }
}

/** The destination text changed. */
export function applyLocation(state: CurrencyState, location: string): CurrencyState {
  const country = detectCountry(location)
  if (country === null || country === state.country) return state
  const suggested = suggestionFor(country)
  if (suggested === null) return state
  return { currency: suggested, country, overridden: false }
}

/** The user picked a currency from the selector. */
export function applyManualCurrency(state: CurrencyState, currency: string): CurrencyState {
  if (!isSupportedCurrency(currency) || currency === state.currency) return state
  return { ...state, currency, overridden: true }
}

/** A saved plan is reopened with its own location and currency. A currency that differs from
 *  what the destination suggests is treated as the user's own choice, so it isn't replaced. */
export function restoreCurrencyState(location: string, currency: string): CurrencyState {
  const country = detectCountry(location)
  const suggested = suggestionFor(country)
  const safe = isSupportedCurrency(currency) ? currency : DEFAULT_CURRENCY
  return { currency: safe, country, overridden: suggested !== null && suggested !== safe }
}

export function useBudgetCurrency(initialLocation: string) {
  const [state, setState] = useState(() => initialCurrencyState(initialLocation))
  const onLocationChange = useCallback((location: string) => setState((s) => applyLocation(s, location)), [])
  const setCurrency = useCallback((code: string) => setState((s) => applyManualCurrency(s, code)), [])
  const restore = useCallback(
    (location: string, currency: string) => setState(restoreCurrencyState(location, currency)), [])
  return { currency: state.currency, overridden: state.overridden, onLocationChange, setCurrency, restore }
}
