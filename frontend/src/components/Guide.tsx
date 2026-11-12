import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlarmClock, ArrowRight, BedDouble, CalendarDays, Check, CheckCircle2, CloudRain, MapPin, Plane, Plus, RefreshCw, Route, Snowflake, Sparkles, ThermometerSun, Utensils, Wallet, Wind } from './icons'
import { api, inr, mins, Json } from '../api'
import { useApp } from '../store'
import { useRebuild } from '../hooks'
import { ErrorBox, MapView, Photo, Pin, Prov, Reveal, Stars } from './ui'
import { LivePanel, WeatherIcon } from './Live'
import PlaceDetail from './PlaceDetail'

const TIP_ICON: Record<string, typeof Wallet> = { wallet: Wallet, rain: CloudRain, heat: ThermometerSun, cold: Snowflake, air: Wind, clock: AlarmClock, route: Route, calendar: CalendarDays, plane: Plane, bed: BedDouble, check: CheckCircle2 }
const TIP_STYLE: Record<string, string> = { warn: 'bg-amber-100 text-amber-700', info: 'bg-sky-100 text-sky-700', good: 'bg-emerald-100 text-emerald-700' }
const REFRESH_MS = 5 * 60 * 1000

/** Reveals text word by word, like TRIP is saying it. */
function Typed({ text }: { text: string }) {
  const words = useMemo(() => text.split(' '), [text])
  const [n, setN] = useState(0)
  useEffect(() => {
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) { setN(words.length); return }
    setN(0)
    const iv = window.setInterval(() => setN(x => { if (x >= words.length) { window.clearInterval(iv); return x } return x + 1 }), 34)
    return () => window.clearInterval(iv)
  }, [words])
  return <span aria-label={text}><span aria-hidden>{words.slice(0, n).join(' ')}</span>{n < words.length && <span className="ml-0.5 inline-block h-4 w-[2px] translate-y-0.5 animate-pulse bg-white/70" aria-hidden />}</span>
}

/** The live guide: what is happening at the destination right now, what that means for this plan, and what is worth adding. */
export default function Guide({ goTab }: { goTab: (tab: string) => void }) {
  const { tripId, plan, context, send, busy: chatBusy } = useApp()
  const rb = useRebuild()
  const [g, setG] = useState<Json | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [at, setAt] = useState<Date | null>(null)
  const [active, setActive] = useState<string | null>(null)
  const [sel, setSel] = useState<{ item: Json; kind: 'attraction' | 'restaurant'; addable: boolean } | null>(null)
  const [added, setAdded] = useState<string[]>([])
  const days: Json[] = plan.itinerary.days
  const todayIso = new Date().toISOString().slice(0, 10)
  const [day, setDay] = useState(() => Math.max(0, days.findIndex(d => d.date === todayIso)))
  const seq = useRef(0)
  const ids: string[] = context.selected_attraction_ids ?? []

  const load = useCallback(async (quiet = false) => {
    if (!tripId) return
    const mine = ++seq.current
    if (!quiet) setLoading(true)
    try { const r = await api(`/trips/${tripId}/guide`); if (mine === seq.current) { setG(r); setErr(null); setAt(new Date()) } }
    catch (e) { if (mine === seq.current && !quiet) setErr((e as Error).message) }
    finally { if (mine === seq.current) setLoading(false) }
  }, [tripId])
  // refetch when the plan itself changes (hotel, stops, budget), and keep the live readings fresh while the tab stays open
  const planKey = `${plan.hotel?.id}|${ids.join(',')}|${plan.budget?.estimated_total_inr}|${context.pace}`
  useEffect(() => { void load(!!g) }, [planKey, load])
  useEffect(() => { const iv = window.setInterval(() => { if (!document.hidden) void load(true) }, REFRESH_MS); return () => window.clearInterval(iv) }, [load])

  const d = days[Math.min(day, days.length - 1)]
  const hotel = plan.itinerary.hotel
  const stops: Json[] = d.stops
  const sights = stops.filter(s => s.type === 'attraction')
  const pins: Pin[] = useMemo(() => [
    ...(hotel ? [{ id: 'hotel', lat: hotel.lat, lon: hotel.lon, label: (plan.hotel?.id === 'home' ? 'Home: ' : 'Your stay: ') + hotel.name, color: '#0b1f33', kind: 'hotel' }] : []),
    ...stops.map((s, i) => ({ id: `s${i}`, lat: s.lat, lon: s.lon, label: `${s.start} · ${s.name}`, color: s.type === 'meal' ? '#f6b73c' : '#f4553f', kind: s.type === 'meal' ? 'meal' : undefined, n: s.type === 'meal' ? undefined : sights.indexOf(s) + 1 })),
  ], [d, hotel])
  const [road, setRoad] = useState<Json | null>(null)
  useEffect(() => {
    setRoad(null); setActive(null)
    if (!hotel || sights.length === 0) return
    let dead = false
    api('/route/directions', { body: { points: [[hotel.lat, hotel.lon], ...sights.map(s => [s.lat, s.lon]), [hotel.lat, hotel.lon]], profile: 'driving' } }).then(r => { if (!dead) setRoad(r) }).catch(() => {})
    return () => { dead = true }
  }, [day, plan.itinerary])
  const line = road?.geometry?.length ? [road.geometry] : d.route_geometry?.length ? [d.route_geometry] : undefined
  const wxDay = g?.day_weather?.[String(d.day)]

  const act = (t: Json) => { if (t.ask) void send(t.ask); else if (t.tab) goTab(t.tab) }
  const addPlace = async (p: Json) => { if (await rb.run({ attraction_ids: [...ids, p.id] })) setAdded(a => [...a, p.id]) }
  const openRec = (p: Json, kind: 'attraction' | 'restaurant') => {
    const pool: Json[] = (kind === 'attraction' ? plan.catalog?.attractions : plan.catalog?.restaurants) ?? []
    setSel({ item: pool.find(x => x.id === p.id) ?? p, kind, addable: kind === 'attraction' })
  }
  const recs = g?.recommendations

  return (
    <div className="space-y-6">
      {err && <ErrorBox msg={err} retry={() => void load()} />}
      {rb.err && <ErrorBox msg={rb.err} />}

      {/* AI briefing */}
      <motion.section initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="relative overflow-hidden rounded-[2rem] bg-ink-900 p-6 text-white md:p-8" aria-label="TRIP's briefing">
        <div className="pointer-events-none absolute -right-16 -top-20 h-64 w-64 animate-aurora rounded-full bg-coral/30 blur-[90px]" aria-hidden />
        <div className="pointer-events-none absolute -bottom-24 left-10 h-56 w-56 animate-aurora rounded-full bg-lagoon/25 blur-[90px] [animation-delay:-6s]" aria-hidden />
        <div className="relative flex flex-wrap items-center justify-between gap-3">
          <p className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-[.16em] text-white/60"><span className="grid h-7 w-7 place-items-center rounded-lg bg-gradient-to-br from-coral to-sun text-white"><Sparkles className="h-3.5 w-3.5" aria-hidden /></span>TRIP's briefing</p>
          <div className="flex items-center gap-2 text-xs text-white/50">
            {at && <span className="num" title="Live readings refresh every 5 minutes while this tab is open">Updated {at.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>}
            <button onClick={() => void load()} disabled={loading} className="grid h-9 w-9 place-items-center rounded-full bg-white/10 transition hover:bg-white/20 disabled:opacity-50" aria-label="Refresh live guide"><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} aria-hidden /></button>
          </div>
        </div>
        <div className="relative mt-4 min-h-[4.5rem] max-w-4xl text-lg leading-relaxed text-white/90 md:text-xl">
          {!g ? <div className="space-y-2" role="status" aria-label="Preparing briefing"><div className="h-4 w-11/12 animate-pulse rounded bg-white/15" /><div className="h-4 w-9/12 animate-pulse rounded bg-white/15" /><div className="h-4 w-7/12 animate-pulse rounded bg-white/15" /></div>
            : g.briefing ? <Typed text={g.briefing.text} />
              : <span>{g.tips.filter((t: Json) => t.level === 'warn').length ? `I found ${g.tips.filter((t: Json) => t.level === 'warn').length} thing${g.tips.filter((t: Json) => t.level === 'warn').length === 1 ? '' : 's'} worth a look before you go. They are listed below with a fix for each.` : 'Your plan looks good against the live weather, opening hours and your budget. Recommendations are below if you want to add more.'}</span>}
        </div>
        <div className="relative mt-5 flex flex-wrap items-center gap-2">
          {g?.briefing && <Prov p={g.briefing.provenance} label="AI summary of live data" />}
          {['What should I pack?', 'Make it cheaper', 'Add more sightseeing'].map(q => <button key={q} disabled={chatBusy} onClick={() => void send(q)} className="btn btn-glass btn-sm">{q}</button>)}
        </div>
      </motion.section>

      {/* live conditions */}
      <section aria-label="Live conditions">
        <div className="mb-3 flex items-end justify-between gap-3"><h2 className="font-display text-2xl font-bold">Right now in {context.destination}</h2></div>
        <LivePanel live={g?.live ?? null} place={context.destination} highlight={days.map(x => x.date)} />
      </section>

      {/* today's route + tips */}
      <div className="grid gap-6 lg:grid-cols-[1.35fr_1fr]">
        <section className="card !p-4" aria-label="Day route">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <h2 className="mr-auto font-display text-xl font-bold">Day {d.day} on the map</h2>
            {wxDay && <span className="badge bg-sky-50 text-sky-800" title={`Forecast for ${wxDay.date}`}><WeatherIcon text={wxDay.summary} className="h-3.5 w-3.5" />{wxDay.max_c}° / {wxDay.min_c}° · {Math.round(wxDay.pop * 100)}% rain</span>}
          </div>
          <div className="no-scrollbar mb-3 flex gap-1.5 overflow-x-auto" role="group" aria-label="Choose a day">
            {days.map((x, i) => <button key={i} onClick={() => setDay(i)} aria-pressed={i === day} className={`chip !min-h-[34px] whitespace-nowrap ${i === day ? 'chip-on' : ''}`}>Day {x.day}{x.date === todayIso ? ' · today' : ''}</button>)}
          </div>
          <MapView pins={pins} route={line} height={340} activeId={active} onPinClick={setActive} traveller />
          <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink/55">
            {road ? <><Prov p={road.provenance} /><span className="num">{road.distance_km} km · about {mins(road.duration_min)} of driving</span></> : <span>Loading the road route…</span>}
            <button className="link ml-auto py-1" onClick={() => goTab('map')}>Open full map</button>
          </p>
          <ol className="mt-3 space-y-1.5">
            {stops.length === 0 && <li className="rounded-2xl bg-sand p-3 text-sm text-ink/60">A free day. Ask TRIP to add more sightseeing.</li>}
            {stops.map((s, i) => (
              <li key={i}><button onMouseEnter={() => setActive(`s${i}`)} onFocus={() => setActive(`s${i}`)} onClick={() => setActive(`s${i}`)}
                className={`flex w-full items-center gap-3 rounded-2xl p-2.5 text-left text-sm transition ${active === `s${i}` ? 'bg-coral-50 ring-1 ring-coral/30' : 'bg-sand hover:bg-sand-200'}`}>
                <span className={`num grid h-8 w-8 shrink-0 place-items-center rounded-full text-xs font-bold text-white ${s.type === 'meal' ? 'bg-sun' : 'bg-coral'}`}>{s.type === 'meal' ? <Utensils className="h-3.5 w-3.5" aria-hidden /> : sights.indexOf(s) + 1}</span>
                <span className="min-w-0 flex-1"><span className="block truncate font-semibold">{s.name}</span><span className="num block truncate text-xs text-ink/55">{s.start}{s.end ? `–${s.end}` : ''}{s.type === 'meal' ? ` · ${s.meal}` : ` · ${s.travel_km} km hop`}</span></span>
                {s.hours_flag === 'closed' && <span className="badge bg-rose-100 text-rose-800">closed</span>}
              </button></li>
            ))}
          </ol>
        </section>

        <section aria-label="Smart tips">
          <h2 className="mb-3 font-display text-xl font-bold">What TRIP noticed</h2>
          {!g ? <div className="space-y-3" role="status" aria-label="Loading tips">{[0, 1, 2].map(i => <div key={i} className="skeleton h-24" />)}</div> : (
            <ul className="space-y-3">
              <AnimatePresence initial={false}>
                {g.tips.map((t: Json, i: number) => {
                  const Icon = TIP_ICON[t.icon] ?? Sparkles
                  return (
                    <motion.li key={t.title} layout initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ delay: i * 0.05 }} className="card !p-4">
                      <div className="flex gap-3">
                        <span className={`icon-tile !h-10 !w-10 !rounded-xl ${TIP_STYLE[t.level]}`}><Icon className="h-5 w-5" aria-hidden /></span>
                        <div className="min-w-0 flex-1"><p className="font-semibold leading-snug">{t.title}</p><p className="mt-0.5 text-sm leading-relaxed text-ink/65">{t.text}</p>
                          {t.label && (t.ask || t.tab) && <button onClick={() => act(t)} disabled={!!t.ask && chatBusy} className="mt-2 inline-flex min-h-[36px] items-center gap-1 text-sm font-semibold text-coral-600 transition hover:gap-2 disabled:opacity-50">{t.label}<ArrowRight className="h-3.5 w-3.5" aria-hidden /></button>}
                        </div>
                      </div>
                    </motion.li>
                  )
                })}
              </AnimatePresence>
            </ul>
          )}
          <p className="mt-3 text-xs leading-relaxed text-ink/45">Tips are worked out from the forecast, air-quality readings, opening hours and your budget. They are checks, not guarantees.</p>
        </section>
      </div>

      {/* recommendations */}
      {recs?.places?.length > 0 && (
        <section aria-label="Recommended places">
          <Reveal><div className="mb-3"><h2 className="font-display text-2xl font-bold">Recommended for you</h2><p className="text-sm text-ink/60">Not in your plan yet. Ranked by rating, popularity, your interests and distance from {plan.hotel?.id === 'home' ? 'home' : 'your stay'}.</p></div></Reveal>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {recs.places.map((p: Json, i: number) => {
              const done = added.includes(p.id) || ids.includes(p.id)
              return (
                <Reveal key={p.id} delay={(i % 3) * 0.06}>
                  <article className="card card-hover group flex h-full min-w-0 flex-col !p-3">
                    <button onClick={() => openRec(p, 'attraction')} aria-label={`Details for ${p.name}`} className="block w-full text-left">
                      <Photo src={p.thumbnail} name={p.name} h="h-40" zoom>{p.match && <span className="badge absolute left-2 top-2 bg-white/95 text-coral-700 shadow-soft"><Sparkles className="h-3 w-3" aria-hidden />Matches your interests</span>}{p.demo && <span className="absolute right-2 top-2"><Prov p="Demo dataset entry: location approximate, details not verified" label="demo data" /></span>}</Photo>
                    </button>
                    <div className="flex flex-1 flex-col px-1 pt-3">
                      <h3 className="font-display text-lg font-bold leading-tight">{p.name}</h3>
                      <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink/55"><Stars v={p.rating} n={p.reviews} /><span className="flex items-center gap-1"><MapPin className="h-3 w-3" aria-hidden />{p.distance_km} km</span>{p.visit_min && <span>~{p.visit_min} min</span>}</div>
                      <ul className="mt-2 flex flex-wrap gap-1.5">{p.why.slice(1).map((w: string) => <li key={w} className="rounded-full bg-sand px-2.5 py-1 text-[11px] font-medium text-ink/70">{w}</li>)}</ul>
                      <div className="mt-auto flex items-center gap-2 pt-3">
                        <button className={`btn btn-sm ${done ? 'bg-emerald-100 text-emerald-800' : 'btn-primary'}`} disabled={rb.busy || done} onClick={() => void addPlace(p)}>{done ? <><Check className="h-3.5 w-3.5" aria-hidden />Added</> : <><Plus className="h-3.5 w-3.5" aria-hidden />Add to trip</>}</button>
                        <button className="btn btn-ghost btn-sm" onClick={() => openRec(p, 'attraction')}>Details</button>
                      </div>
                    </div>
                  </article>
                </Reveal>
              )
            })}
          </div>
        </section>
      )}

      {recs?.food?.length > 0 && (
        <section aria-label="Recommended restaurants">
          <Reveal><div className="mb-3"><h2 className="font-display text-2xl font-bold">Good food near {plan.hotel?.id === 'home' ? 'home' : 'your stay'}</h2><p className="text-sm text-ink/60">Well-rated places close by that are not already in your meal plan.</p></div></Reveal>
          <div className="no-scrollbar -mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-2">
            {recs.food.map((r: Json) => (
              <button key={r.id} onClick={() => openRec(r, 'restaurant')} aria-label={`Details for ${r.name}`} className="card card-hover group w-64 shrink-0 snap-start !p-3 text-left">
                <Photo src={r.thumbnail} name={r.name} h="h-32" zoom>{r.demo && <span className="absolute right-2 top-2"><Prov p="Demo venue: a fictional name modelled on local cuisine, not a real listing" label="demo venue" /></span>}</Photo>
                <p className="mt-2 truncate font-display text-base font-bold">{r.name}</p>
                <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-ink/55"><Stars v={r.rating} n={r.reviews} /><span>{r.distance_km} km</span>{r.price_for_two ? <span>{inr(r.price_for_two)} for two</span> : r.price_level ? <span>{r.price_level}</span> : null}</div>
                <p className="mt-1 truncate text-xs text-ink/45">{r.types?.[0] ?? r.category}</p>
              </button>
            ))}
          </div>
        </section>
      )}
      {g && !recs?.places?.length && !recs?.food?.length && <p className="rounded-2xl bg-sand-200 p-4 text-sm text-ink/60">No extra recommendations: everything well-rated nearby is already in your plan.</p>}

      {sel && <PlaceDetail item={sel.item} kind={sel.kind} onClose={() => setSel(null)} busy={rb.busy}
        onAdd={sel.addable && !ids.includes(sel.item.id) ? async () => { await addPlace(sel.item); setSel(null) } : undefined} />}
    </div>
  )
}
