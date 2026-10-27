import { useState } from 'react'
import { Check, CircleAlert, LoaderCircle, Plus, Search, X } from 'lucide-react'
import { searchEntities } from '../api/client'
import type { EntityCandidate } from '../types'
import { MAX_INTERESTS, newRow, rowStatus, type InterestRow } from '../lib/interests'
import { friendlyType } from '../lib/present'

type Props = {
  rows: InterestRow[]
  onChange: (rows: InterestRow[]) => void
  idPrefix: string
}

/** Per-interest entity confirmation: type -> search Qloo -> explicitly pick the entity you
 *  mean. Every interest must be confirmed (or removed) before the form can be submitted;
 *  the server never accepts a first result or an exact-name match on the user's behalf. */
export default function InterestPicker({ rows, onChange, idPrefix }: Props) {
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const [errorById, setErrorById] = useState<Record<string, string>>({})

  function patch(id: string, changes: Partial<InterestRow>) {
    onChange(rows.map((r) => (r.id === id ? { ...r, ...changes } : r)))
  }
  function setText(id: string, text: string) {
    // Changing the text invalidates any prior search/selection for that row.
    patch(id, { text, candidates: [], selected: null, searched: false })
  }
  function addRow() {
    if (rows.length < MAX_INTERESTS) onChange([...rows, newRow()])
  }
  function removeRow(id: string) {
    onChange(rows.length > 1 ? rows.filter((r) => r.id !== id) : rows)
  }

  async function find(row: InterestRow) {
    const query = row.text.trim()
    if (query.length < 2) {
      setErrorById((e) => ({ ...e, [row.id]: 'Type at least 2 characters to search.' }))
      return
    }
    setErrorById((e) => ({ ...e, [row.id]: '' }))
    setLoadingId(row.id)
    try {
      const res = await searchEntities(query, 5)
      patch(row.id, { candidates: res.candidates, searched: true, selected: null })
    } catch (err) {
      setErrorById((e) => ({ ...e, [row.id]: err instanceof Error ? err.message : 'Search failed.' }))
    } finally {
      setLoadingId(null)
    }
  }

  function select(row: InterestRow, c: EntityCandidate) {
    patch(row.id, { selected: c, candidates: [] })
  }

  return (
    <div className="interest-picker">
      {rows.map((row, index) => {
        const status = rowStatus(row)
        const err = errorById[row.id]
        const loading = loadingId === row.id
        const label = row.text.trim() || 'this interest'
        return (
          <div className={`interest-row is-${status}`} key={row.id}>
            <div className="interest-row-top">
              <span className="interest-index" aria-hidden="true">{index + 1}</span>
              <input
                id={`${idPrefix}-interest-${index}`}
                className="input input-plain"
                aria-label={`Interest ${index + 1}`}
                value={row.text}
                maxLength={100}
                placeholder="e.g. independent film"
                onChange={(e) => setText(row.id, e.target.value)}
              />
              <button type="button" className="btn-search" onClick={() => find(row)}
                disabled={loading} aria-label={`Find matches for ${label}`}>
                {loading ? <LoaderCircle size={15} className="spinner" /> : <Search size={15} />}
                <span>{loading ? 'Searching' : 'Search'}</span>
              </button>
              {rows.length > 1 && (
                <button type="button" className="icon-button" aria-label={`Remove interest ${index + 1}`}
                  onClick={() => removeRow(row.id)}><X size={15} /></button>
              )}
            </div>

            <div className="sr-only" role="status" aria-live="polite">
              {loading ? `Searching Qloo for ${label}…` : ''}
            </div>

            {err && <p className="pick-note warn" role="alert"><CircleAlert size={13} /> {err}</p>}

            {loading && (
              <div className="cand-skeleton" aria-hidden="true">
                <span /><span /><span />
              </div>
            )}

            {status === 'confirmed' && row.selected && (
              <div className="pick-confirmed">
                <span className="confirm-tick" aria-hidden="true"><Check size={13} strokeWidth={3} /></span>
                <span className="confirm-body">
                  <span className="confirm-label">Confirmed</span>
                  <span className="confirm-name">
                    {row.selected.name}
                    {row.selected.source !== 'mock' && friendlyType(row.selected.entity_type) &&
                      <em className="type-chip">{friendlyType(row.selected.entity_type)}</em>}
                    {row.selected.source === 'mock' && <strong className="demo-tag">demo</strong>}
                  </span>
                </span>
                <button type="button" className="text-button"
                  aria-label={`Change the confirmed entity for ${label}`}
                  onClick={() => patch(row.id, { selected: null })}>
                  Change
                </button>
              </div>
            )}

            {status === 'unconfirmed' && !loading && row.searched && row.candidates.length > 0 && (
              <div className="pick-candidates" role="group" aria-label={`Qloo matches for ${label}`}>
                <p className="pick-note">Pick the one you mean — nothing is chosen for you.</p>
                {row.candidates.map((c) => {
                  const type = c.source === 'mock' ? null : friendlyType(c.entity_type)
                  return (
                    <button type="button" key={c.entity_id} className="candidate" onClick={() => select(row, c)}>
                      <span className="cand-main">
                        <span className="cand-name">{c.name}</span>
                        {type && <span className="type-chip">{type}</span>}
                        {c.source === 'mock' && <span className="demo-tag">demo</span>}
                      </span>
                      {c.disambiguation && <span className="cand-dis">{c.disambiguation}</span>}
                      {c.source === 'mock' && <span className="cand-dis">Demo entity — not a real Qloo match</span>}
                      <span className="cand-cta" aria-hidden="true">Confirm <Check size={13} strokeWidth={3} /></span>
                    </button>
                  )
                })}
                <p className="pick-note">None right? Edit the text and search again, or remove this interest.</p>
              </div>
            )}

            {status === 'unconfirmed' && !loading && row.searched && row.candidates.length === 0 && (
              <p className="pick-note warn">
                <CircleAlert size={13} /> No matches found. Edit the text and search again, or remove this interest — it can&rsquo;t be used until you confirm an entity.
              </p>
            )}

            {status === 'unconfirmed' && !loading && !row.searched && (
              <p className="pick-note warn">
                <CircleAlert size={13} /> Not confirmed yet — search and pick the entity you mean. Unconfirmed interests can&rsquo;t be used.
              </p>
            )}
          </div>
        )
      })}
      {rows.length < MAX_INTERESTS && (
        <button type="button" className="add-link" onClick={addRow}>
          <Plus size={15} /> Add an interest
        </button>
      )}
    </div>
  )
}
