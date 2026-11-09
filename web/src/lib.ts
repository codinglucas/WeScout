import { useCallback, useEffect, useState, type CSSProperties } from 'react'
import { fetchMeta, type Meta, type PlayerCard } from './api'

export const GROUP_LABEL: Record<string, string> = { GK: 'GK', DF: 'DEF', MF: 'MID', FW: 'FWD' }

export function fmt(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '–'
  return value.toLocaleString('en-GB', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export function ratingColor(r: number | null | undefined): string {
  if (r === null || r === undefined) return 'var(--r-low)'
  if (r >= 7.5) return 'var(--r-excellent)'
  if (r >= 7.0) return 'var(--r-good)'
  if (r >= 6.6) return 'var(--r-ok)'
  return 'var(--r-low)'
}

/** Rating 6.0-8.5 mapped onto 0-100% for bars. */
export function ratingPct(r: number | null | undefined): number {
  if (r === null || r === undefined) return 0
  return Math.max(4, Math.min(100, ((r - 6) / 2.5) * 100))
}

export function initials(name: string): string {
  const parts = name.replace(/\./g, ' ').split(/\s+/).filter(Boolean)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

const AVATAR_HUES = [145, 160, 190, 210, 260, 20, 40, 330]
export function avatarStyle(name: string): CSSProperties {
  let h = 0
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0
  // Hue only; the theme decides lightness (see .avatar in styles.css).
  return { '--h': AVATAR_HUES[h % AVATAR_HUES.length] } as CSSProperties
}

// ---------- persisted state (per browser; failures are ignored) ----------

function readStorage<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

function writeStorage(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* private mode or storage blocked: keep working in memory */
  }
}

export type SavedPlayer = Pick<
  PlayerCard,
  'player_id' | 'player_name' | 'club_name' | 'competition' | 'position_group' | 'age' | 'rating' | 'minutes_played'
> & { saved_at: string }

const SHORTLIST_KEY = 'wescout.shortlist.v1'
const listeners = new Set<() => void>()

export function useShortlist() {
  const [items, setItems] = useState<SavedPlayer[]>(() => readStorage(SHORTLIST_KEY, []))

  useEffect(() => {
    const sync = () => setItems(readStorage(SHORTLIST_KEY, []))
    listeners.add(sync)
    window.addEventListener('storage', sync)
    return () => {
      listeners.delete(sync)
      window.removeEventListener('storage', sync)
    }
  }, [])

  const save = useCallback((next: SavedPlayer[]) => {
    writeStorage(SHORTLIST_KEY, next)
    setItems(next)
    listeners.forEach((fn) => fn())
  }, [])

  const has = useCallback((id: number) => items.some((p) => p.player_id === id), [items])

  const toggle = useCallback(
    (p: PlayerCard) => {
      const current: SavedPlayer[] = readStorage(SHORTLIST_KEY, [])
      if (current.some((x) => x.player_id === p.player_id)) {
        save(current.filter((x) => x.player_id !== p.player_id))
      } else {
        save([
          {
            player_id: p.player_id,
            player_name: p.player_name,
            club_name: p.club_name,
            competition: p.competition,
            position_group: p.position_group,
            age: p.age,
            rating: p.rating,
            minutes_played: p.minutes_played,
            saved_at: new Date().toISOString(),
          },
          ...current,
        ])
      }
    },
    [save],
  )

  const remove = useCallback(
    (id: number) => save(readStorage<SavedPlayer[]>(SHORTLIST_KEY, []).filter((x) => x.player_id !== id)),
    [save],
  )
  const clear = useCallback(() => save([]), [save])

  return { items, has, toggle, remove, clear }
}

export type Theme = 'dark' | 'light'

export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => readStorage<Theme>('wescout.theme', 'dark'))
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    writeStorage('wescout.theme', theme)
  }, [theme])
  return [theme, () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))]
}

// ---------- meta (loaded once, shared) ----------

let metaPromise: Promise<Meta> | null = null
export function useMeta(): { meta: Meta | null; error: string | null } {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    metaPromise ??= fetchMeta()
    metaPromise.then(setMeta).catch((e: Error) => {
      metaPromise = null
      setError(e.message)
    })
  }, [])
  return { meta, error }
}


// Pitch quick-select groups
export const LINES: Record<string, string[]> = {
  Attack: ['st', 'lw', 'rw', 'cam'],
  Midfield: ['cdm', 'cam'],
  Defence: ['lb', 'cb', 'rb'],
  Goalkeeper: ['gk'],
}
