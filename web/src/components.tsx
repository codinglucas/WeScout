import type { ReactNode } from 'react'
import { Link, NavLink } from 'react-router-dom'
import type { PlayerCard } from './api'
import { GROUP_LABEL, avatarStyle, fmt, initials, ratingColor, ratingPct, useMeta, useShortlist, useTheme } from './lib'

// ---------- icons (inline, stroke-based) ----------

type IconName = 'bookmark' | 'sun' | 'moon' | 'arrow-left' | 'x' | 'search'
const PATHS: Record<IconName, string> = {
  bookmark: 'M6 4h12v16l-6-4-6 4z',
  sun: 'M12 4V2m0 20v-2m8-8h2M2 12h2m13.66-5.66 1.41-1.41M4.93 19.07l1.41-1.41m0-11.32L4.93 4.93m14.14 14.14-1.41-1.41M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z',
  moon: 'M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z',
  'arrow-left': 'M19 12H5m6-6-6 6 6 6',
  x: 'M6 6l12 12M18 6 6 18',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zm9 16-4.35-4.35',
}

export function Icon({ name, size = 18, filled = false }: { name: IconName; size?: number; filled?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" fill={filled ? 'currentColor' : 'none'}
      stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <path d={PATHS[name]} />
    </svg>
  )
}

export function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="var(--accent-soft)" />
      <circle cx="16" cy="16" r="9" fill="none" stroke="var(--accent)" strokeWidth="2.5" />
      <circle cx="16" cy="16" r="2.5" fill="var(--accent)" />
    </svg>
  )
}

// ---------- layout ----------

export function Layout({ children }: { children: ReactNode }) {
  const [theme, toggleTheme] = useTheme()
  const { items } = useShortlist()
  const { meta } = useMeta()
  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="brand" aria-label="WeScout home">
            <BrandMark /> WESCOUT
          </Link>
          <nav className="nav" aria-label="Main">
            <NavLink to="/" end>Scout</NavLink>
            <NavLink to="/shortlist">
              Shortlist{items.length > 0 && <span className="count">{items.length}</span>}
            </NavLink>
          </nav>
          {meta && (
            <span className={`mode-badge ${meta.public_mode ? '' : 'local'}`}
              title={meta.public_mode ? 'Licensed data only' : 'Includes local-only data'}>
              {meta.public_mode ? 'Licensed data' : 'Local mode'}
            </span>
          )}
          <button className="icon-btn" onClick={toggleTheme}
            aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}>
            <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
          </button>
        </div>
      </header>
      <main className="page">{children}</main>
      <footer className="footer">
        <div className="footer-inner">
          <span>{meta?.attribution.join(' · ') || 'WeScout'}</span>
          <span>Personal, non-commercial project · not affiliated with any data provider</span>
        </div>
      </footer>
    </div>
  )
}

// ---------- pitch (4-2-3-1, multi-select) ----------

const SPOTS: { code: string; x: number; y: number; label: string }[] = [
  { code: 'st', x: 150, y: 58, label: 'ST' },
  { code: 'lw', x: 52, y: 128, label: 'LW' },
  { code: 'cam', x: 150, y: 148, label: 'CAM' },
  { code: 'rw', x: 248, y: 128, label: 'RW' },
  { code: 'cdm', x: 104, y: 222, label: 'CDM' },
  { code: 'cdm', x: 196, y: 222, label: 'CDM' },
  { code: 'lb', x: 40, y: 300, label: 'LB' },
  { code: 'cb', x: 112, y: 318, label: 'CB' },
  { code: 'cb', x: 188, y: 318, label: 'CB' },
  { code: 'rb', x: 260, y: 300, label: 'RB' },
  { code: 'gk', x: 150, y: 384, label: 'GK' },
]


export function Pitch({ selected, onToggle }: { selected: string[]; onToggle: (code: string) => void }) {
  return (
    <div className="pitch">
      <svg viewBox="0 0 300 420" role="group" aria-label="Pick positions on a 4-2-3-1 pitch">
        <rect width="300" height="420" rx="12" fill="var(--pitch)" />
        {[0, 1, 2, 3, 4, 5, 6].map((i) => (
          <rect key={i} y={i * 60} width="300" height="30" fill="rgba(255,255,255,0.025)" />
        ))}
        <g fill="none" stroke="var(--pitch-line)" strokeWidth="1.5">
          <rect x="10" y="10" width="280" height="400" rx="2" />
          <line x1="10" y1="210" x2="290" y2="210" />
          <circle cx="150" cy="210" r="38" />
          <rect x="80" y="10" width="140" height="58" />
          <rect x="115" y="10" width="70" height="22" />
          <rect x="80" y="352" width="140" height="58" />
          <rect x="115" y="388" width="70" height="22" />
        </g>
        {SPOTS.map((s, i) => {
          const on = selected.includes(s.code)
          return (
            <g key={i} className={`spot ${on ? 'on' : ''}`} role="checkbox" aria-checked={on} tabIndex={0}
              aria-label={s.label} onClick={() => onToggle(s.code)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onToggle(s.code)
                }
              }}>
              <circle cx={s.x} cy={s.y} r={on ? 21 : 19} />
              <text x={s.x} y={s.y + 4} textAnchor="middle">{s.label}</text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

// ---------- player card ----------

export function Avatar({ name, large = false }: { name: string; large?: boolean }) {
  return (
    <div className={`avatar ${large ? 'lg' : ''}`} style={avatarStyle(name)} aria-hidden="true">
      {initials(name)}
    </div>
  )
}

export function RatingBar({ rating }: { rating: number | null }) {
  return (
    <div className="bar" role="img" aria-label={`Rating ${fmt(rating, 2)} out of 10`}>
      <i style={{ width: `${ratingPct(rating)}%`, background: ratingColor(rating) }} />
    </div>
  )
}

export function PlayerCardView({ p }: { p: PlayerCard }) {
  const { has, toggle } = useShortlist()
  const saved = has(p.player_id)
  return (
    <article className="card">
      <Link to={`/player/${p.player_id}`} className="card-link" aria-label={`Open ${p.player_name}`} />
      <button className={`save ${saved ? 'on' : ''}`} onClick={() => toggle(p)}
        aria-pressed={saved} aria-label={saved ? `Remove ${p.player_name} from shortlist` : `Add ${p.player_name} to shortlist`}>
        <Icon name="bookmark" size={16} filled={saved} />
      </button>
      <div className="card-top">
        <Avatar name={p.player_name} />
        <div style={{ minWidth: 0 }}>
          <div className="name">{p.player_name}</div>
          <div className="meta">{p.club_name ?? 'Unknown club'}</div>
        </div>
        <div className="rating" style={{ color: ratingColor(p.rating), marginRight: 30 }}>
          {fmt(p.rating, 2)}
          <small>rating</small>
        </div>
      </div>
      <RatingBar rating={p.rating} />
      <div className="tags">
        {p.position_group && <span className="tag pos">{GROUP_LABEL[p.position_group]}</span>}
        {p.age !== null && <span className="tag">{p.age} yrs</span>}
        {p.nationality && <span className="tag">{p.nationality}</span>}
        {p.competition && <span className="tag">{p.competition}</span>}
      </div>
      <div className="stats">
        <div className="stat"><b>{fmt(p.minutes_played)}</b><span>Mins</span></div>
        <div className="stat"><b>{fmt(p.goals)}</b><span>Goals</span></div>
        <div className="stat"><b>{fmt(p.assists)}</b><span>Assists</span></div>
        <div className="stat"><b>{fmt(p.tackles_per_90, 1)}</b><span>Tkl/90</span></div>
      </div>
      {p.sofascore_ratings.length > 0 && (
        <div className="tags" aria-label="SofaScore ratings, local data">
          {p.sofascore_ratings.map((r) => (
            <span key={r.season} className="tag" title="SofaScore (local only)">
              SofaScore {r.season}: <b style={{ color: ratingColor(r.rating) }}>{fmt(r.rating, 2)}</b>
            </span>
          ))}
        </div>
      )}
    </article>
  )
}

export function Skeletons({ n = 6 }: { n?: number }) {
  return (
    <div className="grid" aria-busy="true" aria-label="Loading players">
      {Array.from({ length: n }, (_, i) => <div key={i} className="skeleton" />)}
    </div>
  )
}
