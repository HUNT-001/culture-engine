import { useState } from 'react'
import { Check, LoaderCircle, Plus, Search, X } from 'lucide-react'
import { searchEntities } from '../api/client'
import type { EntityCandidate } from '../types'
import { MAX_INTERESTS, newRow, rowStatus, type InterestRow } from '../lib/interests'

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
        return (
          <div className="interest-row" key={row.id}>
            <div className="interest-row-top">
              <input
                id={`${idPrefix}-interest-${index}`}
                className="plain-input"
                value={row.text}
                maxLength={100}
                placeholder="e.g. independent film"
                onChange={(e) => setText(row.id, e.target.value)}
              />
              <button type="button" className="mini-button" onClick={() => find(row)}
                disabled={loadingId === row.id} aria-label="Find matches">
                {loadingId === row.id ? <LoaderCircle size={14} className="spinner" /> : <Search size={14} />}
              </button>
              {rows.length > 1 && (
                <button type="button" className="icon-button" aria-label="Remove interest"
                  onClick={() => removeRow(row.id)}><X size={14} /></button>
              )}
            </div>

            {err && <p className="pick-note warn">{err}</p>}

            {status === 'confirmed' && row.selected && (
              <div className="pick-confirmed">
                <Check size={13} />
                <span>
                  {row.selected.name}
                  {row.selected.entity_type && row.selected.entity_type !== 'unknown' &&
                    <em> · {row.selected.entity_type.replace('urn:entity:', '').replace('urn:tag:', 'tag:')}</em>}
                  {row.selected.source === 'mock' && <strong className="demo-tag"> demo</strong>}
                </span>
                <button type="button" className="text-button" onClick={() => patch(row.id, { selected: null })}>
                  Change
                </button>
              </div>
            )}

            {status === 'unconfirmed' && row.searched && row.candidates.length > 0 && (
              <div className="pick-candidates">
                <p className="pick-note">Pick the one you mean:</p>
                {row.candidates.map((c) => (
                  <button type="button" key={c.entity_id} className="candidate" onClick={() => select(row, c)}>
                    <span className="cand-name">{c.name}</span>
                    {c.disambiguation && <span className="cand-dis">{c.disambiguation}</span>}
                    <span className="cand-type">
                      {c.source === 'mock' ? 'demo entity (not a real Qloo match)' : c.entity_type}
                    </span>
                  </button>
                ))}
                <p className="pick-note">None right? Edit the text and search again, or remove this interest.</p>
              </div>
            )}

            {status === 'unconfirmed' && row.searched && row.candidates.length === 0 && (
              <p className="pick-note warn">No matches found. Edit the text and search again, or remove this interest — it can&rsquo;t be used until you confirm an entity.</p>
            )}

            {status === 'unconfirmed' && !row.searched && (
              <p className="pick-note warn">Not confirmed yet — search and pick the entity you mean. Unconfirmed interests can&rsquo;t be used.</p>
            )}
          </div>
        )
      })}
      {rows.length < MAX_INTERESTS && (
        <button type="button" className="add-person" onClick={addRow}>
          <Plus size={15} /> Add an interest
        </button>
      )}
    </div>
  )
}
