import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { searchPlayers, type SearchQuery, type SearchResponse } from '../api'
import { Pitch, PlayerCardView, Skeletons } from '../components'
import { LINES, useMeta } from '../lib'

const DEFAULTS = { minAge: 16, maxAge: 40, minMinutes: 900, sort: 'rating' }
const SORT_LABEL: Record<string, string> = {
  rating: 'Rating', minutes: 'Minutes', goals: 'Goals', assists: 'Assists', age: 'Youngest',
}

function readQuery(sp: URLSearchParams): SearchQuery {
  const num = (k: string, d: number) => {
    const v = Number(sp.get(k))
    return sp.has(k) && Number.isFinite(v) ? v : d
  }
  return {
    positions: (sp.get('pos') ?? '').split(',').filter(Boolean),
    competition: sp.get('league') ?? '',
    season: sp.get('season') ?? '',
    minAge: num('minAge', DEFAULTS.minAge),
    maxAge: num('maxAge', DEFAULTS.maxAge),
    minMinutes: num('minMin', DEFAULTS.minMinutes),
    sort: sp.get('sort') ?? DEFAULTS.sort,
  }
}

function writeQuery(q: SearchQuery): URLSearchParams {
  const sp = new URLSearchParams()
  if (q.positions.length) sp.set('pos', q.positions.join(','))
  if (q.competition) sp.set('league', q.competition)
  if (q.season) sp.set('season', q.season)
  if (q.minAge !== DEFAULTS.minAge) sp.set('minAge', String(q.minAge))
  if (q.maxAge !== DEFAULTS.maxAge) sp.set('maxAge', String(q.maxAge))
  if (q.minMinutes !== DEFAULTS.minMinutes) sp.set('minMin', String(q.minMinutes))
  if (q.sort !== DEFAULTS.sort) sp.set('sort', q.sort)
  return sp
}

export default function Scout() {
  const [sp, setSp] = useSearchParams()
  const q = useMemo(() => readQuery(sp), [sp])
  const { meta, error: metaError } = useMeta()
  const [data, setData] = useState<SearchResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [retry, setRetry] = useState(0)

  const update = (patch: Partial<SearchQuery>) => setSp(writeQuery({ ...q, ...patch }), { replace: true })
  const togglePos = (code: string) =>
    update({ positions: q.positions.includes(code) ? q.positions.filter((c) => c !== code) : [...q.positions, code] })
  const setLine = (codes: string[]) => {
    const all = codes.every((c) => q.positions.includes(c))
    update({ positions: all ? q.positions.filter((c) => !codes.includes(c)) : [...new Set([...q.positions, ...codes])] })
  }

  useEffect(() => {
    const ctrl = new AbortController()
    setLoading(true)
    setError(null)
    const t = window.setTimeout(() => {
      searchPlayers(q, ctrl.signal)
        .then((r) => setData(r))
        .catch((e: Error) => { if (e.name !== 'AbortError') setError(e.message) })
        .finally(() => { if (!ctrl.signal.aborted) setLoading(false) })
    }, 180) // debounce slider drags
    return () => { ctrl.abort(); window.clearTimeout(t) }
  }, [q, retry])

  const seasonLabel = meta?.seasons.find((s) => String(s.start_year) === q.season)?.label
    ?? (data?.season ? `${data.season}/${String((data.season + 1) % 100).padStart(2, '0')}` : '')
  const leagueName = meta?.competitions.find((c) => String(c.id) === q.competition)?.name ?? 'All leagues'
  const totalPlayers = meta?.competitions.reduce((n, c) => n + c.seasons.reduce((m, s) => m + s.players, 0), 0)

  return (
    <>
      <section className="hero">
        <h1>Find your next signing</h1>
        <p>
          Pick positions on the pitch, set the filters, and compare players on season performance.
          {totalPlayers ? ` ${totalPlayers.toLocaleString('en-GB')} players across ${meta?.competitions.length} leagues.` : ''}
        </p>
      </section>

      <div className="scout">
        <aside className="sidebar">
          <section className="panel" aria-labelledby="pos-title">
            <div className="panel-title">
              <h2 id="pos-title">Positions</h2>
              {q.positions.length > 0 && <button className="link-btn" onClick={() => update({ positions: [] })}>Clear</button>}
            </div>
            <Pitch selected={q.positions} onToggle={togglePos} />
            <div className="lines">
              {Object.entries(LINES).map(([name, codes]) => (
                <button key={name} className={`chip ${codes.every((c) => q.positions.includes(c)) ? 'on' : ''}`}
                  onClick={() => setLine(codes)}>{name}</button>
              ))}
            </div>
            <p className="hint">Current data groups positions by line (GK, DEF, MID, FWD), so LB also returns other defenders.</p>
          </section>

          <section className="panel" aria-labelledby="filter-title">
            <div className="panel-title">
              <h2 id="filter-title">Filters</h2>
              <button className="link-btn" onClick={() => setSp(writeQuery({ ...readQuery(new URLSearchParams()), positions: q.positions }), { replace: true })}>Reset</button>
            </div>
            <div className="field">
              <label htmlFor="league">League</label>
              <select id="league" value={q.competition} onChange={(e) => update({ competition: e.target.value })}>
                <option value="">All leagues</option>
                {meta?.competitions.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="season">Season</label>
              <select id="season" value={q.season} onChange={(e) => update({ season: e.target.value })}>
                <option value="">Latest</option>
                {meta?.seasons.map((s) => <option key={s.start_year} value={s.start_year}>{s.label}</option>)}
              </select>
            </div>
            <div className="field">
              <span className="label">Age <span className="value">{q.minAge}–{q.maxAge}</span></span>
              <div className="range-pair">
                <input type="range" min={16} max={40} step={1} value={q.minAge} aria-label="Minimum age"
                  onChange={(e) => update({ minAge: Math.min(Number(e.target.value), q.maxAge) })} />
                <input type="range" min={16} max={40} step={1} value={q.maxAge} aria-label="Maximum age"
                  onChange={(e) => update({ maxAge: Math.max(Number(e.target.value), q.minAge) })} />
              </div>
            </div>
            <div className="field">
              <label htmlFor="mins">Minimum minutes <span className="value">{q.minMinutes.toLocaleString('en-GB')}</span></label>
              <input id="mins" type="range" min={0} max={3000} step={90} value={q.minMinutes}
                onChange={(e) => update({ minMinutes: Number(e.target.value) })} />
            </div>
          </section>
        </aside>

        <section aria-live="polite">
          <div className="results-head">
            <div>
              <h2>{data ? `${data.count}${data.count === 60 ? '+' : ''} players` : 'Players'}</h2>
              <div className="sub">{leagueName}{seasonLabel ? ` · ${seasonLabel}` : ''}</div>
            </div>
            <label className="sort">
              Sort by
              <select value={q.sort} onChange={(e) => update({ sort: e.target.value })}>
                {(meta?.sorts ?? Object.keys(SORT_LABEL)).map((s) => <option key={s} value={s}>{SORT_LABEL[s] ?? s}</option>)}
              </select>
            </label>
          </div>

          {error || metaError ? (
            <div className="empty">
              <h3>Couldn't load players</h3>
              <p className="error">{error ?? metaError}</p>
              <button className="btn" onClick={() => setRetry((n) => n + 1)}>Try again</button>
            </div>
          ) : loading && !data ? (
            <Skeletons />
          ) : data && data.players.length === 0 ? (
            <div className="empty">
              <h3>No players match</h3>
              <p>Lower the minimum minutes, widen the age range, or pick more positions.</p>
            </div>
          ) : (
            <div className="grid" style={{ opacity: loading ? 0.55 : 1, transition: 'opacity .15s' }}>
              {data?.players.map((p) => <PlayerCardView key={p.player_id} p={p} />)}
            </div>
          )}
        </section>
      </div>
    </>
  )
}
