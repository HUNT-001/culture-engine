// Budget currency: ISO 4217 codes, formatting, and the amount/currency pair sent to the API.
// The budget is an amount in the stated currency — there is no conversion anywhere in the app.

export type CurrencyOption = { code: string; name: string }

// Kept in step with backend/app/domain/currency.py (the API rejects anything else).
export const CURRENCIES: readonly CurrencyOption[] = [
  { code: 'INR', name: 'Indian rupee' },
  { code: 'USD', name: 'US dollar' },
  { code: 'GBP', name: 'British pound' },
  { code: 'EUR', name: 'Euro' },
  { code: 'CAD', name: 'Canadian dollar' },
  { code: 'AUD', name: 'Australian dollar' },
  { code: 'NZD', name: 'New Zealand dollar' },
  { code: 'JPY', name: 'Japanese yen' },
  { code: 'CNY', name: 'Chinese yuan' },
  { code: 'SGD', name: 'Singapore dollar' },
  { code: 'HKD', name: 'Hong Kong dollar' },
  { code: 'AED', name: 'UAE dirham' },
  { code: 'CHF', name: 'Swiss franc' },
  { code: 'KRW', name: 'South Korean won' },
  { code: 'MXN', name: 'Mexican peso' },
  { code: 'BRL', name: 'Brazilian real' },
  { code: 'ZAR', name: 'South African rand' },
]

/** What plans without a stored currency mean: the app was INR-only before currencies existed. */
export const DEFAULT_CURRENCY = 'INR'

export function isSupportedCurrency(code: string): boolean {
  return CURRENCIES.some((c) => c.code === code)
}

export function currencyName(code: string): string {
  return CURRENCIES.find((c) => c.code === code)?.name ?? code
}

/** The symbol for the field's prefix ("₹", "$", "£"). Falls back to the code itself. */
export function currencySymbol(code: string, locale?: string): string {
  try {
    const parts = new Intl.NumberFormat(locale, {
      style: 'currency', currency: code, currencyDisplay: 'narrowSymbol',
    }).formatToParts(0)
    return parts.find((p) => p.type === 'currency')?.value ?? code
  } catch {
    return code
  }
}

/** Locale-aware money text, e.g. formatMoney(800, 'INR', 'en-IN') → "₹800". */
export function formatMoney(amount: number, code: string, locale?: string): string {
  try {
    // Whole amounts read as "₹800"; fractional ones use the currency's own digits ("£12.50").
    const whole = Number.isInteger(amount) ? { minimumFractionDigits: 0, maximumFractionDigits: 0 } : {}
    return new Intl.NumberFormat(locale, { style: 'currency', currency: code, ...whole }).format(amount)
  } catch {
    return `${amount} ${code}`
  }
}

/** The budget as the API wants it: a plain number, and the currency code beside it — never a
 *  symbol inside the number. A blank/invalid amount sends no budget. */
export function budgetFields(
  budget: string, currency: string,
): { budget_per_person?: number; budget_currency: string } {
  const value = Number(budget)
  const fields: { budget_per_person?: number; budget_currency: string } = { budget_currency: currency }
  if (budget.trim() && Number.isFinite(value) && value > 0) fields.budget_per_person = value
  return fields
}
