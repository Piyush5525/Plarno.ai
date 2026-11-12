import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowRight, BookOpen, Flower2, Home, Landmark, Leaf, Minus, Plus, ShoppingBag, Sparkles, Utensils, TreePine } from './icons'
import { useApp } from '../store'
import PlaceInput from './PlaceInput'

const POPULAR = ['Paris', 'Tokyo', 'Bali', 'New York', 'Dubai', 'Goa', 'Rome', 'Bangkok', 'Delhi', 'London', 'Singapore']
const INTERESTS: [string, string, string, typeof Landmark][] = [['history', 'History', 'historical places', Landmark], ['food', 'Food', 'good food', Utensils], ['museum', 'Museums', 'museums', BookOpen], ['garden', 'Nature', 'parks and gardens', TreePine],
  ['shopping', 'Shopping', 'shopping markets', ShoppingBag], ['religious', 'Temples & shrines', 'temples', Flower2], ['peaceful', 'Peaceful', 'a peaceful quiet hotel', Leaf]]
const PENDING = 'plarno_pending_prompt'

type Form = { dest: string; from: string; days: number; adults: number; budget: string; date: string; interests: string[]; pace: string; home: boolean }

export function composePrompt(f: Form) {
  const words = INTERESTS.filter(([k]) => f.interests.includes(k)).map(([, , w]) => w)
  const tail = `${f.date ? `, start ${f.date}` : ''}${f.budget ? `, budget ₹${f.budget}` : ''}. ${words.length ? 'I like ' + words.join(', ') + '. ' : ''}${f.pace !== 'balanced' ? `${f.pace} pace.` : ''}`
  const who = `${f.adults} ${f.adults === 1 ? 'person' : 'people'}`
  const msg = f.home
    ? `I live in ${f.dest.trim()}. Plan a ${f.days} day trip exploring places near me for ${who}${tail}`
    : `Plan a ${f.days} day trip to ${f.dest.trim()}${f.from.trim() ? ` from ${f.from.trim()}` : ''} for ${who}${tail}`
  return msg.trim()
}

/** Number field with large − / + buttons (easier than typing on a phone). */
function Stepper({ id, label, value, min, max, onChange }: { id: string; label: string; value: number; min: number; max: number; onChange: (n: number) => void }) {
  const clamp = (n: number) => Math.max(min, Math.min(max, n))
  return (
    <div><label className="label" htmlFor={id}>{label}</label>
      <div className="flex items-center rounded-2xl border border-ink/15 bg-white transition focus-within:border-coral focus-within:ring-4 focus-within:ring-coral/15">
        <button type="button" aria-label={`Fewer ${label.toLowerCase()}`} disabled={value <= min} onClick={() => onChange(clamp(value - 1))} className="grid h-[42px] w-10 shrink-0 place-items-center rounded-l-2xl text-ink/60 transition hover:bg-sand hover:text-coral disabled:opacity-30"><Minus className="h-4 w-4" /></button>
        <input id={id} type="number" inputMode="numeric" min={min} max={max} value={value} onChange={e => onChange(clamp(+e.target.value || min))} className="num h-[42px] w-full min-w-0 bg-transparent text-center text-base font-semibold outline-none sm:text-sm [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none" />
        <button type="button" aria-label={`More ${label.toLowerCase()}`} disabled={value >= max} onClick={() => onChange(clamp(value + 1))} className="grid h-[42px] w-10 shrink-0 place-items-center rounded-r-2xl text-ink/60 transition hover:bg-sand hover:text-coral disabled:opacity-30"><Plus className="h-4 w-4" /></button>
      </div>
    </div>
  )
}

/** Structured trip form: friendlier than free text; produces the same natural-language request TRIP understands. */
export default function TripBuilder({ compact = false }: { compact?: boolean }) {
  const { user, send, busy } = useApp()
  const nav = useNavigate()
  const [sp] = useSearchParams()
  const [f, setF] = useState<Form>({ dest: (sp.get('to') ?? '').slice(0, 60), from: '', days: 4, adults: 2, budget: '', date: '', interests: ['history', 'food'], pace: 'balanced', home: false })
  const [err, setErr] = useState<string | null>(null)
  const toggle = (k: string) => setF(s => ({ ...s, interests: s.interests.includes(k) ? s.interests.filter(x => x !== k) : [...s.interests, k] }))

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (f.dest.trim().length < 2) { setErr(f.home ? 'Tell me which town or city you live in.' : 'Tell me where you would like to go.'); return }
    if (!f.budget || Number(f.budget) < 500) { setErr('Add a total budget in ₹ (at least 500) so I can plan realistically.'); return }
    setErr(null)
    const msg = composePrompt(f)
    if (!user) { try { sessionStorage.setItem(PENDING, msg) } catch { /* ignore */ } nav('/auth'); return }
    nav('/workspace'); void send(msg)
  }
  return (
    <form onSubmit={submit} noValidate className={`rounded-[2rem] border border-white/60 bg-white p-5 text-ink shadow-lift ${compact ? '' : 'md:p-8'}`} aria-label="Plan a trip">
      <div className="mb-5 inline-flex w-full rounded-2xl bg-sand p-1 sm:w-auto" role="group" aria-label="Kind of trip">
        {([[false, 'Travel somewhere', Sparkles], [true, 'Day trips from home', Home]] as [boolean, string, typeof Home][]).map(([v, l, Icon]) => (
          <button key={l} type="button" aria-pressed={f.home === v} onClick={() => setF({ ...f, home: v })} className={`relative flex min-h-[42px] flex-1 items-center justify-center gap-2 rounded-xl px-4 text-sm font-semibold transition-colors sm:flex-none ${f.home === v ? 'text-ink' : 'text-ink/55 hover:text-ink'}`}>
            {f.home === v && <motion.span layoutId={`tb-mode-${compact}`} className="absolute inset-0 rounded-xl bg-white shadow-soft" transition={{ type: 'spring', stiffness: 420, damping: 34 }} />}
            <span className="relative z-10 flex items-center gap-2"><Icon className="h-4 w-4" aria-hidden />{l}</span>
          </button>
        ))}
      </div>
      <AnimatePresence initial={false}>{f.home && <motion.p initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden text-sm text-ink/60"><span className="mb-4 block rounded-2xl bg-lagoon-50 p-3 text-lagoon-700">Great for your own town: nearby places, local food and a day-by-day schedule, with no hotel or long-distance travel.</span></motion.p>}</AnimatePresence>

      <div className="grid gap-4 md:grid-cols-6">
        <div className={f.home ? 'md:col-span-6' : 'md:col-span-3'}>
          <PlaceInput id={compact ? 'tbc-dest' : 'tb-dest'} label={f.home ? 'Your town or city' : 'Where to?'} placeholder={f.home ? 'e.g. Kishangarh, Rajasthan' : 'Any city in the world, e.g. Paris'} value={f.dest} onChange={v => setF(s => ({ ...s, dest: v }))} />
        </div>
        {!f.home && <div className="md:col-span-3">
          <PlaceInput id={compact ? 'tbc-from' : 'tb-from'} label="Travelling from (optional)" placeholder="Your town, college or station: adds routes and fares" value={f.from} onChange={v => setF(s => ({ ...s, from: v }))} />
        </div>}
        <Stepper id={compact ? 'tbc-days' : 'tb-days'} label={f.home ? 'Days out' : 'Days'} value={f.days} min={1} max={21} onChange={n => setF(s => ({ ...s, days: n }))} />
        <Stepper id={compact ? 'tbc-adults' : 'tb-adults'} label="Travellers" value={f.adults} min={1} max={12} onChange={n => setF(s => ({ ...s, adults: n }))} />
        <div className="md:col-span-2"><label className="label" htmlFor={compact ? 'tbc-budget' : 'tb-budget'}>Total budget (₹)</label><input id={compact ? 'tbc-budget' : 'tb-budget'} type="number" inputMode="numeric" min={500} step={500} className="input num" placeholder={f.home ? 'e.g. 8000' : 'e.g. 150000'} value={f.budget} onChange={e => setF({ ...f, budget: e.target.value })} /></div>
        <div className="md:col-span-2"><label className="label" htmlFor={compact ? 'tbc-date' : 'tb-date'}>Start date</label><input id={compact ? 'tbc-date' : 'tb-date'} type="date" className="input num" min={new Date().toISOString().slice(0, 10)} value={f.date} onChange={e => setF({ ...f, date: e.target.value })} /></div>
      </div>
      <fieldset className="mt-5"><legend className="label">What do you enjoy?</legend>
        <div className="flex flex-wrap gap-2">{INTERESTS.map(([k, l, , Icon]) => <motion.button whileTap={{ scale: 0.94 }} type="button" key={k} aria-pressed={f.interests.includes(k)} onClick={() => toggle(k)} className={`chip ${f.interests.includes(k) ? 'chip-on' : ''}`}><Icon className="h-3.5 w-3.5" aria-hidden />{l}</motion.button>)}</div></fieldset>
      <div className="mt-5 flex flex-wrap items-end justify-between gap-4">
        <div><p className="label">Pace</p><div className="inline-flex rounded-full bg-sand p-1" role="group" aria-label="Pace">{['relaxed', 'balanced', 'packed'].map(p => (
          <button type="button" key={p} aria-pressed={f.pace === p} onClick={() => setF({ ...f, pace: p })} className={`relative min-h-[36px] rounded-full px-4 text-sm font-semibold capitalize transition-colors ${f.pace === p ? 'text-white' : 'text-ink/60 hover:text-ink'}`}>
            {f.pace === p && <motion.span layoutId={`tb-pace-${compact}`} className="absolute inset-0 rounded-full bg-ink" transition={{ type: 'spring', stiffness: 420, damping: 34 }} />}<span className="relative z-10">{p}</span></button>))}</div></div>
        <button className="btn btn-primary w-full !px-8 !py-3.5 text-base sm:w-auto" disabled={busy}>{f.home ? 'Plan my outings' : 'Plan my trip'}<ArrowRight className="h-4 w-4" aria-hidden /></button>
      </div>
      <AnimatePresence>{err && <motion.p initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} role="alert" className="mt-3 rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</motion.p>}</AnimatePresence>
      {!f.home && <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-ink/[.06] pt-4 text-xs text-ink/50"><span className="font-semibold">Popular:</span>
        {POPULAR.map(c => <button type="button" key={c} onClick={() => setF({ ...f, dest: c })} className={`min-h-[34px] rounded-full px-3 font-medium transition hover:bg-coral-50 hover:text-coral-600 ${f.dest === c ? 'bg-coral-50 text-coral-700' : 'bg-sand'}`}>{c}</button>)}</div>}
    </form>
  )
}
export { PENDING }
