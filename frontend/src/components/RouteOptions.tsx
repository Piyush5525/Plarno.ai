import { useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Armchair, Bus, Car, Check, ChevronDown, CircleDollarSign, ExternalLink, Info, Luggage, Plane, Star, TrainFront, Zap } from './icons'
import { inr, Json, mins } from '../api'
import { Prov, Stars } from './ui'

const ICON: Record<string, typeof Plane> = { flight: Plane, train: TrainFront, bus: Bus, cab: Car }
const BADGE: Record<string, [string, string, typeof Plane]> = {
  cheapest: ['Cheapest', 'bg-emerald-100 text-emerald-800', CircleDollarSign], fastest: ['Fastest', 'bg-sky-100 text-sky-800', Zap], most_comfortable: ['Most comfortable', 'bg-violet-100 text-violet-800', Armchair],
  best_value: ['Best value', 'bg-amber-100 text-amber-800', Star], most_convenient: ['Most convenient', 'bg-teal-100 text-teal-800', Luggage],
}
const SORTS: [string, string][] = [['best', 'Best value'], ['cheapest', 'Cheapest'], ['fastest', 'Fastest'], ['comfort', 'Most comfortable']]

export function OptionCard({ o, chosen, onChoose, busy, allowance }: { o: Json; chosen?: boolean; onChoose?: () => void; busy?: boolean; allowance?: number | null }) {
  const [open, setOpen] = useState(false)
  return (
    <motion.article layout="position" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className={`card !p-4 transition-shadow hover:shadow-lift sm:!p-5 ${chosen ? 'ring-2 ring-coral' : ''}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap gap-1.5">{(o.badges ?? []).map((b: string) => { const x = BADGE[b]; if (!x) return null; const I = x[2]; return <span key={b} className={`badge ${x[1]}`}><I className="h-3 w-3" aria-hidden />{x[0]}</span> })}{chosen && <span className="badge bg-coral text-white"><Check className="h-3 w-3" aria-hidden />Your choice</span>}</div>
          <div className="flex items-center gap-2.5">
            <div className="flex shrink-0 items-center" aria-hidden>{o.legs.map((l: Json, i: number) => { const I = ICON[l.mode] ?? Car; return <span key={i} className={`grid h-9 w-9 place-items-center rounded-full border-2 border-white ${l.mode === 'flight' ? 'bg-sky-100 text-sky-700' : l.mode === 'train' ? 'bg-violet-100 text-violet-700' : l.mode === 'bus' ? 'bg-emerald-100 text-emerald-700' : 'bg-sun-50 text-amber-700'} ${i ? '-ml-2' : ''}`}><I className="h-4 w-4" /></span> })}</div>
            <h3 className="min-w-0 font-display text-lg font-bold leading-tight">{o.summary}</h3>
          </div>
          <p className="num mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-ink/60"><span>{mins(o.total_duration_min)} door to door</span><span aria-hidden>·</span><span>{o.transfers} change{o.transfers === 1 ? '' : 's'}</span><span aria-hidden>·</span><span className="flex items-center gap-1">comfort <Stars v={o.comfort} /></span></p>
        </div>
        <div className="num text-right">
          <p className="font-display text-2xl font-bold leading-none">{inr(o.total_fare_inr)}</p>
          <p className="mt-1 text-xs text-ink/50">one way · {inr(o.per_person_inr)} per person</p>
          <p className="mt-1 text-sm font-semibold">{inr(o.round_trip_inr)} <span className="text-xs font-normal text-ink/50">round trip</span></p>
        </div>
      </div>
      {allowance != null && <p className={`mt-3 flex items-center gap-2 rounded-xl px-3 py-2 text-sm ${o.fits_budget ? 'bg-emerald-50 text-emerald-800' : 'bg-amber-50 text-amber-900'}`}>{o.fits_budget ? <><Check className="h-4 w-4 shrink-0" aria-hidden />Fits your travel budget</> : <><Info className="h-4 w-4 shrink-0" aria-hidden />Over your travel budget by {inr(o.over_by_inr)} (round trip)</>}</p>}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Prov p={o.provenance} />
        <button className="chip !min-h-[34px] !py-1 !text-xs" aria-expanded={open} onClick={() => setOpen(v => !v)}>{open ? 'Hide' : 'Show'} step by step<ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden /></button>
        {onChoose && <button className="btn btn-primary btn-sm ml-auto" disabled={busy || chosen} onClick={onChoose}>{chosen ? 'Selected' : 'Choose this'}</button>}
      </div>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.25 }} className="overflow-hidden">
            <ol className="relative mt-3 space-y-2 border-t border-ink/10 pt-3">
              {o.legs.map((l: Json, i: number) => { const I = ICON[l.mode] ?? Car; return (
                <li key={i} className="flex gap-3 rounded-2xl bg-sand p-3 text-sm">
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-white text-ink/70" aria-hidden><I className="h-4 w-4" /></span>
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold capitalize">{l.mode}: {l.from} → {l.to}</p>
                    <p className="num text-xs text-ink/60">{mins(l.duration_min)}{l.distance_km ? ` · ${l.distance_km} km` : ''} · {l.mode === 'cab' ? '' : 'per person '}{inr(l.fare_inr + (l.extra_charges_inr || 0))}{l.mode === 'cab' ? ' for the cab' : ''}{l.depart ? ` · departs ${String(l.depart).slice(11, 16)}` : ''}{l.arrive ? ` · arrives ${String(l.arrive).slice(11, 16)}` : ''}</p>
                    <p className="text-xs text-ink/50">{[l.operator, l.stops ? `${l.stops} stop(s)` : null, l.availability_note].filter(Boolean).join(' · ')}</p>
                    <div className="mt-1 flex flex-wrap items-center gap-2"><Prov p={l.provenance} />{l.booking_link && <a className="link inline-flex items-center gap-1 py-1 text-xs" href={l.booking_link} target="_blank" rel="noreferrer">View &amp; book<ExternalLink className="h-3 w-3" aria-hidden /></a>}</div>
                  </div>
                </li>) })}
              {(o.notes ?? []).map((n: string) => <li key={n} className="flex gap-2 rounded-xl bg-sky-50 p-2.5 text-xs text-sky-900"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />{n}</li>)}
              <li className="text-xs text-ink/45">Includes {o.legs.some((l: Json) => l.mode === 'flight') ? '2.5 h airport check-in and 45 min after landing. ' : ''}Taxes and fees may vary; confirm with the operator.</li>
            </ol>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.article>
  )
}

/** Ranked list split into "within your travel budget" and "stretch" options. */
export default function RouteOptions({ data, chosenIndex, onChoose, busy }: { data: Json; chosenIndex?: number | null; onChoose?: (i: number) => void; busy?: boolean }) {
  const [sort, setSort] = useState('best')
  const opts: Json[] = data.options ?? []
  const sorted = useMemo(() => {
    const k: Record<string, (o: Json) => number> = { best: o => o.index, cheapest: o => o.total_fare_inr, fastest: o => o.total_duration_min, comfort: o => -o.comfort }
    return [...opts].sort((a, b) => k[sort](a) - k[sort](b))
  }, [opts, sort])
  const allowance = data.allowance_round_trip_inr as number | null | undefined
  const within = sorted.filter(o => o.fits_budget !== false)
  const over = sorted.filter(o => o.fits_budget === false)
  const stretch: Record<number, Json> = Object.fromEntries((data.stretch ?? []).map((s: Json) => [s.index, s]))
  return (
    <div className="space-y-5">
      {(data.notes ?? []).map((n: string) => <p key={n} className="flex gap-2.5 rounded-2xl bg-sky-50 p-3 text-sm text-sky-900"><Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />{n}</p>)}
      {data.airports?.origin && data.airports?.destination && <p className="num text-xs text-ink/55">Nearest airports: {data.airports.origin.city} ({data.airports.origin.iata}, {Math.round(data.airports.origin.km)} km from the start) → {data.airports.destination.city} ({data.airports.destination.iata}, {Math.round(data.airports.destination.km)} km from the destination). Straight-line distance {data.straight_km} km.</p>}
      {opts.length > 1 && <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Sort options">
        <span className="text-sm font-semibold text-ink/60">Sort</span>{SORTS.map(([k, l]) => <button key={k} aria-pressed={sort === k} onClick={() => setSort(k)} className={`chip !min-h-[34px] !py-1 ${sort === k ? 'chip-on' : ''}`}>{l}</button>)}
        {allowance != null && <span className="num ml-auto text-xs text-ink/55">Travel budget ≈ {inr(allowance)} round trip (45% of your total)</span>}
      </div>}
      {opts.length === 0 && <p className="rounded-2xl border border-dashed border-ink/20 p-6 text-center text-sm text-ink/60">No route options could be built for this pair.</p>}
      {allowance != null ? <>
        <section aria-label="Within budget"><h3 className="mb-3 font-display text-xl font-bold">Within your budget <span className="num text-sm font-normal text-ink/50">({within.length})</span></h3>
          {within.length === 0 ? <p className="rounded-2xl bg-amber-50 p-3 text-sm text-amber-900">Nothing fits that travel budget. The cheapest options are shown below with how far over they are. You can raise the budget or choose a cheaper destination.</p> :
            <div className="space-y-3">{within.map(o => <OptionCard key={o.index} o={o} allowance={allowance} chosen={chosenIndex === o.index} busy={busy} onChoose={onChoose && (() => onChoose(o.index))} />)}</div>}</section>
        {over.length > 0 && <section aria-label="Stretch options"><h3 className="mb-3 font-display text-xl font-bold">If you can stretch <span className="num text-sm font-normal text-ink/50">({over.length})</span></h3>
          <div className="space-y-3">{over.map(o => <div key={o.index}>
            {stretch[o.index] && <p className="num mb-1.5 text-sm font-medium text-amber-900">+{inr(stretch[o.index].extra_round_trip_inr)} round trip{stretch[o.index].saves_min > 0 ? ` → saves about ${mins(stretch[o.index].saves_min)}` : ''}{stretch[o.index].comfort_gain > 0.2 ? ' → more comfortable' : ''}</p>}
            <OptionCard o={o} allowance={allowance} chosen={chosenIndex === o.index} busy={busy} onChoose={onChoose && (() => onChoose(o.index))} /></div>)}</div></section>}
      </> : <div className="space-y-3">{sorted.map(o => <OptionCard key={o.index} o={o} chosen={chosenIndex === o.index} busy={busy} onChoose={onChoose && (() => onChoose(o.index))} />)}</div>}
    </div>
  )
}
