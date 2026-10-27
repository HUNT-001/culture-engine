// Deterministic destination → country → currency detection. No geocoding, no network.
//
// Rules (conservative on purpose — a wrong guess is worse than no guess):
//  * The location is split on commas/semicolons/pipes/spaced dashes and each segment must match a
//    name or alias exactly. Nothing is matched inside a segment, so "Little Italy" is not Italy.
//  * An explicit country segment wins ("Chennai, Tamil Nadu, India"). Otherwise a state/province
//    segment decides ("Austin, Texas"). Evidence for two different countries means no answer.
//  * Names that can mean more than one place are left out (Georgia, Victoria, Punjab, …), and so
//    are two-letter state codes that are also another place's code (CA, IN, DE, WA, …).
// Anything unrecognised returns null so the caller keeps the user's current choice.

type Country = {
  code: string        // ISO 3166-1 alpha-2
  currency: string    // ISO 4217
  names: string[]     // country names and aliases
  regions?: string[]  // states / provinces / nations that identify only this country
}

const US_STATES = [
  'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado', 'connecticut', 'delaware', 'florida',
  'hawaii', 'idaho', 'illinois', 'indiana', 'iowa', 'kansas', 'kentucky', 'louisiana', 'maine', 'maryland',
  'massachusetts', 'michigan', 'minnesota', 'mississippi', 'missouri', 'montana', 'nebraska', 'nevada',
  'new hampshire', 'new jersey', 'new mexico', 'new york', 'north carolina', 'north dakota', 'ohio',
  'oklahoma', 'oregon', 'pennsylvania', 'rhode island', 'south carolina', 'south dakota', 'tennessee',
  'texas', 'utah', 'vermont', 'virginia', 'washington', 'west virginia', 'wisconsin', 'wyoming',
  'district of columbia',
]

// Only abbreviations that mean nothing else, and only when typed in capitals ("Portland, OR").
// Left out: CA, IN, DE, IL, CO, AR, AL, AZ, GA, ID, LA, MA, MD, ME, MN, MO, MS, MT, NC, NE, PA, SC,
// SD, TN, VA, KY (also country codes) and WA (also Western Australia).
const US_STATE_CODES = new Set([
  'AK', 'CT', 'FL', 'HI', 'IA', 'KS', 'MI', 'NH', 'NJ', 'NM', 'NV', 'NY', 'OH', 'OK', 'OR', 'RI', 'TX',
  'UT', 'VT', 'WI', 'WV', 'WY', 'DC', 'ND',
])

const COUNTRIES: Country[] = [
  { code: 'IN', currency: 'INR', names: ['india', 'republic of india', 'bharat'], regions: [
    'andhra pradesh', 'arunachal pradesh', 'assam', 'bihar', 'chhattisgarh', 'goa', 'gujarat', 'haryana',
    'himachal pradesh', 'jharkhand', 'karnataka', 'kerala', 'madhya pradesh', 'maharashtra', 'manipur',
    'meghalaya', 'mizoram', 'nagaland', 'odisha', 'orissa', 'rajasthan', 'sikkim', 'tamil nadu', 'telangana',
    'tripura', 'uttar pradesh', 'uttarakhand', 'west bengal', 'delhi', 'new delhi', 'jammu and kashmir',
    'ladakh', 'puducherry', 'pondicherry', 'chandigarh'] },
  { code: 'US', currency: 'USD', names: [
    'united states', 'united states of america', 'usa', 'us', 'u s', 'u s a', 'america'], regions: US_STATES },
  { code: 'GB', currency: 'GBP', names: [
    'united kingdom', 'uk', 'u k', 'great britain', 'britain', 'gb', 'england', 'scotland', 'wales',
    'northern ireland'] },
  { code: 'CA', currency: 'CAD', names: ['canada'], regions: [
    'ontario', 'quebec', 'british columbia', 'alberta', 'manitoba', 'saskatchewan', 'nova scotia',
    'new brunswick', 'newfoundland and labrador', 'prince edward island', 'yukon'] },
  { code: 'AU', currency: 'AUD', names: ['australia'], regions: [
    'new south wales', 'queensland', 'tasmania', 'western australia', 'south australia',
    'australian capital territory'] },
  { code: 'NZ', currency: 'NZD', names: ['new zealand', 'aotearoa'] },
  { code: 'JP', currency: 'JPY', names: ['japan'] },
  { code: 'CN', currency: 'CNY', names: ['china', 'peoples republic of china', 'prc'] },
  { code: 'SG', currency: 'SGD', names: ['singapore'] },
  { code: 'HK', currency: 'HKD', names: ['hong kong'] },
  { code: 'AE', currency: 'AED', names: ['united arab emirates', 'uae', 'u a e'] },
  { code: 'CH', currency: 'CHF', names: ['switzerland'] },
  { code: 'KR', currency: 'KRW', names: ['south korea', 'republic of korea', 'korea'] },
  { code: 'MX', currency: 'MXN', names: ['mexico', 'united mexican states'] },
  { code: 'BR', currency: 'BRL', names: ['brazil', 'brasil'] },
  { code: 'ZA', currency: 'ZAR', names: ['south africa'] },
  // Euro-area countries.
  { code: 'DE', currency: 'EUR', names: ['germany', 'deutschland'] },
  { code: 'FR', currency: 'EUR', names: ['france'] },
  { code: 'IT', currency: 'EUR', names: ['italy', 'italia'] },
  { code: 'ES', currency: 'EUR', names: ['spain', 'espana'] },
  { code: 'NL', currency: 'EUR', names: ['netherlands', 'the netherlands', 'holland'] },
  { code: 'IE', currency: 'EUR', names: ['ireland', 'republic of ireland'] },
  { code: 'PT', currency: 'EUR', names: ['portugal'] },
  { code: 'BE', currency: 'EUR', names: ['belgium'] },
  { code: 'AT', currency: 'EUR', names: ['austria'] },
  { code: 'FI', currency: 'EUR', names: ['finland'] },
  { code: 'GR', currency: 'EUR', names: ['greece'] },
  { code: 'LU', currency: 'EUR', names: ['luxembourg'] },
]

// "Georgia" (US state / country), "Punjab" (India / Pakistan), "Victoria" (Australia / Canada /
// a first name) etc. are deliberately absent from every table above, so they match nothing.

const BY_COUNTRY_NAME = new Map<string, Country>()
const BY_REGION = new Map<string, Country>()
for (const country of COUNTRIES) {
  for (const name of country.names) BY_COUNTRY_NAME.set(name, country)
  for (const region of country.regions ?? []) BY_REGION.set(region, country)
}
function normalize(segment: string): string {
  return segment
    .normalize('NFKD').replace(/[\u0300-\u036f]/g, '') // strip accents
    .toLowerCase()
    .replace(/['’]/g, '')                              // "People's" → "peoples"
    .replace(/[^a-z]+/g, ' ')                          // "U.S.A." → "u s a"
    .trim()
}

function segmentsOf(location: string): string[] {
  return location.split(/[,;|]|\s[-–—]\s/).map((s) => s.trim()).filter(Boolean)
}

/** The single country the evidence points to, null for none, or 'conflict' for several. */
function unique(found: Array<Country | undefined>): Country | null | 'conflict' {
  const set = new Set(found.filter((c): c is Country => c !== undefined))
  if (set.size === 0) return null
  return set.size === 1 ? [...set][0] : 'conflict'
}

/** ISO 3166-1 alpha-2 code of the destination country, or null when it can't be told confidently. */
export function detectCountry(location: string): string | null {
  const raw = segmentsOf(location)
  const names = raw.map(normalize).filter(Boolean)
  if (names.length === 0) return null

  const byName = unique(names.map((n) => BY_COUNTRY_NAME.get(n)))
  if (byName === 'conflict') return null
  if (byName) return byName.code

  const usCode = COUNTRIES.find((c) => c.code === 'US')
  const byRegion = unique([
    ...names.map((n) => BY_REGION.get(n)),
    ...raw.filter((r) => US_STATE_CODES.has(r)).map(() => usCode),
  ])
  return byRegion && byRegion !== 'conflict' ? byRegion.code : null
}

/** ISO 4217 code of the currency used in a country, or null if the country isn't known. */
export function currencyForCountry(countryCode: string): string | null {
  return COUNTRIES.find((c) => c.code === countryCode)?.currency ?? null
}

/** Suggested budget currency for a destination, or null when the country can't be identified. */
export function detectCurrency(location: string): string | null {
  const country = detectCountry(location)
  return country ? currencyForCountry(country) : null
}
