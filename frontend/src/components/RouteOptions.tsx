import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Armchair, ArrowRight, Bus, Car, Check, ChevronDown, CircleDollarSign, Clock, ExternalLink, Info, Luggage, Map as MapIcon, Plane, Ruler, Star, TrainFront, Zap } from './icons'
import { api, inr, Json, mins } from '../api'
import { MapView, Pin, Prov, Stars } from './ui'

const ICON: Record<string, typeof Plane> = { flight: Plane, train: TrainFront, bus: Bus, cab: Car }
const TONE: Record<string, string> = { flight: 'bg-sky-100 text-sky-700', train: 'bg-violet-100 text-violet-700', bus: 'bg-emerald-100 text-emerald-700', cab: 'bg-sun-50 text-amber-700' }
const PIN: Record<string, string> = { flight: '#3b9eea', train: '#7c3aed', bus: '#059669', cab: '#f6b73c' }
const BADGE: Record<string, [string, string, typeof Plane]> = {
  cheapest: ['Cheapest', 'bg-emerald-100 text-emerald-800', CircleDollarSign], fastest: ['Fastest', 'bg-sky-100 text-sky-800', Zap], most_comfortable: ['Most comfortable', 'bg-violet-100 text-violet-800', Armchair],
  best_value: ['Best value', 'bg-amber-100 text-amber-800', Star], most_convenient: ['Fewest changes', 'bg-teal-100 text-teal-800', Luggage],
}
const SORTS: [string, string][] = [['best', 'Best value'], ['cheapest', 'Cheapest'], ['fastest', 'Fastest'], ['comfort', 'Most comfortable']]
type Basis = 'one_way' | 'round_trip'
const hhmm = (s?: string) => (s ? String(s).slice(11, 16) : '')

/** The route on a map: every stop pinned in order; road legs follow real roads (Mapbox), rail and air legs are drawn straight. */
function RouteMap({ legs }: { legs: Json[] }) {
  const [lines, setLines] = useState<[number, number][][]>([])
  const ok = legs.every(l => Array.isArray(l.from_pt) && Array.isArray(l.to_pt))
  const key = legs.map(l => `${l.from_pt}|${l.to_pt}|${l.mode}`).join(';')
  useEffect(() => {
    if (!ok) return
    let dead = false
    const straight = legs.map(l => [[l.from_pt[1], l.from_pt[0]], [l.to_pt[1], l.to_pt[0]]] as [number, number][])
    setLines(straight)  // drawn at once; road legs are refined as their real geometry arrives
    legs.forEach((l, i) => {
      if (l.mode !== 'cab' && l.mode !== 'bus') return
      api('/route/directions', { body: { points: [l.from_pt, l.to_pt], profile: 'driving' } })
        .then(r => { if (!dead && r?.geometry?.length > 1) setLines(prev => prev.map((x, k) => (k === i ? r.geometry : x))) }).catch(() => { /* keep the straight line */ })
    })
    return () => { dead = true }
  }, [key])
  const pins: Pin[] = useMemo(() => !ok ? [] : [
    { lat: legs[0].from_pt[0], lon: legs[0].from_pt[1], label: `Start: ${legs[0].from}`, color: '#0b1f33', n: 'A' },
    ...legs.map((l, i) => ({ lat: l.to_pt[0], lon: l.to_pt[1], label: i === legs.length - 1 ? `Arrive: ${l.to}` : `Change at ${l.to}`, color: i === legs.length - 1 ? '#f4553f' : PIN[legs[i + 1]?.mode] ?? '#0fa596', n: i === legs.length - 1 ? 'B' : i + 1 })),
  ], [key])
  if (!ok) return null
  return (
    <div>
      <MapView pins={pins} route={lines} height={300} />
      <p className="mt-1.5 text-xs text-ink/45">A = start, B = destination, numbers = where you change. Road legs follow real roads; rail and air legs are drawn as straight lines.</p>
    </div>
  )
}

function Leg({ l, last }: { l: Json; last: boolean }) {
  const I = ICON[l.mode] ?? Car
  const cab = l.mode === 'cab'
  const fare = (l.fare_inr ?? 0) + (l.extra_charges_inr || 0)
  const links: Json[] = l.links?.length ? l.links : l.booking_link ? [{ label: 'View & book', url: l.booking_link }] : []
  return (
    <li className="relative flex gap-3 pb-4 last:pb-0">
      {!last && <span className="absolute bottom-0 left-[1.1rem] top-10 w-px bg-ink/15" aria-hidden />}
      <span className={`relative z-10 grid h-9 w-9 shrink-0 place-items-center rounded-full ${TONE[l.mode] ?? TONE.cab}`} aria-hidden><I className="h-4 w-4" /></span>
      <div className="min-w-0 flex-1 rounded-2xl bg-sand p-3 text-sm">
        <p className="font-semibold leading-snug"><span className="capitalize">{l.mode}</span>: {l.from} <ArrowRight className="mx-0.5 inline h-3.5 w-3.5 text-ink/40" aria-label="to" /> {l.to}</p>
        <p className="num mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-ink/65">
          <span className="flex items-center gap-1"><Clock className="h-3 w-3" aria-hidden />{mins(l.duration_min)}</span>
          {l.distance_km ? <span className="flex items-center gap-1"><Ruler className="h-3 w-3" aria-hidden />{l.distance_km} km</span> : null}
          <span className="font-semibold text-ink">{cab ? `${inr(fare)} for the cab` : `${l.fare_options?.length ? 'from ' : ''}${inr(fare)} per person`}</span>
          {l.depart && <span>departs {hhmm(l.depart)}</span>}{l.arrive && <span>arrives {hhmm(l.arrive)}</span>}
        </p>
        {l.fare_options?.length > 1 && <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Fare by class">{l.fare_options.map((f: Json) => <li key={f.label} className="num rounded-full bg-white px-2.5 py-1 text-xs"><span className="text-ink/55">{f.label}</span> <b>{inr(f.inr)}</b></li>)}</ul>}
        <p className="mt-1.5 text-xs text-ink/55">{[l.operator, l.stops ? `${l.stops} stop${l.stops === 1 ? '' : 's'}` : null, l.availability_note].filter(Boolean).join(' · ')}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2"><Prov p={l.provenance} />
          {links.map(k => <a key={k.url} href={k.url} target="_blank" rel="noreferrer" className="inline-flex min-h-[34px] items-center gap-1.5 rounded-full border border-ink/15 bg-white px-3 text-xs font-semibold text-ink transition hover:border-coral hover:text-coral-600">{k.label}<ExternalLink className="h-3 w-3" aria-hidden /></a>)}</div>
      </div>
    </li>
  )
}

export function OptionCard({ o, chosen, onChoose, busy, budget, basis = 'one_way' }: { o: Json; chosen?: boolean; onChoose?: () => void; busy?: boolean; budget?: number | null; basis?: Basis }) {
  const [open, setOpen] = useState(false)
  const rt = basis === 'round_trip'
  const main = rt ? o.round_trip_inr : o.total_fare_inr
  const via: string[] = o.via ?? []
  return (
    <motion.article layout="position" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className={`card !p-4 transition-shadow hover:shadow-lift sm:!p-5 ${chosen ? 'ring-2 ring-coral' : ''}`}>
      <div className="mb-2 flex flex-wrap gap-1.5">{(o.badges ?? []).map((b: string) => { const x = BADGE[b]; if (!x) return null; const I = x[2]; return <span key={b} className={`badge ${x[1]}`}><I className="h-3 w-3" aria-hidden />{x[0]}</span> })}{chosen && <span className="badge bg-coral text-white"><Check className="h-3 w-3" aria-hidden />Your choice</span>}</div>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2.5">
            <div className="flex shrink-0 items-center" aria-hidden>{o.legs.map((l: Json, i: number) => { const I = ICON[l.mode] ?? Car; return <span key={i} className={`grid h-9 w-9 place-items-center rounded-full border-2 border-white ${TONE[l.mode] ?? TONE.cab} ${i ? '-ml-2' : ''}`}><I className="h-4 w-4" /></span> })}</div>
            <h3 className="min-w-0 font-display text-lg font-bold leading-tight">{o.summary}</h3>
          </div>
          {via.length > 2 && <p className="mt-2 flex flex-wrap items-center gap-x-1 gap-y-0.5 text-xs text-ink/60" aria-label="Stops on this route">{via.map((v, i) => <span key={i} className="flex items-center gap-1">{i > 0 && <ArrowRight className="h-3 w-3 text-ink/30" aria-hidden />}<span className={i === 0 || i === via.length - 1 ? 'font-semibold text-ink/80' : ''}>{v}</span></span>)}</p>}
          <p className="num mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink/65"><span className="flex items-center gap-1 font-semibold text-ink"><Clock className="h-3.5 w-3.5" aria-hidden />{mins(o.total_duration_min)}</span>
            {o.total_distance_km ? <span>{o.total_distance_km} km</span> : null}<span>{o.transfers === 0 ? 'no changes' : `${o.transfers} change${o.transfers === 1 ? '' : 's'}`}</span><span className="flex items-center gap-1">comfort <Stars v={o.comfort} /></span></p>
        </div>
        <div className="num flex items-end justify-between gap-3 border-t border-ink/[.06] pt-3 sm:block sm:border-0 sm:pt-0 sm:text-right">
          <div><p className="font-display text-2xl font-bold leading-none">{inr(main)}</p>
            <p className="mt-1 text-xs text-ink/50">{rt ? 'round trip' : 'one way'}{o.per_person_inr && o.per_person_inr !== o.total_fare_inr ? ` · ${inr(rt ? o.per_person_inr * 2 : o.per_person_inr)} per person` : ''}</p></div>
          <p className="text-sm text-ink/60 sm:mt-1">{rt ? <>{inr(o.total_fare_inr)} <span className="text-xs">one way</span></> : <>{inr(o.round_trip_inr)} <span className="text-xs">round trip</span></>}</p>
        </div>
      </div>
      {budget != null && o.fits_budget != null && <p className={`num mt-3 flex items-center gap-2 rounded-xl px-3 py-2 text-sm ${o.fits_budget ? 'bg-emerald-50 text-emerald-800' : 'bg-amber-50 text-amber-900'}`}>{o.fits_budget
        ? <><Check className="h-4 w-4 shrink-0" aria-hidden /><span>Fits your {inr(budget)} budget, with {inr(budget - main)} left</span></>
        : <><Info className="h-4 w-4 shrink-0" aria-hidden /><span>{inr(o.over_by_inr)} over your {inr(budget)} budget ({rt ? 'round trip' : 'one way'})</span></>}</p>}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Prov p={o.provenance} />
        <button className="chip !min-h-[38px] !text-[13px]" aria-expanded={open} onClick={() => setOpen(v => !v)}><MapIcon className="h-3.5 w-3.5" aria-hidden />{open ? 'Hide' : 'Show'} route, map &amp; booking<ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden /></button>
        {onChoose && <button className="btn btn-primary btn-sm ml-auto" disabled={busy || chosen} onClick={onChoose}>{chosen ? 'Selected' : 'Choose this'}</button>}
      </div>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.25 }} className="overflow-hidden">
            <div className="mt-4 grid gap-4 border-t border-ink/10 pt-4 lg:grid-cols-2">
              <ol aria-label="Step by step">{o.legs.map((l: Json, i: number) => <Leg key={i} l={l} last={i === o.legs.length - 1} />)}</ol>
              <div className="space-y-3">
                <RouteMap legs={o.legs} />
                {(o.notes ?? []).map((n: string) => <p key={n} className="flex gap-2 rounded-xl bg-sky-50 p-2.5 text-xs text-sky-900"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />{n}</p>)}
                <p className="text-xs text-ink/45">{o.legs.some((l: Json) => l.mode === 'flight') ? 'Includes 2.5 h for airport check-in and 45 min after landing. ' : ''}Timings and fares marked “estimated” are worked out from distance: open the links to see real departures and prices before you book.</p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.article>
  )
}

/** Ranked list split into "within your budget" and "over your budget". */
export default function RouteOptions({ data, chosenIndex, onChoose, busy }: { data: Json; chosenIndex?: number | null; onChoose?: (i: number) => void; busy?: boolean }) {
  const [sort, setSort] = useState('best')
  const opts: Json[] = data.options ?? []
  const sorted = useMemo(() => {
    const k: Record<string, (o: Json) => number> = { best: o => o.index, cheapest: o => o.total_fare_inr, fastest: o => o.total_duration_min, comfort: o => -o.comfort }
    return [...opts].sort((a, b) => k[sort](a) - k[sort](b))
  }, [opts, sort])
  const budget = (data.budget_inr ?? data.allowance_round_trip_inr) as number | null | undefined
  const basis: Basis = data.budget_basis ?? (data.allowance_round_trip_inr != null ? 'round_trip' : 'one_way')
  const within = sorted.filter(o => o.fits_budget !== false)
  const over = sorted.filter(o => o.fits_budget === false)
  const stretch: Record<number, Json> = Object.fromEntries((data.stretch ?? []).map((s: Json) => [s.index, s]))
  const card = (o: Json) => <OptionCard key={o.index} o={o} budget={budget} basis={basis} chosen={chosenIndex === o.index} busy={busy} onChoose={onChoose && (() => onChoose(o.index))} />
  return (
    <div className="space-y-5">
      {(data.notes ?? []).map((n: string) => <p key={n} className="flex gap-2.5 rounded-2xl bg-sky-50 p-3 text-sm text-sky-900"><Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />{n}</p>)}
      {data.airports?.origin && data.airports?.destination && <p className="num text-xs text-ink/55">Nearest airports: {data.airports.origin.city} ({data.airports.origin.iata}, {Math.round(data.airports.origin.km)} km from the start) → {data.airports.destination.city} ({data.airports.destination.iata}, {Math.round(data.airports.destination.km)} km from the destination).</p>}
      {opts.length > 1 && <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Sort options">
        <span className="text-sm font-semibold text-ink/60">Sort</span>{SORTS.map(([k, l]) => <button key={k} aria-pressed={sort === k} onClick={() => setSort(k)} className={`chip !min-h-[36px] !py-1 ${sort === k ? 'chip-on' : ''}`}>{l}</button>)}
      </div>}
      {budget != null && <p className="num rounded-2xl bg-sand-200 px-3 py-2 text-sm text-ink/70">{data.budget_share
        ? <>Travel budget about <b>{inr(budget)}</b> round trip: that is {Math.round(data.budget_share * 100)}% of your whole trip budget, leaving the rest for the stay, food and sights.</>
        : <>Your budget: <b>{inr(budget)}</b> {basis === 'round_trip' ? 'for the round trip' : 'one way'}{data.travellers > 1 ? `, for all ${data.travellers} travellers` : ''}.</>}</p>}
      {opts.length === 0 && <p className="rounded-2xl border border-dashed border-ink/20 p-6 text-center text-sm text-ink/60">No route options could be built for this pair.</p>}
      {budget != null ? <>
        <section aria-label="Within budget"><h3 className="mb-3 font-display text-xl font-bold">Within your budget <span className="num text-sm font-normal text-ink/50">({within.length})</span></h3>
          {within.length === 0 ? <p className="rounded-2xl bg-amber-50 p-3 text-sm text-amber-900">Nothing fits that budget. The options below show how far over each one is: raise the budget, or pick the closest.</p> :
            <div className="space-y-3">{within.map(card)}</div>}</section>
        {over.length > 0 && <section aria-label="Over budget"><h3 className="mb-3 font-display text-xl font-bold">Over your budget <span className="num text-sm font-normal text-ink/50">({over.length})</span></h3>
          <div className="space-y-3">{over.map(o => <div key={o.index}>
            {stretch[o.index] && (stretch[o.index].saves_min > 0 || stretch[o.index].comfort_gain > 0.2) && <p className="num mb-1.5 text-sm font-medium text-amber-900">Worth it? +{inr(stretch[o.index].extra_round_trip_inr)}{stretch[o.index].saves_min > 0 ? ` saves about ${mins(stretch[o.index].saves_min)}` : ''}{stretch[o.index].comfort_gain > 0.2 ? `${stretch[o.index].saves_min > 0 ? ' and' : ''} is more comfortable` : ''}</p>}
            {card(o)}</div>)}</div></section>}
      </> : <div className="space-y-3">{sorted.map(card)}</div>}
    </div>
  )
}
