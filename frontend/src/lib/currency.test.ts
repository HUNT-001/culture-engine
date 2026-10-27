import { describe, expect, it } from 'vitest'
import { buildPayload } from './plan'
import {
  budgetFields, CURRENCIES, currencyName, currencySymbol, DEFAULT_CURRENCY, formatMoney, isSupportedCurrency,
} from './currency'

describe('currency options', () => {
  it('include the required currencies with names and ISO codes', () => {
    for (const code of ['INR', 'USD', 'GBP', 'EUR', 'CAD', 'AUD']) expect(isSupportedCurrency(code)).toBe(true)
    expect(currencyName('GBP')).toBe('British pound')
    expect(CURRENCIES.every((c) => /^[A-Z]{3}$/.test(c.code) && c.name.length > 2)).toBe(true)
    expect(new Set(CURRENCIES.map((c) => c.code)).size).toBe(CURRENCIES.length)
  })

  it('every option is something Intl can format', () => {
    for (const { code } of CURRENCIES) {
      expect(() => new Intl.NumberFormat('en', { style: 'currency', currency: code })).not.toThrow()
    }
  })

  it('defaults legacy plans to INR', () => {
    expect(DEFAULT_CURRENCY).toBe('INR')
  })
})

describe('formatting', () => {
  it('shows the right symbol per currency', () => {
    expect(currencySymbol('INR', 'en-US')).toBe('₹')
    expect(currencySymbol('USD', 'en-US')).toBe('$')
    expect(currencySymbol('GBP', 'en-US')).toBe('£')
    expect(currencySymbol('EUR', 'en-US')).toBe('€')
  })

  it('formats amounts with Intl', () => {
    expect(formatMoney(800, 'INR', 'en-US')).toBe('₹800')
    expect(formatMoney(50, 'USD', 'en-US')).toBe('$50')
    expect(formatMoney(12.5, 'GBP', 'en-US')).toBe('£12.50')
  })

  it('does not throw for an unknown code', () => {
    expect(formatMoney(5, 'nope', 'en-US')).toBe('5 nope')
    expect(currencySymbol('nope')).toBe('nope')
  })
})

describe('budget request fields', () => {
  it('sends a numeric amount and the code separately', () => {
    const f = budgetFields('50', 'USD')
    expect(f).toEqual({ budget_per_person: 50, budget_currency: 'USD' })
    expect(typeof f.budget_per_person).toBe('number')
    expect(JSON.stringify(f)).not.toMatch(/[$₹£]/)
  })

  it('omits the amount when blank or not positive, keeping the existing optional behaviour', () => {
    for (const blank of ['', '   ', '0', '-3', 'abc']) {
      const f = budgetFields(blank, 'GBP')
      expect(f.budget_per_person).toBeUndefined()
      expect(f.budget_currency).toBe('GBP')
    }
  })

  it('is what the recommendation payload carries', () => {
    const people = [
      { participant_id: 'a', display_name: 'A', interestsText: 'jazz' },
      { participant_id: 'b', display_name: 'B', interestsText: 'film' },
    ]
    const payload = buildPayload('London, United Kingdom', '40', people, 'GBP')
    expect(payload.budget_per_person).toBe(40)
    expect(payload.budget_currency).toBe('GBP')
    expect(buildPayload('Chennai', '800', people).budget_currency).toBe('INR')
  })
})
