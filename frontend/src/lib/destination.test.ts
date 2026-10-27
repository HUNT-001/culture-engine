import { describe, expect, it } from 'vitest'
import { currencyForCountry, detectCountry, detectCurrency } from './destination'

describe('detectCurrency — destinations the app is likely to see', () => {
  it.each([
    ['Chennai, Tamil Nadu, India', 'INR'],
    ['Austin, Texas, United States', 'USD'],
    ['New York, USA', 'USD'],
    ['London, United Kingdom', 'GBP'],
    ['Austin, Texas', 'USD'],
    ['Mumbai, Maharashtra', 'INR'],
    ['Portland, OR', 'USD'],
    ['Toronto, Ontario, Canada', 'CAD'],
    ['Perth, Western Australia', 'AUD'],
    ['Edinburgh, Scotland', 'GBP'],
    ['Berlin, Germany', 'EUR'],
    ['Dublin, Ireland', 'EUR'],
    ['Tokyo, Japan', 'JPY'],
    ['Dubai, UAE', 'AED'],
    ['Zürich, Switzerland', 'CHF'],
  ])('%s → %s', (location, currency) => {
    expect(detectCurrency(location)).toBe(currency)
  })

  it.each(['India', 'USA', 'United States', 'US', 'U.S.A.', 'UK', 'U.K.', 'United Kingdom', 'united kingdom', 'Canada'])(
    'recognises the country alone: %s', (location) => {
      expect(detectCountry(location)).not.toBeNull()
    })

  it('is case-, space- and punctuation-insensitive', () => {
    expect(detectCurrency('  chennai ,  TAMIL NADU ,  india  ')).toBe('INR')
    expect(detectCurrency('Austin,Texas,U.S.A.')).toBe('USD')
  })

  it('maps countries to ISO 4217 codes', () => {
    expect(currencyForCountry('IN')).toBe('INR')
    expect(currencyForCountry('GB')).toBe('GBP')
    expect(currencyForCountry('FR')).toBe('EUR')
    expect(currencyForCountry('ZZ')).toBeNull()
  })
})

describe('detectCurrency — no unjustified guesses', () => {
  it.each([
    '', '   ', ',', 'Chennai', 'London', 'Paris', 'Springfield', 'Downtown',
    'Georgia',            // a US state and a country
    'Tbilisi, Georgia',
    'Punjab',             // India and Pakistan
    'Victoria',           // Australia, Canada, a first name
    'Perth, WA',          // Washington or Western Australia
    'Toronto, CA',        // California or Canada
    'Mumbai, IN',         // Indiana or India
    'Berlin, DE',         // Delaware or Germany
    'Little Italy', 'Little India', 'New England', 'Mexico City', 'Indiana Jones',
  ])('returns null for %j', (location) => {
    expect(detectCountry(location)).toBeNull()
    expect(detectCurrency(location)).toBeNull()
  })

  it('does not match partial words while typing', () => {
    for (const partial of ['Chennai, Ind', 'Chennai, Indi', 'Austin, Tex', 'London, United', 'Paris, Fran']) {
      expect(detectCountry(partial)).toBeNull()
    }
  })

  it('refuses when two different countries are named', () => {
    expect(detectCountry('India, United Kingdom')).toBeNull()
    expect(detectCountry('Texas, Ontario')).toBeNull()
  })

  it('lets an explicit country outrank a state that is also a city elsewhere', () => {
    expect(detectCountry('New Brunswick, New Jersey, USA')).toBe('US')
  })

  it('only reads two-letter state codes written in capitals', () => {
    expect(detectCountry('Portland, OR')).toBe('US')
    expect(detectCountry('Portland, or')).toBeNull()
  })
})
