// Typed client for the WeScout FastAPI backend (same origin in production, proxied in dev).

export type PositionGroup = 'GK' | 'DF' | 'MF' | 'FW'

export interface SeasonRating {
  season: string
  rating: number
  minutes: number | null
  clubs: string[]
}

export interface PlayerCard {
  player_id: number
  player_name: string
  club_name: string | null
  competition: string | null
  competition_id: number | null
  position: string | null
  position_group: PositionGroup | null
  age: number | null
  nationality: string | null
  price_int: number | null
  rating: number | null
  goals: number | null
  assists: number | null
  key_passes: number | null
  minutes_played: number | null
  appearances: number | null
  tackles_per_90: number | null
  interceptions_per_90: number | null
  sofascore_ratings: SeasonRating[]
}

export interface SearchResponse {
  success: boolean
  count: number
  players: PlayerCard[]
  season: number | null
  public_mode: boolean
  attribution: string[]
}

export interface Meta {
  public_mode: boolean
  positions: { id: number; code: string; name: string }[]
  sorts: string[]
  attribution: string[]
  seasons: { start_year: number; label: string }[]
  competitions: {
    id: number
    name: string
    country: string | null
    seasons: { season: number; players: number; clubs: number }[]
  }[]
}

export interface PlayerSeason {
  season: string
  start_year: number
  competition: string
  club: string
  position_group: PositionGroup | null
  appearances: number | null
  starts: number | null
  minutes: number | null
  rating: number | null
  goals: number | null
  assists: number | null
  key_passes: number | null
  tackles: number | null
  interceptions: number | null
  per90: Record<'goals' | 'assists' | 'key_passes' | 'tackles' | 'interceptions' | 'total_passes', number | null>
}

export interface PlayerDetail {
  player_id: number
  name: string
  full_name: string
  date_of_birth: string | null
  age: number | null
  nationality: string | null
  height_cm: number | null
  weight_kg: number | null
  position_group: PositionGroup | null
  position: string | null
  seasons: PlayerSeason[]
  transfers: {
    date: string | null
    from_club: string | null
    to_club: string | null
    fee_eur: number | null
    fee_type: string
    fee_raw: string | null
  }[]
  sofascore_ratings: SeasonRating[]
}

export interface SearchQuery {
  positions: string[]
  competition: string
  season: string
  minAge: number
  maxAge: number
  minMinutes: number
  sort: string
}

async function get<T>(url: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(url, { signal, headers: { Accept: 'application/json' } })
  const body = await res.json().catch(() => null)
  if (!res.ok || !body?.success) {
    throw new Error(body?.error ?? `Request failed (${res.status})`)
  }
  return body as T
}

export function fetchMeta(signal?: AbortSignal): Promise<Meta> {
  return get<Meta>('/api/meta', signal)
}

export function searchPlayers(q: SearchQuery, signal?: AbortSignal): Promise<SearchResponse> {
  const p = new URLSearchParams({
    min_age: String(q.minAge),
    max_age: String(q.maxAge),
    min_minutes: String(q.minMinutes),
    sort: q.sort,
    limit: '60',
  })
  if (q.positions.length) p.set('positions', q.positions.join(','))
  if (q.competition) p.set('competition', q.competition)
  if (q.season) p.set('season', q.season)
  return get<SearchResponse>(`/api/players/search?${p}`, signal)
}

export async function fetchPlayer(id: string, signal?: AbortSignal): Promise<PlayerDetail> {
  const body = await get<{ player: PlayerDetail }>(`/api/players/${encodeURIComponent(id)}`, signal)
  return body.player
}
