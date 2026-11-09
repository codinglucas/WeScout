import { Link } from 'react-router-dom'
import { Avatar, Icon } from '../components'
import { GROUP_LABEL, fmt, ratingColor, useShortlist } from '../lib'

export default function Shortlist() {
  const { items, remove, clear } = useShortlist()

  return (
    <>
      <section className="hero">
        <h1>Your shortlist</h1>
        <p>Players you've saved, kept in this browser. Open one to see the full profile.</p>
      </section>

      {items.length === 0 ? (
        <div className="empty">
          <h3>Start your shortlist</h3>
          <p>Use the bookmark on any player card to save it here.</p>
          <Link className="btn primary" to="/"><Icon name="search" size={16} /> Find players</Link>
        </div>
      ) : (
        <section className="panel" style={{ padding: 0 }}>
          <div className="results-head" style={{ padding: '14px 14px 0' }}>
            <h2>{items.length} saved</h2>
            <button className="link-btn" onClick={clear}>Clear all</button>
          </div>
          {items.map((p) => (
            <div className="list-row" key={p.player_id}>
              <Avatar name={p.player_name} />
              <Link to={`/player/${p.player_id}`} style={{ minWidth: 0 }}>
                <div className="name">{p.player_name}</div>
                <div className="meta">
                  {[p.club_name, p.competition, p.age !== null ? `${p.age} yrs` : null,
                    p.position_group ? GROUP_LABEL[p.position_group] : null].filter(Boolean).join(' · ')}
                </div>
              </Link>
              <div className="rating" style={{ color: ratingColor(p.rating), fontSize: 22 }}>{fmt(p.rating, 2)}</div>
              <button className="icon-btn" onClick={() => remove(p.player_id)} aria-label={`Remove ${p.player_name}`}>
                <Icon name="x" size={16} />
              </button>
            </div>
          ))}
        </section>
      )}
    </>
  )
}
