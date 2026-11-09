import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchPlayer, type PlayerDetail } from '../api'
import { Avatar, Icon } from '../components'
import { GROUP_LABEL, fmt, ratingColor, ratingPct, useShortlist } from '../lib'

// Reference values for per-90 bars (roughly a top-10% season). Percentiles arrive in Phase 2.
const P90: { key: keyof PlayerDetail['seasons'][number]['per90']; label: string; max: number; digits: number }[] = [
  { key: 'goals', label: 'Goals', max: 0.8, digits: 2 },
  { key: 'assists', label: 'Assists', max: 0.5, digits: 2 },
  { key: 'key_passes', label: 'Key passes', max: 3, digits: 2 },
  { key: 'tackles', label: 'Tackles', max: 3.5, digits: 2 },
  { key: 'interceptions', label: 'Interceptions', max: 2, digits: 2 },
  { key: 'total_passes', label: 'Passes', max: 80, digits: 1 },
]

const FEE_LABEL: Record<string, string> = { loan: 'Loan', loan_end: 'End of loan', free: 'Free', unknown: '–' }

export default function Player() {
  const { id = '' } = useParams()
  const [player, setPlayer] = useState<PlayerDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { has, toggle } = useShortlist()

  useEffect(() => {
    const ctrl = new AbortController()
    setPlayer(null)
    setError(null)
    fetchPlayer(id, ctrl.signal)
      .then((p) => {
        setPlayer(p)
        document.title = `${p.name} · WeScout`
      })
      .catch((e: Error) => { if (e.name !== 'AbortError') setError(e.message) })
    return () => { ctrl.abort(); document.title = 'WeScout' }
  }, [id])

  if (error) {
    return (
      <div className="empty">
        <h3>Player not found</h3>
        <p className="error">{error}</p>
        <Link className="btn" to="/">Back to search</Link>
      </div>
    )
  }
  if (!player) return <div className="skeleton" style={{ height: 320 }} aria-busy="true" />

  const latest = player.seasons[0]
  const saved = has(player.player_id)
  const seasons = [...new Map(player.seasons.map((s) => [s.start_year, s])).values()]
    .sort((a, b) => a.start_year - b.start_year)

  return (
    <>
      <Link to="/" className="back"><Icon name="arrow-left" size={16} /> Back to search</Link>

      <section className="profile">
        <Avatar name={player.name} large />
        <div style={{ minWidth: 0 }}>
          <h1>{player.full_name}</h1>
          <div className="meta">
            {[latest?.club, latest?.competition, player.nationality].filter(Boolean).join(' · ')}
          </div>
          <div className="tags" style={{ marginTop: 10 }}>
            {player.position_group && <span className="tag pos">{GROUP_LABEL[player.position_group]}</span>}
            <button className={`btn ${saved ? 'primary' : ''}`} style={{ height: 28, fontSize: 13 }}
              onClick={() => toggle({
                player_id: player.player_id, player_name: player.name, club_name: latest?.club ?? null,
                competition: latest?.competition ?? null, competition_id: null, position: player.position,
                position_group: player.position_group, age: player.age, nationality: player.nationality,
                price_int: null, rating: latest?.rating ?? null, goals: latest?.goals ?? null,
                assists: latest?.assists ?? null, key_passes: latest?.key_passes ?? null,
                minutes_played: latest?.minutes ?? null, appearances: latest?.appearances ?? null,
                tackles_per_90: latest?.per90.tackles ?? null, interceptions_per_90: latest?.per90.interceptions ?? null,
                sofascore_ratings: [],
              })}>
              <Icon name="bookmark" size={14} filled={saved} /> {saved ? 'On shortlist' : 'Add to shortlist'}
            </button>
          </div>
        </div>
        <div className="big-rating">
          <b style={{ color: ratingColor(latest?.rating) }}>{fmt(latest?.rating, 2)}</b>
          <span>{latest ? `${latest.season} rating` : 'No rating'}</span>
        </div>
      </section>

      <section className="facts" aria-label="Key facts">
        <div className="fact"><span>Age</span><b>{fmt(player.age)}</b></div>
        <div className="fact"><span>Born</span><b>{player.date_of_birth ?? '–'}</b></div>
        <div className="fact"><span>Height</span><b>{player.height_cm ? `${player.height_cm} cm` : '–'}</b></div>
        <div className="fact"><span>Minutes</span><b>{fmt(latest?.minutes)}</b></div>
        <div className="fact"><span>Apps / starts</span><b>{fmt(latest?.appearances)} / {fmt(latest?.starts)}</b></div>
        <div className="fact"><span>G + A</span><b>{fmt(latest?.goals)} + {fmt(latest?.assists)}</b></div>
      </section>

      <div className="two-col">
        <section className="panel">
          <h2 className="section-title">Per 90 minutes · {latest?.season ?? ''}</h2>
          {latest ? (
            <div className="p90">
              {P90.map(({ key, label, max, digits }) => {
                const v = latest.per90[key]
                return (
                  <div className="p90-row" key={key}>
                    <span>{label}</span>
                    <div className="bar"><i style={{ width: `${Math.min(100, ((v ?? 0) / max) * 100)}%`, background: 'var(--accent)' }} /></div>
                    <b>{fmt(v, digits)}</b>
                  </div>
                )
              })}
              <p className="hint">Bars are scaled to a strong season for each stat. Percentiles against the same position and league come next.</p>
            </div>
          ) : <p className="hint">No season data yet.</p>}
        </section>

        <section className="panel">
          <h2 className="section-title">Rating by season</h2>
          <div className="season-chart" role="img"
            aria-label={seasons.map((s) => `${s.season}: ${fmt(s.rating, 2)}`).join(', ')}>
            {seasons.map((s) => (
              <div key={s.start_year} className={`season-col ${s.rating === null ? 'missing' : ''}`}>
                <div className="col" style={{ height: `${Math.max(28, ratingPct(s.rating) * 1.1)}px`, background: ratingColor(s.rating) }}>
                  {fmt(s.rating, 2)}
                </div>
                {s.season}
              </div>
            ))}
          </div>
          {player.sofascore_ratings.length > 0 && (
            <>
              <h2 className="section-title" style={{ marginTop: 22 }}>SofaScore (local only)</h2>
              <div className="tags">
                {player.sofascore_ratings.map((r) => (
                  <span className="tag" key={r.season}>{r.season}: <b style={{ color: ratingColor(r.rating) }}>{fmt(r.rating, 2)}</b></span>
                ))}
              </div>
            </>
          )}
          {seasons.length < 2 && (
            <p className="hint" style={{ marginTop: 14 }}>More seasons appear here as they're loaded.</p>
          )}
        </section>
      </div>

      <section className="panel" style={{ marginTop: 18 }}>
        <h2 className="section-title">Season stats</h2>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Season</th><th>Club</th><th>League</th>
                <th className="num">Apps</th><th className="num">Mins</th><th className="num">G</th>
                <th className="num">A</th><th className="num">KP</th><th className="num">Tkl</th>
                <th className="num">Int</th><th className="num">Rating</th>
              </tr>
            </thead>
            <tbody>
              {player.seasons.map((s, i) => (
                <tr key={i}>
                  <td>{s.season}</td><td>{s.club}</td><td>{s.competition}</td>
                  <td className="num">{fmt(s.appearances)}</td><td className="num">{fmt(s.minutes)}</td>
                  <td className="num">{fmt(s.goals)}</td><td className="num">{fmt(s.assists)}</td>
                  <td className="num">{fmt(s.key_passes)}</td><td className="num">{fmt(s.tackles)}</td>
                  <td className="num">{fmt(s.interceptions)}</td>
                  <td className="num" style={{ color: ratingColor(s.rating), fontWeight: 600 }}>{fmt(s.rating, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {player.transfers.length > 0 && (
        <section className="panel" style={{ marginTop: 18 }}>
          <h2 className="section-title">Transfers</h2>
          <div className="timeline">
            {player.transfers.map((t, i) => (
              <div key={i}>
                <span className="date">{t.date ?? '–'}</span>
                <span>{t.from_club ?? '?'} → <b>{t.to_club ?? '?'}</b></span>
                <span className="badge">
                  {t.fee_type === 'fee'
                    ? (t.fee_eur !== null ? `€${fmt(t.fee_eur / 1e6, 1)}m` : (t.fee_raw ?? 'Fee'))
                    : FEE_LABEL[t.fee_type] ?? t.fee_type}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
    </>
  )
}
