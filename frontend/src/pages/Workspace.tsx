import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  AlertTriangle, ArrowUpRight, BedDouble, Bot, CalendarDays, Car, Check, ChevronDown, ChevronUp, Clock, Compass, ExternalLink, Home, Info, Lightbulb, List, Map as MapIcon, MapPin, Navigation,
  Plane, Plus, Radio, Receipt, Ruler, Send, ShieldCheck, Sparkles, Ticket, Users, Utensils, Wallet, X,
} from '../components/icons'
import { api, inr, mins, Json } from '../api'
import { useApp } from '../store'
import { useRebuild } from '../hooks'
import { CountUp, Empty, ErrorBox, Loading, MapView, PageHead, Photo, Pin, Prov, Segmented, Stars } from '../components/ui'
import TripBuilder from '../components/TripBuilder'
import PlaceDetail from '../components/PlaceDetail'
import RouteOptions from '../components/RouteOptions'
import Guide from '../components/Guide'

const TABS: [string, string, typeof Radio][] = [['guide', 'Live guide', Radio], ['itinerary', 'Itinerary', CalendarDays], ['map', 'Map', MapIcon], ['travel', 'Travel', Navigation], ['hotels', 'Hotels', BedDouble],
  ['areas', 'Areas', MapPin], ['budget', 'Budget', Wallet], ['safety', 'Safety', ShieldCheck], ['bookings', 'Bookings', Ticket], ['agents', 'Agents', Bot]]
const NEED: Record<string, string> = { start_date: 'start date', origin: 'where you are travelling from', destination: 'destination', days: 'number of days', travellers: 'number of travellers', budget: 'budget' }
const WORKING = ['Finding real places and their opening hours…', 'Checking hotel rates for your dates…', 'Comparing flights, trains and cabs…', 'Ordering each day to cut backtracking…', 'Adding up the budget…']
const IDEAS = ['Make it cheaper', 'Add more sightseeing', 'Make the pace relaxed', 'Find a hotel closer to the sights']

function Working() {
  const [i, setI] = useState(0)
  useEffect(() => { const iv = window.setInterval(() => setI(x => (x + 1) % WORKING.length), 2600); return () => window.clearInterval(iv) }, [])
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mb-6 overflow-hidden rounded-3xl border border-ink/[.07] bg-white p-5 shadow-soft" role="status">
      <div className="flex items-center gap-3">
        <span className="relative grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-coral text-white"><span className="absolute inset-0 animate-ping rounded-2xl bg-coral/40" aria-hidden /><Sparkles className="relative h-5 w-5" aria-hidden /></span>
        <div className="min-w-0"><p className="font-semibold">TRIP's agents are on it</p>
          <AnimatePresence mode="wait"><motion.p key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.25 }} className="text-sm text-ink/60">{WORKING[i]}</motion.p></AnimatePresence></div>
      </div>
      <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-ink/[.06]"><motion.div className="h-full w-1/3 rounded-full bg-gradient-to-r from-coral via-sun to-lagoon" animate={{ x: ['-100%', '300%'] }} transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }} /></div>
      <p className="mt-3 text-xs text-ink/45">A city we have not seen before can take up to about 30 seconds. Repeat requests are much faster.</p>
    </motion.div>
  )
}

export default function Workspace() {
  const app = useApp()
  const { plan, context, tripId, send, busy, followUps } = app
  const [sp, setSp] = useSearchParams()
  const tab = TABS.some(([k]) => k === sp.get('tab')) ? sp.get('tab')! : 'guide'
  const goTab = (k: string) => { setSp({ tab: k }); window.scrollTo({ top: 0, behavior: 'smooth' }) }
  const [text, setText] = useState('')
  const hasPlan = !!plan?.itinerary
  const last = app.messages.at(-1)
  const home = plan.hotel?.id === 'home'

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 md:py-10">
      <PageHead eyebrow={hasPlan ? `${context.days} days · ${context.adults + (context.children || 0)} traveller${context.adults + (context.children || 0) === 1 ? '' : 's'}` : 'Trip planner'}
        title={hasPlan ? (context.stay_home ? `Day trips from ${context.destination}` : `Your trip to ${context.destination}`) : 'Plan a trip'}
        sub={hasPlan ? 'Change anything below or just tell TRIP. Only the parts that depend on your change are recalculated.' : 'Describe it in plain language or use the form. Plarno finds real places, hotels and flights.'} />

      <form className="mb-3 flex flex-col gap-2 sm:flex-row" onSubmit={e => { e.preventDefault(); if (text.trim()) { void send(text); setText('') } }}>
        <div className="relative flex-1"><Sparkles className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-coral" aria-hidden />
          <input className="input !rounded-full !py-3.5 !pl-11" value={text} onChange={e => setText(e.target.value)} disabled={busy} aria-label="Describe your trip"
            placeholder={hasPlan ? 'Ask for a change: “make it cheaper”, “change my hotel to …”' : 'e.g. Plan 5 days in Tokyo for two, budget ₹300000, love food and temples'} /></div>
        <button className="btn btn-primary !px-6 !py-3.5" disabled={busy || !text.trim()}><Send className="h-4 w-4" aria-hidden />{busy ? 'Working…' : 'Send'}</button>
      </form>
      {hasPlan && <div className="mb-6 flex flex-wrap gap-2">{IDEAS.map(q => <button key={q} disabled={busy} onClick={() => void send(q)} className="chip !min-h-[32px] !py-1 !text-xs">{q}</button>)}</div>}
      {!hasPlan && <div className="mb-6" />}

      {busy && <Working />}
      {followUps.length > 0 && !busy && <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} className="mb-5 flex items-start gap-3 rounded-2xl border border-amber-200 bg-sun-50 p-4 text-sm text-amber-900"><Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden /><p>TRIP still needs: <b>{followUps.map(f => NEED[f] ?? f).join(', ')}</b>. Tell me in the box above or use the TRIP chat.</p></motion.div>}

      {!hasPlan && !busy ? (
        <div className="space-y-6">
          {last?.role === 'assistant' && <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="whitespace-pre-wrap rounded-2xl border border-coral/20 bg-coral-50 p-4 text-sm">{last.content.replace(/\*\*/g, '')}</motion.div>}
          <TripBuilder compact />
        </div>
      ) : hasPlan && (
        <>
          <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat i={0} Icon={MapPin} label="Destination" value={`${context.destination}`} sub={[`${context.days} days`, context.dest_geo?.country].filter(Boolean).join(' · ')} />
            <Stat i={1} Icon={Users} label="Travellers" value={String(context.adults + (context.children || 0))} sub={context.start_date ? `from ${context.start_date}${context.dates_assumed ? ' (assumed)' : ''}` : undefined} />
            <Stat i={2} Icon={Wallet} label="Estimated total" num={plan.budget?.estimated_total_inr} value={inr(plan.budget?.estimated_total_inr)} sub={plan.budget?.within_budget === false ? 'over budget' : plan.budget?.max_budget_inr ? `of ${inr(plan.budget.max_budget_inr)}` : ''} bad={plan.budget?.within_budget === false} />
            <Stat i={3} Icon={home ? Home : BedDouble} label={home ? 'Base' : 'Stay'} value={home ? `Home in ${context.destination}` : plan.hotel?.name} sub={home ? 'no hotel or long-distance travel' : `${inr(plan.hotel?.price_per_night)}/night`} />
          </div>
          {context.dates_assumed && <p className="mb-3 flex items-center gap-2 text-xs text-amber-700"><AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden />Start date ({context.start_date}) is an assumption: hotel rates depend on dates. Tell TRIP your real dates.</p>}

          <div className="sticky top-[68px] z-30 -mx-4 mb-6 px-4">
            <div className="no-scrollbar flex gap-1 overflow-x-auto rounded-full border border-ink/[.07] bg-white/90 p-1 shadow-soft backdrop-blur-xl" role="tablist" aria-label="Trip sections">
              {TABS.map(([k, l, Icon]) => (
                <button key={k} role="tab" id={`tab-${k}`} aria-selected={tab === k} aria-controls="tab-panel" onClick={() => setSp({ tab: k })} className={`relative flex min-h-[42px] items-center gap-2 whitespace-nowrap rounded-full px-4 text-sm font-semibold transition-colors ${tab === k ? 'text-white' : 'text-ink/60 hover:text-ink'}`}>
                  {tab === k && <motion.span layoutId="ws-tab" className="absolute inset-0 rounded-full bg-ink" transition={{ type: 'spring', stiffness: 400, damping: 34 }} />}
                  <span className="sr-only">{k}</span><span aria-hidden className="relative z-10 flex items-center gap-2"><Icon className={`h-4 w-4 ${k === 'guide' && tab !== k ? 'text-coral' : ''}`} />{l}</span>
                </button>
              ))}
            </div>
          </div>

          {/* enter-only transition: the old panel leaves at once, so a tab switch can never wait on (or be blocked by) an exit animation */}
            <motion.div key={tab} id="tab-panel" role="tabpanel" aria-labelledby={`tab-${tab}`} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.28, ease: [0.2, 0.8, 0.2, 1] }}>
              {tab === 'guide' && <Guide goTab={goTab} />}
              {tab === 'itinerary' && <Itinerary />}
              {tab === 'travel' && <TravelTab />}
              {tab === 'map' && <MapTab />}
              {tab === 'hotels' && <Hotels />}
              {tab === 'areas' && <Areas />}
              {tab === 'budget' && <BudgetTab />}
              {tab === 'safety' && <Safety />}
              {tab === 'bookings' && <Bookings />}
              {tab === 'agents' && <Agents />}
            </motion.div>
        </>
      )}
      {tripId && <p className="mt-10 flex items-center gap-1.5 text-xs text-ink/40"><Check className="h-3.5 w-3.5" aria-hidden />Trip #{tripId} · saved automatically</p>}
    </div>
  )
}

function Stat({ Icon, label, value, sub, bad, num, i }: { Icon: typeof MapPin; label: string; value?: string; sub?: string; bad?: boolean; num?: number; i: number }) {
  return (
    <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06, duration: 0.4 }} className="card flex items-center gap-3 !p-4">
      <div className={`icon-tile ${bad ? 'bg-rose-100 text-rose-700' : 'bg-sand-200 text-ink'}`} aria-hidden><Icon className="h-5 w-5" /></div>
      <div className="min-w-0"><p className="text-[11px] font-bold uppercase tracking-[.1em] text-ink/45">{label}</p>
        <p className={`truncate font-display text-lg font-bold leading-tight ${bad ? 'text-rose-700' : ''}`} title={value}>{num != null ? <CountUp value={num} format={v => inr(v)} /> : value ?? '—'}</p>
        {sub && <p className="truncate text-xs text-ink/50">{sub}</p>}</div>
    </motion.div>
  )
}

/** Small stop photo; falls back to an icon when there is no photo or it fails to load. */
function StopThumb({ src, meal }: { src?: string | null; meal: boolean }) {
  const [bad, setBad] = useState(false)
  if (src && !bad) return <img src={src} alt="" loading="lazy" referrerPolicy="no-referrer" className="h-12 w-12 shrink-0 rounded-xl object-cover" onError={() => setBad(true)} />
  return <div className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-white text-ink/60" aria-hidden>{meal ? <Utensils className="h-5 w-5" /> : <MapPin className="h-5 w-5" />}</div>
}

function Itinerary() {
  const { plan, context, tripId, setPlan } = useApp()
  const rb = useRebuild()
  const [delay, setDelay] = useState('')
  const [rec, setRec] = useState<Json>(plan.pending_recovery ?? null)
  const [recMsg, setRecMsg] = useState<string | null>(null)
  const [approval, setApproval] = useState<Json>(null)
  const ids: string[] = context.selected_attraction_ids ?? []
  const world = !!plan.world
  const [sel, setSel] = useState<{ item: Json; kind: 'attraction' | 'restaurant'; addable?: boolean } | null>(null)
  const openStop = (s: Json) => {
    const cat = plan.catalog
    const found = (s.type === 'meal' ? cat?.restaurants : cat?.attractions)?.find((x: Json) => x.id === s.id)
    setSel({ item: found ?? { ...s, types: [], description: undefined, address: undefined }, kind: s.type === 'meal' ? 'restaurant' : 'attraction' })
  }
  const move = (id: string, dir: -1 | 1) => { const i = ids.indexOf(id); const j = i + dir; if (j < 0 || j >= ids.length) return; const n = [...ids]; [n[i], n[j]] = [n[j], n[i]]; void rb.run({ attraction_ids: n }) }
  const [demoAll, setDemoAll] = useState<Json[]>([])
  useEffect(() => { if (!world) api('/destinations').then(r => setDemoAll(r.attractions)).catch(() => {}) }, [world])
  const pool: Json[] = world ? plan.catalog?.attractions ?? [] : demoAll
  const available = pool.filter(a => !ids.includes(a.id)).slice(0, 14)

  async function propose() {
    setRecMsg(null)
    try { const r = await api(`/trips/${tripId}/recovery/propose`, { body: { delay_min: Math.round(parseFloat(delay) * 60) } }); setRec(r) } catch (e) { setRecMsg((e as Error).message) }
  }
  async function requestApproval(id: string) {
    try { setApproval(await api(`/trips/${tripId}/recovery/request-approval`, { body: { option_id: id } })) } catch (e) { setRecMsg((e as Error).message) }
  }
  async function decide(ok: boolean) {
    try {
      await api(`/approvals/${approval.approval_id}/decide`, { body: { approve: ok, idempotency_key: crypto.randomUUID() } })
      setApproval(null); setRec(null); setRecMsg(ok ? 'Approved. Itinerary and budget updated.' : 'Rejected. Nothing changed.')
      const t = await api(`/trips/${tripId}`); setPlan(t.plan)
    } catch (e) { setRecMsg((e as Error).message) }
  }

  return (
    <div className="space-y-6">
      {rb.err && <ErrorBox msg={rb.err} />}
      {sel && <PlaceDetail item={sel.item} kind={sel.kind} onClose={() => setSel(null)} busy={rb.busy} onAdd={sel.addable ? async () => { await rb.run({ attraction_ids: [...ids, sel.item.id] }); setSel(null) } : undefined} />}
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-semibold text-ink/60">Pace</span>
        {['relaxed', 'balanced', 'packed'].map(p => <button key={p} disabled={rb.busy} aria-pressed={context.pace === p} onClick={() => void rb.run({ pace: p })} className={`chip capitalize ${context.pace === p ? 'chip-on' : ''}`}>{p}</button>)}
        <span className="ml-auto flex items-center gap-2 text-xs text-ink/50">{rb.busy && <span className="h-3 w-3 animate-spin rounded-full border-2 border-ink/20 border-t-coral" aria-hidden />}{rb.busy ? 'Updating…' : plan.itinerary.provenance}</span>
      </div>
      {plan.itinerary.dropped_for_pace?.length > 0 && <p className="flex items-start gap-2 rounded-2xl bg-sun-50 p-3 text-sm text-amber-900"><Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />Dropped to respect your pace: {plan.itinerary.dropped_for_pace.join(', ')}</p>}
      <div className={`grid grid-cols-1 gap-5 transition-opacity lg:grid-cols-2 ${rb.busy ? 'opacity-60' : ''}`}>
        {plan.itinerary.days.map((d: Json, di: number) => {
          const cover = d.stops.find((s: Json) => s.type === 'attraction' && s.thumbnail)?.thumbnail
          return (
            <motion.article key={d.day} initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(di, 6) * 0.06 }} className="card group space-y-3 !p-4">
              <Photo src={cover} name={d.title.replace(/^Day \d+: /, '')} h="h-40" zoom>
                <div className="absolute inset-0 bg-gradient-to-t from-ink-900/80 via-ink-900/10 to-transparent" />
                <span className="num absolute left-3 top-3 rounded-full bg-white/95 px-3 py-1 text-xs font-bold shadow-soft">Day {d.day} · {d.date}</span>
                <span className="absolute bottom-3 left-3 right-3 truncate font-display text-xl font-bold text-white drop-shadow">{d.title.replace(/^Day \d+: /, '')}</span>
              </Photo>
              <div className="num flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink/60"><span className="flex items-center gap-1.5"><Car className="h-3.5 w-3.5" aria-hidden />{mins(d.travel_min)} travel</span><span className="flex items-center gap-1.5"><Ruler className="h-3.5 w-3.5" aria-hidden />{d.distance_km} km</span><span className="flex items-center gap-1.5"><Wallet className="h-3.5 w-3.5" aria-hidden />{inr(d.cost_inr)} est.</span></div>
              {d.stops.length === 0 && <p className="text-sm text-ink/50">Free day. Ask TRIP to “add more sightseeing”.</p>}
              <ol className="relative space-y-2 before:absolute before:bottom-6 before:left-[1.85rem] before:top-6 before:w-px before:bg-ink/10">
                {d.stops.map((s: Json, i: number) => (
                  <li key={i} className={`relative flex items-start gap-3 rounded-2xl p-2.5 transition-colors ${s.type === 'meal' ? 'bg-sun-50' : 'bg-sand hover:bg-sand-200'} ${s.status === 'needs_reschedule' ? 'ring-2 ring-rose-300' : ''}`}>
                    <StopThumb src={s.thumbnail} meal={s.type === 'meal'} />
                    <div className="min-w-0 flex-1 text-sm">
                      <p className="font-semibold leading-snug"><button className="-my-1 inline-block py-1.5 text-left underline-offset-2 hover:underline" aria-label={`Details for ${s.name}`} onClick={() => openStop(s)}>{s.name}</button>{s.status === 'needs_reschedule' && <span className="badge ml-2 bg-rose-100 text-rose-800">needs reschedule</span>}</p>
                      <p className="text-xs text-ink/55"><span className="num font-semibold text-ink/75">{s.start}</span> · {s.type === 'meal' ? `${s.meal} · ${s.note} · ${inr(s.cost_inr)}` : `${s.travel_km} km by cab (${Math.round(s.travel_min)} min, ≈ ${inr(Math.max(100, Math.round(s.travel_km * 14)))} est.) · ${s.fee_known ? inr(s.fee_inr) : 'ticket price unverified'}`}</p>
                      <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-ink/50"><Stars v={s.rating} n={s.reviews} />{s.type === 'attraction' && s.hours_note && <span className="flex min-w-0 items-center gap-1" title={s.hours_note}><Clock className="h-3 w-3 shrink-0" aria-hidden /><span className="truncate">{s.hours_note}</span></span>}{s.hours_flag === 'closed' && <span className="badge bg-rose-100 text-rose-800">closed that day: swap or check</span>}{s.hours_flag === 'closes_early' && <span className="badge bg-amber-100 text-amber-800">may close before you finish</span>}{s.maps_url && <a href={s.maps_url} target="_blank" rel="noreferrer" className="link inline-block py-2">Google Maps</a>}{s.website && <a href={s.website} target="_blank" rel="noreferrer" className="link inline-block py-2">Website</a>}</div>
                    </div>
                    {s.type === 'attraction' && <div className="flex shrink-0 flex-col items-center text-ink/50">
                      <button aria-label={`Move ${s.name} earlier`} className="grid h-8 w-8 place-items-center rounded-lg transition hover:bg-white hover:text-coral disabled:opacity-30" onClick={() => move(s.id, -1)} disabled={rb.busy || ids.indexOf(s.id) <= 0}><ChevronUp className="h-4 w-4" /></button>
                      <button aria-label={`Move ${s.name} later`} className="grid h-8 w-8 place-items-center rounded-lg transition hover:bg-white hover:text-coral disabled:opacity-30" onClick={() => move(s.id, 1)} disabled={rb.busy || ids.indexOf(s.id) >= ids.length - 1}><ChevronDown className="h-4 w-4" /></button>
                      <button aria-label={`Remove ${s.name}`} className="grid h-8 w-8 place-items-center rounded-lg text-rose-600 transition hover:bg-white disabled:opacity-30" disabled={rb.busy || ids.length <= 1} onClick={() => void rb.run({ attraction_ids: ids.filter(x => x !== s.id) })}><X className="h-4 w-4" /></button>
                    </div>}
                  </li>
                ))}
              </ol>
            </motion.article>
          )
        })}
      </div>
      {available.length > 0 && (
        <div className="card">
          <p className="mb-3 flex items-center gap-2 font-display text-lg font-bold"><Plus className="h-4 w-4 text-coral" aria-hidden />Add a place</p>
          <div className="flex flex-wrap gap-2">{available.map(a => <button key={a.id} disabled={rb.busy} onClick={() => setSel({ item: a, kind: 'attraction', addable: true })} className="chip !text-xs"><Plus className="h-3 w-3" aria-hidden />{a.name}{a.rating ? ` · ${a.rating}` : ''}</button>)}</div>
        </div>
      )}
      <div className="card space-y-3">
        <p className="flex items-center gap-2 font-display text-xl font-bold"><AlertTriangle className="h-5 w-5 text-sun" aria-hidden />Travel disruption</p>
        <p className="text-sm text-ink/60">If your journey is delayed, enter the delay. TRIP shows what is affected and your options. Nothing changes until you approve.</p>
        <div className="flex flex-wrap gap-2">
          <input className="input !w-44" type="number" min="0.5" step="0.5" placeholder="Delay (hours)" value={delay} onChange={e => setDelay(e.target.value)} aria-label="Delay in hours" />
          <button className="btn btn-ghost" disabled={!plan.journey || !(parseFloat(delay) > 0)} onClick={() => void propose()}>Assess impact</button>
          {!plan.journey && <span className="self-center text-xs text-ink/50">Add where you are travelling from to the trip to model a journey.</span>}
        </div>
        {recMsg && <p className="text-sm text-lagoon-700" role="status">{recMsg}</p>}
        {rec && (
          <div className="space-y-2 text-sm">
            <p>New arrival <b>{rec.disruption.new_arrival}</b>. Affected: {rec.affected_activities.map((a: Json) => a.name).join(', ') || 'none'}.</p>
            {rec.options.map((o: Json) => <div key={o.id} className="flex items-center justify-between gap-3 rounded-2xl border border-ink/10 p-3"><div><p className="font-semibold">{o.label}</p><p className="text-xs text-ink/60">{o.detail} · {o.extra_cost_inr < 0 ? 'saves' : 'extra'} {inr(Math.abs(o.extra_cost_inr))}</p></div><button className="btn btn-ghost btn-sm" onClick={() => void requestApproval(o.id)}>Choose</button></div>)}
          </div>
        )}
        {approval && <div className="rounded-2xl border-2 border-amber-300 bg-amber-50 p-4 text-sm"><p className="font-semibold">Approval needed</p><p className="mt-1">This applies the selected option and recalculates your itinerary and budget.</p><div className="mt-3 flex gap-2"><button className="btn btn-dark" onClick={() => void decide(true)}>Approve</button><button className="btn btn-ghost" onClick={() => void decide(false)}>Reject</button></div></div>}
      </div>
    </div>
  )
}

function MapTab() {
  const { plan } = useApp()
  const [day, setDay] = useState(0)
  const [view, setView] = useState<'map' | 'list'>('map')
  const [road, setRoad] = useState<Json>(null)
  const [active, setActive] = useState<string | null>(null)
  const days: Json[] = plan.itinerary.days
  const d = days[Math.min(day, days.length - 1)]
  const hotel = plan.itinerary.hotel
  const attractionStops = d.stops.filter((s: Json) => s.type === 'attraction')
  const pins: Pin[] = useMemo(() => [
    ...(hotel ? [{ id: 'hotel', lat: hotel.lat, lon: hotel.lon, label: 'Your hotel: ' + hotel.name, color: '#0b1f33', kind: 'hotel' }] : []),
    ...d.stops.map((s: Json, i: number) => ({ id: `s${i}`, lat: s.lat, lon: s.lon, label: `${s.start} ${s.name}`, color: s.type === 'meal' ? '#f6b73c' : '#f4553f', kind: s.type === 'meal' ? 'meal' : undefined, n: s.type === 'meal' ? undefined : attractionStops.indexOf(s) + 1 })),
  ], [d, hotel])
  useEffect(() => {  // real road route (Mapbox) for the day's stops; falls back to the straight-line sketch
    setRoad(null); setActive(null)
    if (!hotel || attractionStops.length === 0) return
    const pts = [[hotel.lat, hotel.lon], ...attractionStops.map((s: Json) => [s.lat, s.lon]), [hotel.lat, hotel.lon]]
    let dead = false
    api('/route/directions', { body: { points: pts, profile: 'driving' } }).then(r => { if (!dead) setRoad(r) }).catch(() => {})
    return () => { dead = true }
  }, [day, plan.itinerary])
  const line = road?.geometry?.length ? [road.geometry] : d.route_geometry?.length ? [d.route_geometry] : undefined
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {days.map((x, i) => <button key={i} onClick={() => setDay(i)} aria-pressed={i === day} className={`chip ${i === day ? 'chip-on' : ''}`}>Day {x.day}</button>)}
        <div className="ml-auto"><Segmented id="mapview" label="View" value={view} onChange={setView} options={[['map', <><MapIcon className="h-3.5 w-3.5" aria-hidden />Map</>], ['list', <><List className="h-3.5 w-3.5" aria-hidden />List</>]]} /></div>
      </div>
      {view === 'map' ? (
        <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
          <MapView pins={pins} route={line} height={520} activeId={active} onPinClick={setActive} traveller />
          <ol className="card max-h-[520px] space-y-1.5 overflow-y-auto !p-3">
            <li className="px-1 pb-1 text-[11px] font-bold uppercase tracking-[.12em] text-ink/45">Day {d.day} stops</li>
            {d.stops.length === 0 && <li className="p-2 text-sm text-ink/55">No stops on this day.</li>}
            {d.stops.map((s: Json, i: number) => (
              <li key={i}><button onMouseEnter={() => setActive(`s${i}`)} onFocus={() => setActive(`s${i}`)} onClick={() => setActive(`s${i}`)} className={`flex w-full items-center gap-3 rounded-2xl p-2.5 text-left text-sm transition ${active === `s${i}` ? 'bg-coral-50 ring-1 ring-coral/30' : 'hover:bg-sand'}`}>
                <span className={`num grid h-8 w-8 shrink-0 place-items-center rounded-full text-xs font-bold text-white ${s.type === 'meal' ? 'bg-sun' : 'bg-coral'}`}>{s.type === 'meal' ? <Utensils className="h-3.5 w-3.5" aria-hidden /> : attractionStops.indexOf(s) + 1}</span>
                <span className="min-w-0"><span className="block truncate font-semibold">{s.name}</span><span className="num block text-xs text-ink/50">{s.start}{s.type === 'attraction' ? ` · ${s.travel_km} km hop` : ` · ${s.meal}`}</span></span></button></li>
            ))}
          </ol>
        </div>
      ) : (
        <ul className="card divide-y divide-ink/10 text-sm">{d.stops.map((s: Json, i: number) => <li key={i} className="flex justify-between gap-3 py-2.5"><span><span className="num font-semibold">{s.start}</span> · {s.name}</span><span className="num text-ink/50">{s.lat.toFixed(4)}, {s.lon.toFixed(4)}</span></li>)}</ul>
      )}
      <div className="flex flex-wrap items-center gap-2 text-xs text-ink/60">
        {road ? <><Prov p={road.provenance} /> <span>Road route: {road.distance_km} km, ~{Math.round(road.duration_min)} min driving, no live traffic ({road.provenance.source}).</span></> : <span>Showing a straight-line sketch while the road route loads.</span>}
        <span>Pins: <b className="text-ink">dark = your stay</b>, <b className="text-coral">numbered = sights in visiting order</b>, <b className="text-amber-600">yellow = meals</b>. Use the target button on the map to show where you are.</span>
      </div>
    </div>
  )
}

function Hotels() {
  const { plan } = useApp()
  const rb = useRebuild()
  const world = !!plan.world
  const [selH, setSelH] = useState<Json | null>(null)
  const [open, setOpen] = useState<string | null>(null)
  if (plan.hotel?.id === 'home') return <Empty title="No hotel needed" icon={<Home className="h-7 w-7" />}>This plan is day trips from your home town, so there is nothing to book. Switch to a normal trip if you also want to stay somewhere.</Empty>
  const cands: Json[] = plan.hotel_candidates ?? []
  return (
    <div className="space-y-4">
      {rb.err && <ErrorBox msg={rb.err} />}
      <p className="text-sm text-ink/60">{world ? 'Real hotels for your dates, scored on guest rating, price vs. your budget, distance to your sights and nearby transit.' : 'Ranked by neighbourhood first, then the hotel.'} Weights: {Object.entries(plan.weights_used ?? {}).map(([k, v]) => `${k.replace('_', ' ')} ${Math.round((v as number) * 100)}%`).join(' · ')}</p>
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {cands.map((h, i) => {
          const on = h.id === plan.hotel.id
          return (
            <motion.div key={h.id} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 8) * 0.05 }} className={`card group space-y-3 !p-4 transition-shadow hover:shadow-lift ${on ? 'ring-2 ring-coral' : ''}`}>
              <div className="flex gap-3">
                {world ? <button aria-label={`Details for ${h.name}`} onClick={() => setSelH(h)} className="shrink-0"><Photo src={h.images?.[0]} name={h.name} h="h-28" className="w-32 sm:w-36" zoom /></button> : null}
                <div className="min-w-0 flex-1">
                  {on && <span className="badge mb-1 bg-coral text-white"><Check className="h-3 w-3" aria-hidden />Your stay</span>}
                  <button className="block text-left font-display text-lg font-bold leading-tight underline-offset-2 hover:underline" onClick={() => setSelH(h)}>{h.name}</button>
                  <p className="text-sm text-ink/60">{world ? `${h.type ?? 'hotel'}${h.stars ? ` · ${h.stars}-star` : ''}` : `${h.neighbourhood} · ${h.type.replace('_', ' ')} · ${h.stars}-star`}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-2"><Stars v={h.rating} n={h.reviews} /><Prov p={h.provenance} />{h.over_budget && <span className="badge bg-rose-100 text-rose-800">over hotel budget</span>}</div>
                  <p className="num mt-1 text-sm"><b>{inr(h.price_per_night)}</b>/night · {h.avg_km_to_attractions} km avg to your sights</p>
                </div>
                <div className="text-right"><p className="num font-display text-3xl font-bold leading-none text-lagoon-700">{h.score}</p><p className="text-[10px] font-bold uppercase tracking-wide text-ink/40">score</p></div>
              </div>
              {world && h.amenities?.length > 0 && <p className="text-xs text-ink/55">{h.amenities.slice(0, 5).join(' · ')}</p>}
              <div className="flex flex-wrap gap-2">
                <button className="btn btn-primary btn-sm" disabled={rb.busy || on} onClick={() => void rb.run({ hotel_id: h.id })}>{on ? 'Selected' : 'Choose'}</button>
                <button className="btn btn-ghost btn-sm" aria-expanded={open === h.id} onClick={() => setOpen(open === h.id ? null : h.id)}>Why this score?</button>
                {h.booking_url && <a className="btn btn-ghost btn-sm" href={h.booking_url} target="_blank" rel="noreferrer">View &amp; book<ExternalLink className="h-3.5 w-3.5" aria-hidden /></a>}
              </div>
              <AnimatePresence>{open === h.id && <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden"><Factors e={h.explanation} /></motion.div>}</AnimatePresence>
            </motion.div>
          )
        })}
      </div>
      {selH && <PlaceDetail item={selH} kind="hotel" busy={rb.busy} onClose={() => setSelH(null)} onChoose={selH.id === plan.hotel.id ? undefined : async () => { await rb.run({ hotel_id: selH.id }); setSelH(null) }} />}
      <p className="text-xs text-ink/50">{world ? 'Rates are for your searched dates from Google Hotels and can change. Choosing a hotel recalculates routes, meals and budget.' : 'Hotel facts and rates are demo data.'}</p>
    </div>
  )
}

function Factors({ e }: { e: Json }) {
  return (
    <div className="space-y-2.5 border-t border-ink/10 pt-3">
      {e.factors.map((f: Json) => (
        <div key={f.factor} className="text-sm">
          <div className="flex justify-between gap-2"><span className="capitalize">{f.factor.replace('_', ' ')} <span className="text-xs text-ink/40">weight {Math.round(f.weight * 100)}%</span></span><span className="num flex items-center gap-1.5"><Prov p={{ kind: f.data_kind, source: 'scoring input' }} /> {Math.round(f.subscore * 100)}</span></div>
          <div className="mt-1 h-1.5 overflow-hidden rounded bg-ink/10"><motion.div initial={{ width: 0 }} animate={{ width: `${f.subscore * 100}%` }} transition={{ duration: 0.7, ease: [0.2, 0.8, 0.2, 1] }} className="h-1.5 rounded bg-lagoon" /></div>
          <p className="mt-0.5 text-xs text-ink/50">{f.detail}</p>
        </div>
      ))}
      <p className="text-xs italic text-ink/50">{e.disclaimer}</p>
    </div>
  )
}

const WKEYS = ['attractions', 'environment', 'transit', 'hotel_quality', 'food', 'price', 'safety']
function Areas() {
  const { plan } = useApp()
  const world = !!plan.world
  const [w, setW] = useState<Record<string, number>>(() => Object.fromEntries(WKEYS.map(k => [k, plan.weights_used?.[k] ?? 0.15])))
  const [rows, setRows] = useState<Json[]>(plan.neighbourhoods ?? [])
  const [err, setErr] = useState<string | null>(null)
  const ids = (plan.attractions ?? []).map((a: Json) => a.id)
  useEffect(() => {
    if (world) return
    const t = setTimeout(() => { api('/neighbourhoods/score', { body: { weights: w, attraction_ids: ids } }).then(r => { setRows(r); setErr(null) }).catch(e => setErr(e.message)) }, 250)
    return () => clearTimeout(t)
  }, [w, world])
  if (world) {
    const c = plan.catalog
    return (
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="card space-y-3"><p className="font-display text-xl font-bold">How locations are scored here</p>
          <p className="text-sm leading-relaxed text-ink/70">For cities outside the demo dataset, Plarno.ai scores each <b>hotel's location</b> with provider data only: distance to the sights you chose, guest rating, price against your budget, and nearby transit listed by Google. Noise, crime and industrial-proximity data are <b>not available</b> for this city, so they are not scored, and nothing is guessed.</p>
          <ul className="space-y-2 text-sm">{Object.entries(plan.weights_used ?? {}).map(([k, v]) => <li key={k}><div className="flex justify-between capitalize"><span>{k.replace('_', ' ')}</span><span className="num font-semibold">{Math.round((v as number) * 100)}%</span></div><div className="mt-1 h-1.5 overflow-hidden rounded bg-ink/10"><motion.div initial={{ width: 0 }} animate={{ width: `${(v as number) * 100}%` }} transition={{ duration: 0.7 }} className="h-1.5 rounded bg-coral" /></div></li>)}</ul>
          <p className="text-xs text-ink/50">Change priorities by telling TRIP: “prioritise price”, “closer to the sights”, “better hotel”.</p></div>
        <div className="card"><p className="font-display text-xl font-bold">Data used</p>
          <ul className="mt-3 space-y-2 text-sm">{[['Attractions', c.attractions.length, c.provenance.attractions], ['Restaurants', c.restaurants.length, c.provenance.restaurants], ['Hotels with rates', c.hotels.length, c.provenance.hotels]].map(([k, n, p]) => <li key={String(k)} className="flex items-center justify-between rounded-2xl bg-sand p-3"><span>{String(k)}: <b className="num">{String(n)}</b> found</span><Prov p={p as Json} /></li>)}</ul>
          {c.notes?.length > 0 && <p className="mt-3 text-xs text-amber-700">Notes: {c.notes.join('; ')}</p>}</div>
      </div>
    )
  }
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="card h-fit space-y-3"><p className="font-display text-lg font-bold">Your priorities</p>
        {WKEYS.map(k => <label key={k} className="block text-sm capitalize">{k.replace('_', ' ')} <span className="num text-ink/40">{w[k].toFixed(2)}</span><input type="range" min={0} max={1} step={0.05} value={w[k]} onChange={e => setW({ ...w, [k]: +e.target.value })} className="w-full accent-coral" /></label>)}
      </div>
      <div className="space-y-3 lg:col-span-2">
        {err && <ErrorBox msg={err} />}
        {rows.map((r, i) => <details key={r.id ?? r.neighbourhood} className="card" open={i === 0}><summary className="flex cursor-pointer items-center justify-between"><span className="font-display text-lg font-bold">{i + 1}. {r.neighbourhood}</span><span className="num font-display text-2xl font-bold text-lagoon-700">{r.score}</span></summary><div className="mt-3"><Factors e={r} /></div></details>)}
      </div>
    </div>
  )
}

const BUDGET_ICON: Record<string, typeof Plane> = { intercity_transport: Plane, hotels: BedDouble, food: Utensils, entry_tickets: Ticket, local_transport: Car, misc: Receipt }
const BUDGET_COLOR = ['bg-coral', 'bg-lagoon', 'bg-sun', 'bg-sky', 'bg-indigo-400', 'bg-ink/40']
function BudgetTab() {
  const { tripId, plan } = useApp()
  const [b, setB] = useState<Json>(null)
  const [members, setMembers] = useState('Asha,Ravi')
  const [f, setF] = useState({ category: 'food', amount: '', paid_by: 'Asha', note: '' })
  const [err, setErr] = useState<string | null>(null)
  const load = () => api(`/trips/${tripId}/budget?members=${encodeURIComponent(members)}`).then(r => { setB(r); setErr(null) }).catch(e => setErr(e.message))
  useEffect(() => { void load() }, [plan.budget?.estimated_total_inr])
  if (!b) return err ? <ErrorBox msg={err} retry={() => void load()} /> : <Loading />
  const total = b.estimated_total_inr
  const rows = Object.entries(b.breakdown) as [string, number][]
  const pctUsed = b.max_budget_inr ? Math.min(100, (total / b.max_budget_inr) * 100) : null
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="card space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-[.1em] text-ink/50">Estimated total <Prov p={{ kind: 'estimated', source: 'budget engine', note: b.note }} /></p><p className="font-display text-5xl font-bold leading-tight"><CountUp value={total} format={v => inr(v)} /></p><p className="num text-sm text-ink/60">{inr(b.per_person_inr)} per person</p></div>
          {b.max_budget_inr && <div className="text-right text-sm"><p className="num">Budget {inr(b.max_budget_inr)}</p><p className={`num font-bold ${b.within_budget ? 'text-emerald-700' : 'text-rose-700'}`}>{b.within_budget ? `${inr(b.remaining_inr)} left` : `${inr(-b.remaining_inr)} over`}</p></div>}</div>
        {pctUsed != null && <div className="h-2.5 overflow-hidden rounded-full bg-ink/10" role="img" aria-label={`${Math.round((total / b.max_budget_inr) * 100)}% of budget used`}><motion.div initial={{ width: 0 }} animate={{ width: `${pctUsed}%` }} transition={{ duration: 0.9, ease: [0.2, 0.8, 0.2, 1] }} className={`h-full rounded-full ${b.within_budget ? 'bg-gradient-to-r from-lagoon to-emerald-400' : 'bg-gradient-to-r from-coral to-rose-600'}`} /></div>}
        {(b.alerts ?? []).map((a: string) => <p key={a} className="flex items-start gap-2 rounded-xl bg-sun-50 p-2.5 text-sm text-amber-900"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />{a}</p>)}
        <div className="flex h-3 overflow-hidden rounded-full" aria-hidden>{rows.map(([k, v], i) => <motion.div key={k} initial={{ width: 0 }} animate={{ width: `${total ? (v / total) * 100 : 0}%` }} transition={{ duration: 0.8, delay: i * 0.05 }} className={BUDGET_COLOR[i % BUDGET_COLOR.length]} title={k} />)}</div>
        <ul className="space-y-2">{rows.map(([k, v], i) => { const I = BUDGET_ICON[k] ?? Receipt; return <li key={k} className="flex items-center gap-3 text-sm"><span className={`h-2.5 w-2.5 shrink-0 rounded-full ${BUDGET_COLOR[i % BUDGET_COLOR.length]}`} aria-hidden /><I className="h-4 w-4 shrink-0 text-ink/50" aria-hidden /><span className="flex-1 capitalize">{k.replace(/_/g, ' ')}</span><span className="num text-xs text-ink/45">{total ? Math.round((v / total) * 100) : 0}%</span><span className="num w-24 text-right font-semibold">{inr(v)}</span></li> })}</ul>
        <p className="text-xs text-ink/50">{b.note} Hotel and flight prices come from the providers for your dates; meals, local transport and misc are estimates.</p>
        <div className="rounded-2xl bg-sand p-3 text-sm"><p className="mb-1 flex flex-wrap items-center gap-2 font-semibold"><Car className="h-4 w-4" aria-hidden />Cab charges by day <span className="text-xs font-normal text-ink/50">(estimate: ₹14/km, no live cab pricing)</span></p>{plan.itinerary.days.map((d: Json) => <p key={d.day} className="num flex justify-between py-0.5"><span>Day {d.day} · {d.distance_km} km</span><span>≈ {inr(d.distance_km * 14)}</span></p>)}</div>
        {plan.budget?.suggestions?.map((s: Json, i: number) => <p key={i} className="flex items-start gap-2 rounded-xl bg-lagoon-50 p-2.5 text-sm text-lagoon-700"><Lightbulb className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />{s.text}</p>)}
        <div><p className="mb-2 text-sm font-semibold">Daily estimate</p><div className="no-scrollbar flex gap-2 overflow-x-auto">{Object.entries(b.daily_inr).map(([d, v]) => <div key={d} className="num min-w-[78px] flex-1 rounded-xl bg-sand p-2 text-center text-xs">Day {d}<br /><b>{inr(v as number)}</b></div>)}</div></div>
      </div>
      <div className="card space-y-3">
        <p className="font-display text-lg font-bold">Actual spending &amp; split</p>
        <form className="grid grid-cols-2 gap-2" onSubmit={async e => { e.preventDefault(); setErr(null); try { await api(`/trips/${tripId}/expenses`, { body: { ...f, amount: parseFloat(f.amount) } }); setF({ ...f, amount: '', note: '' }); await load() } catch (x) { setErr((x as Error).message) } }}>
          <input className="input" aria-label="Category" placeholder="Category" value={f.category} onChange={e => setF({ ...f, category: e.target.value })} required />
          <input className="input" aria-label="Amount" type="number" min="1" step="any" placeholder="Amount ₹" value={f.amount} onChange={e => setF({ ...f, amount: e.target.value })} required />
          <input className="input" aria-label="Paid by" placeholder="Paid by" value={f.paid_by} onChange={e => setF({ ...f, paid_by: e.target.value })} required />
          <button className="btn btn-dark"><Plus className="h-4 w-4" aria-hidden />Add expense</button>
        </form>
        {err && <ErrorBox msg={err} />}
        <label className="block text-sm">Group members (comma separated)<input className="input mt-1" value={members} onChange={e => setMembers(e.target.value)} onBlur={() => void load()} /></label>
        <p className="num text-sm">Actual spent: <b>{inr(b.actual_spent_inr ?? 0)}</b> · vs plan {inr(b.planned_vs_actual_inr ?? 0)}</p>
        {b.expenses.length === 0 ? <p className="rounded-2xl bg-sand p-3 text-sm text-ink/55">No expenses logged yet. Add one above to track spending and split it with your group.</p> :
          <ul className="divide-y divide-ink/10 text-sm">{b.expenses.map((e: Json, i: number) => <li key={i} className="num flex justify-between py-2"><span className="capitalize">{e.category} · {e.paid_by}</span><span className="font-semibold">{inr(e.amount)}</span></li>)}</ul>}
        {b.split && <div className="rounded-2xl bg-sand p-3 text-sm"><p className="font-semibold">Settle up (equal split, {inr(b.split.share_each)} each)</p>{b.split.transfers.length ? b.split.transfers.map((t: Json, i: number) => <p key={i} className="num">{t.from} pays {t.to} {inr(t.amount)}</p>) : <p>All settled.</p>}</div>}
      </div>
    </div>
  )
}

function Safety() {
  const { plan } = useApp()
  const s = plan.safety
  if (!s) return <Empty title="No safety report" icon={<ShieldCheck className="h-7 w-7" />}>Plan a trip to see weather, air quality and emergency contacts for the destination.</Empty>
  const nr = s.neighbourhood_report ?? s.nearest_neighbourhood_report
  const env = nr?.environment ?? {}
  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
      <div className="card space-y-3"><p className="font-display text-xl font-bold">Around {nr?.neighbourhood ?? s.city}</p>
        {env.aqi ? <Row k="Air quality (AQI)" v={`${env.aqi.value} · ${env.aqi.band}`} p={env.aqi.provenance} /> : <p className="text-sm text-ink/60">Air quality: no station data available for this location.</p>}
        {env.aqi?.station && <p className="text-xs text-ink/50">Nearest monitoring station: {env.aqi.station}</p>}
        {s.weather?.available ? <Row k="Weather now" v={`${Math.round(s.weather.temp_c)}°C, ${s.weather.summary} (feels ${Math.round(s.weather.feels_like_c)}°C)`} p={s.weather.provenance} /> : <p className="text-sm text-ink/60">Weather: {s.weather?.note ?? 'not available'}</p>}
        {env.noise_db && <Row k="Noise" v={`~${env.noise_db.value} dB`} p={env.noise_db.provenance} />}
        {env.industrial_distance_km && <Row k="Industrial zone distance" v={`${env.industrial_distance_km.value} km (proxy)`} p={env.industrial_distance_km.provenance} />}
        {env.traffic_congestion_index && <Row k="Traffic congestion" v={`${Math.round(env.traffic_congestion_index.value * 100)}%`} p={env.traffic_congestion_index.provenance} />}
        {nr?.safety ? <><Row k="Safety index" v={String(nr.safety.index)} p={nr.safety.provenance} /><p className="text-xs text-ink/60">{nr.safety.limitations}</p></> : <p className="text-xs text-ink/50">Neighbourhood safety and noise data is not available for this city, so nothing is scored or implied.</p>}
        <p className="text-xs text-ink/45">These readings were taken when the plan was built. The Live guide tab shows the current ones.</p>
      </div>
      <div className="space-y-5">
        {s.advisory && <div className="card"><p className="flex flex-wrap items-center gap-2 font-display text-xl font-bold">Advisory <Prov p={s.advisory.provenance} /></p><p className="mt-2 text-sm leading-relaxed">{s.advisory.text}</p><ul className="mt-3 space-y-1.5 text-sm">{s.advisory.tips.map((t: string) => <li key={t} className="flex gap-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-lagoon" aria-hidden />{t}</li>)}</ul></div>}
        {s.emergency_contacts && <div className="card"><p className="font-display text-xl font-bold">Emergency contacts</p><ul className="mt-2 divide-y divide-ink/[.06] text-sm">{Object.entries(s.emergency_contacts).map(([k, v]) => <li key={k} className="flex justify-between gap-3 py-2"><span>{k}</span><span className="num font-bold text-lagoon-700">{String(v)}</span></li>)}</ul>
          {s.emergency_note && <p className="mt-2 text-xs text-ink/50">{s.emergency_note}</p>}<p className="mt-2 text-xs text-ink/50">{s.disclaimer}</p></div>}
      </div>
    </div>
  )
}
const Row = ({ k, v, p }: { k: string; v: string; p: Json }) => <div className="flex items-center justify-between gap-3 text-sm"><span className="text-ink/60">{k}</span><span className="num flex flex-wrap items-center justify-end gap-1.5 text-right font-medium">{v} <Prov p={p} /></span></div>

function Bookings() {
  const { tripId, plan } = useApp()
  const [items, setItems] = useState<Json[]>([])
  const [approval, setApproval] = useState<Json>(null)
  const [cancel, setCancel] = useState<Json>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const world = !!plan.world
  const load = () => api('/bookings').then(r => setItems(r.filter((b: Json) => b.trip_id === tripId))).catch(e => setErr(e.message))
  useEffect(() => { void load() }, [tripId])
  const act = async (fn: () => Promise<void>) => { setBusy(true); setErr(null); try { await fn() } catch (e) { setErr((e as Error).message) } finally { setBusy(false) } }
  if (world) {
    const links: Json[] = plan.booking_links ?? []
    return (
      <div className="space-y-4">
        <div className="flex items-start gap-3 rounded-2xl border border-sky-200 bg-sky-50 p-4 text-sm text-sky-900"><Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden /><p><b>Booking happens on the provider's website.</b> Plarno.ai uses search-only data sources, so it never creates reservations or confirmation numbers on your behalf. Use the links below to continue with your chosen hotel and flight. Prices can change before you pay.</p></div>
        {links.length === 0 && <Empty title="No booking links yet" icon={<Ticket className="h-7 w-7" />}>Pick a hotel (and add where you are travelling from) to get booking links.</Empty>}
        <div className="grid gap-4 md:grid-cols-2">{links.map((l, i) => <motion.a key={i} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }} href={l.url} target="_blank" rel="noreferrer" className="card card-hover flex items-center justify-between gap-3"><span className="flex min-w-0 items-center gap-3"><span className="icon-tile bg-sand-200" aria-hidden>{l.kind === 'flight' ? <Plane className="h-5 w-5" /> : <BedDouble className="h-5 w-5" />}</span><b className="min-w-0">{l.label}</b></span><span className="btn btn-primary btn-sm shrink-0">Book<ArrowUpRight className="h-3.5 w-3.5" aria-hidden /></span></motion.a>)}</div>
      </div>
    )
  }
  return (
    <div className="space-y-5">
      <div className="flex items-start gap-3 rounded-2xl border border-violet-200 bg-violet-50 p-4 text-sm text-violet-900"><Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden /><p>The Delhi demo booking service is a <b>simulation</b>. Approving creates a clearly labelled SIM- record. No real reservation or payment is made and no card details are collected.</p></div>
      {err && <ErrorBox msg={err} />}{msg && <p className="rounded-xl bg-lagoon-50 p-3 text-sm text-lagoon-700" role="status">{msg}</p>}
      {!approval && <div className="card"><p className="font-display text-xl font-bold">Prepared items ({plan.bookable_items?.length ?? 0})</p>
        {(plan.bookable_items ?? []).map((i: Json, k: number) => <div key={k} className="num mt-2 flex justify-between gap-3 text-sm"><span className="capitalize">{i.category}: {i.item}</span><span className="font-semibold">{inr(i.amount_inr)}</span></div>)}
        <button className="btn btn-primary mt-4" disabled={busy || !plan.bookable_items?.length} onClick={() => void act(async () => { setMsg(null); setApproval(await api(`/trips/${tripId}/booking/prepare`, { body: {} })) })}>Review for approval</button></div>}
      {approval && <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="card space-y-3 !border-2 !border-amber-300"><p className="font-display text-xl font-bold">Review before approving</p>
        {approval.payload.items.map((i: Json, k: number) => <div key={k} className="rounded-2xl bg-sand p-3 text-sm"><p className="font-semibold">{i.category}: {i.item} <span className="badge bg-violet-100 text-violet-800">simulated</span></p>
          <p>Supplier: {i.supplier} · Travellers: {i.travellers} · Dates: {Array.isArray(i.travel_dates) ? i.travel_dates.join(' → ') : '—'}</p><p>Amount: <b>{inr(i.amount_inr)}</b> · Extras: {i.additional_charges}</p><p>Cancellation: {i.cancellation_policy}</p><p className="text-xs text-ink/60">{i.terms}</p></div>)}
        <p className="text-sm">Total payable (simulated): <b>{inr(approval.payload.total_inr)}</b></p>
        <div className="flex flex-wrap gap-2"><button className="btn btn-dark" disabled={busy} onClick={() => void act(async () => { const r = await api(`/approvals/${approval.approval_id}/decide`, { body: { approve: true, idempotency_key: 'appr-' + approval.approval_id + '-' + crypto.randomUUID() } }); setMsg(r.notice); setApproval(null); await load() })}>Approve (simulated)</button>
          <button className="btn btn-ghost" disabled={busy} onClick={() => void act(async () => { await api(`/approvals/${approval.approval_id}/decide`, { body: { approve: false, idempotency_key: 'rej-' + crypto.randomUUID() } }); setApproval(null); setMsg('Rejected. Nothing was booked.') })}>Reject</button></div></motion.div>}
      <div className="card"><p className="font-display text-xl font-bold">Confirmations &amp; vouchers</p>
        {items.length === 0 ? <p className="mt-2 text-sm text-ink/50">No bookings for this trip yet.</p> : items.map(b => (
          <div key={b.id} className="mt-3 rounded-2xl bg-sand p-3 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div><p className="font-semibold">{b.item} <span className="badge bg-violet-100 text-violet-800">simulated</span></p><p className="num text-xs text-ink/60">{b.reference} · {b.status} · {inr(b.amount)}</p><p className="text-xs text-ink/50">{b.cancellation_policy}</p></div>
              {b.status !== 'SIMULATED_CANCELLED' && cancel?.booking !== b.id && <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => void act(async () => { const ap = await api(`/bookings/${b.id}/cancel-request`, { body: {} }); setCancel({ ...ap, booking: b.id }) })}>Request cancellation</button>}
            </div>
            {cancel?.booking === b.id && <div className="mt-3 rounded-xl border border-amber-300 bg-amber-50 p-3"><p>{cancel.notice}</p><div className="mt-2 flex flex-wrap gap-2">
              <button className="btn btn-dark btn-sm" disabled={busy} onClick={() => void act(async () => { await api(`/approvals/${cancel.approval_id}/decide`, { body: { approve: true, idempotency_key: 'cx-' + crypto.randomUUID() } }); setCancel(null); setMsg('Booking cancelled (simulated).'); await load() })}>Confirm cancellation</button>
              <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => void act(async () => { await api(`/approvals/${cancel.approval_id}/decide`, { body: { approve: false, idempotency_key: 'cxn-' + crypto.randomUUID() } }); setCancel(null) })}>Keep booking</button></div></div>}
          </div>))}
      </div>
    </div>
  )
}

function Agents() {
  const { workflow } = useApp()
  if (!workflow.length) return <Empty title="No workflow this session" icon={<Bot className="h-7 w-7" />}>Send TRIP a request and this tab shows which specialist agents ran, in order, with timings.</Empty>
  return (
    <div className="card"><p className="mb-4 font-display text-xl font-bold">Last agent workflow</p>
      <ol className="relative space-y-2 before:absolute before:bottom-5 before:left-[1.2rem] before:top-5 before:w-px before:bg-ink/10">{workflow.map((s, i) => (
        <motion.li key={i} initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }} className="relative flex items-start gap-3 rounded-2xl p-2 text-sm">
          <span className={`relative z-10 grid h-7 w-7 shrink-0 place-items-center rounded-full text-white ${s.state === 'succeeded' ? 'bg-lagoon' : 'bg-rose-500'}`} aria-hidden>{s.state === 'succeeded' ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}</span>
          <div className="min-w-0 flex-1"><p className="font-semibold capitalize">{s.agent.replace(/_/g, ' ')}</p><p className="text-xs text-ink/60">{s.error ?? s.summary}</p></div>
          <div className="shrink-0 text-right text-xs"><span className={`badge ${s.state === 'succeeded' ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}`}>{s.state}</span><p className="num mt-1 text-ink/50">{s.duration_ms} ms · {s.attempts} try</p></div>
        </motion.li>))}</ol>
    </div>
  )
}

function TravelTab() {
  const { tripId, plan, context, setPlan } = useApp()
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  if (context.stay_home) return <Empty title="Day trips from home" icon={<Home className="h-7 w-7" />}>No long-distance travel is needed. Each outing's local cab fare (about ₹14/km, an estimate) is shown in the itinerary and the Budget tab.</Empty>
  let data: Json | null = plan.route_options ?? null
  if (!data && plan.journey_options) data = { options: plan.journey_options.map((o: Json, i: number) => ({ ...o, index: i, round_trip_inr: o.total_fare_inr * 2 })), notes: ['These options come from the India demo network (simulated).'] }
  if (!data || !(data.options ?? []).length) return <Empty title="No travel options yet" icon={<Compass className="h-7 w-7" />}>{plan.journey_note ?? 'Add where you are travelling from (any town or city) and Plarno will compare flights, cabs, buses and trains door to door.'}</Empty>
  const canChoose = !!plan.route_options
  const choose = async (index: number) => {
    setBusy(true); setErr(null); setMsg(null)
    try { const r = await api(`/trips/${tripId}/journey`, { body: { index } }); setPlan(r.plan); setMsg(`Updated. Estimated total is now ${inr(r.plan.budget.estimated_total_inr)}${r.plan.budget.within_budget ? ' (within budget)' : ' (over budget: see Budget tab)'}.`) }
    catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <div className="space-y-4">
      <div className="card flex flex-wrap items-center justify-between gap-3 !p-5">
        <div><p className="font-display text-xl font-bold">{context.origin} → {context.destination}</p><p className="text-sm text-ink/60">All the sensible ways to get there, door to door. {canChoose ? 'Pick one and your budget updates.' : 'To switch, tell TRIP which one you prefer.'}</p></div>
        {plan.budget && <div className="text-right text-sm"><p className="text-[11px] font-bold uppercase tracking-[.1em] text-ink/50">Trip estimate</p><p className="num font-display text-2xl font-bold">{inr(plan.budget.estimated_total_inr)}</p>{plan.budget.max_budget_inr && <p className={`num ${plan.budget.within_budget ? 'text-emerald-700' : 'text-rose-700'}`}>{plan.budget.within_budget ? `${inr(plan.budget.remaining_inr)} left of ${inr(plan.budget.max_budget_inr)}` : `${inr(-plan.budget.remaining_inr)} over ${inr(plan.budget.max_budget_inr)}`}</p>}</div>}
      </div>
      {err && <ErrorBox msg={err} />}{msg && <p className="rounded-2xl bg-lagoon-50 p-3 text-sm text-lagoon-700" role="status">{msg}</p>}
      <RouteOptions data={data} chosenIndex={plan.journey?.index ?? null} onChoose={canChoose ? choose : undefined} busy={busy} />
    </div>
  )
}
