import { useState } from 'react'
import { motion } from 'framer-motion'
import { ArrowLeftRight, ArrowRight, Bus, CalendarDays, Car, Plane, Search, TrainFront, Users } from '../components/icons'
import { api, Json } from '../api'
import { Empty, ErrorBox, PageHead, Segmented } from '../components/ui'
import PlaceInput, { PlaceSuggestion } from '../components/PlaceInput'
import RouteOptions from '../components/RouteOptions'

const tomorrow = (n: number) => new Date(Date.now() + n * 864e5).toISOString().slice(0, 10)
const EXAMPLES: [string, string][] = [['Mumbai', 'Goa'], ['Delhi', 'Jaipur'], ['Bengaluru', 'Singapore'], ['Kolkata', 'Bangkok']]
type Pt = { lat: number; lon: number } | null
type Form = { origin: string; destination: string; date: string; travellers: number; budget: string; trip: 'one_way' | 'round_trip' }
const prettyDate = (d: string) => { const x = new Date(d + 'T00:00:00'); return isNaN(+x) ? d : x.toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' }) }

export default function Transport() {
  const [f, setF] = useState<Form>({ origin: '', destination: '', date: tomorrow(21), travellers: 2, budget: '', trip: 'one_way' })
  // exact coordinates of a place picked from the suggestions (or "my location"): the route starts from that very point. Typing again clears them.
  const [oPt, setOPt] = useState<Pt>(null)
  const [dPt, setDPt] = useState<Pt>(null)
  const [res, setRes] = useState<Json | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const pt = (s: PlaceSuggestion): Pt => (s.lat != null && s.lon != null ? { lat: s.lat, lon: s.lon } : null)

  async function search(v = f, o = oPt, d = dPt) {
    if (v.origin.trim().length < 2 || v.destination.trim().length < 2) { setErr('Enter both where you are starting from and where you are going.'); return }
    if (v.origin.trim().toLowerCase() === v.destination.trim().toLowerCase()) { setErr('The start and the destination are the same place.'); return }
    if (v.budget && !(Number(v.budget) > 0)) { setErr('The budget must be more than zero, or leave it empty.'); return }
    setBusy(true); setErr(null); setRes(null)
    const q = new URLSearchParams({ origin: v.origin, destination: v.destination, date: v.date, travellers: String(v.travellers), trip: v.trip, ...(v.budget ? { budget: v.budget } : {}),
      ...(o ? { origin_lat: String(o.lat), origin_lon: String(o.lon) } : {}), ...(d ? { dest_lat: String(d.lat), dest_lon: String(d.lon) } : {}) })
    try { setRes(await api(`/routes/options?${q}`)) } catch (x) { setErr((x as Error).message) } finally { setBusy(false) }
  }
  const swap = () => { setF(s => ({ ...s, origin: s.destination, destination: s.origin })); setOPt(dPt); setDPt(oPt) }
  const fromName = res ? res.origin.spot ?? res.origin.name : ''
  const toName = res ? res.destination.spot ?? res.destination.name : ''

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 md:py-10">
      <PageHead eyebrow="Ways to travel" title="Door to door, every sensible way" sub="From any town, college, station or your own location to anywhere. You get real train routes between actual stations, buses, cabs and live flight fares, each with a map and links to check timings and book." />
      <form onSubmit={e => { e.preventDefault(); void search() }} noValidate className="card grid gap-4 !p-4 sm:grid-cols-6 sm:!p-6">
        <div className="grid gap-3 sm:col-span-6 sm:grid-cols-[1fr_auto_1fr] sm:items-start">
          <PlaceInput id="tr-from" label="From" locate placeholder="Town, college, station, or use your location" value={f.origin} onChange={v => { setF(s => ({ ...s, origin: v })); setOPt(null) }} onPick={s => setOPt(pt(s))} />
          <button type="button" aria-label="Swap from and to" title="Swap" onClick={swap} className="mx-auto grid h-[42px] w-[42px] place-items-center rounded-full border border-ink/10 bg-white text-ink/60 shadow-soft transition duration-300 hover:rotate-180 hover:border-coral hover:text-coral sm:mt-[1.6rem]"><ArrowLeftRight className="h-4 w-4 rotate-90 sm:rotate-0" /></button>
          <PlaceInput id="tr-to" label="To" placeholder="Where to? Town, college, airport…" value={f.destination} onChange={v => { setF(s => ({ ...s, destination: v })); setDPt(null) }} onPick={s => setDPt(pt(s))} />
        </div>
        <div className="sm:col-span-2"><label className="label" htmlFor="tr-date">Date</label><input id="tr-date" type="date" className="input num" min={tomorrow(0)} value={f.date} onChange={e => setF({ ...f, date: e.target.value })} required /></div>
        <div className="grid grid-cols-2 gap-4 sm:col-span-4 sm:grid-cols-[110px_1fr]">
          <div><label className="label" htmlFor="tr-n">Travellers</label><input id="tr-n" type="number" inputMode="numeric" min={1} max={20} className="input num" value={f.travellers} onChange={e => setF({ ...f, travellers: Math.max(1, Math.min(20, +e.target.value || 1)) })} /></div>
          <div><label className="label" htmlFor="tr-b">Travel budget ₹ <span className="font-medium normal-case tracking-normal text-ink/40">(optional)</span></label><input id="tr-b" type="number" inputMode="numeric" min={1} step={100} className="input num" placeholder="e.g. 5000" value={f.budget} onChange={e => setF({ ...f, budget: e.target.value })} aria-describedby="tr-b-help" /></div>
        </div>
        <div className="flex flex-col gap-3 sm:col-span-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-3">
            <Segmented id="trip" label="Trip type" value={f.trip} onChange={t => setF({ ...f, trip: t })} options={[['one_way', 'One way'], ['round_trip', 'Round trip']]} />
            <p id="tr-b-help" className="text-xs text-ink/50">The budget is for this journey, {f.trip === 'round_trip' ? 'there and back' : 'one way'}, for everyone travelling.</p>
          </div>
          <button className="btn btn-primary w-full !px-7 !py-3 sm:w-auto" disabled={busy}><Search className="h-4 w-4" aria-hidden />{busy ? 'Searching…' : 'Compare'}</button>
        </div>
      </form>
      {err && <div className="mt-4"><ErrorBox msg={err} /></div>}

      {busy && (
        <div className="mt-6 space-y-3" role="status" aria-label="Searching">
          <p className="flex items-center gap-3 text-sm text-ink/60"><motion.span animate={{ x: [0, 14, 0] }} transition={{ duration: 1.4, repeat: Infinity }} className="text-coral"><Plane className="h-4 w-4" aria-hidden /></motion.span>Finding the nearest stations and airports, road distances and live flight fares…</p>
          {[0, 1, 2].map(i => <div key={i} className="skeleton h-36" />)}
        </div>
      )}

      {!res && !busy && !err && (
        <div className="mt-8">
          <Empty title="Compare every way to get there" icon={<div className="flex gap-1"><Plane className="h-5 w-5" /><TrainFront className="h-5 w-5" /></div>}>
            <p>Not sure where to start? Try one of these.</p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">{EXAMPLES.map(([a, b]) => <button key={a + b} className="chip" onClick={() => { const v = { ...f, origin: a, destination: b }; setF(v); setOPt(null); setDPt(null); void search(v, null, null) }}>{a}<ArrowRight className="h-3.5 w-3.5" aria-hidden />{b}</button>)}</div>
            <p className="mt-5 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-ink/45"><span className="flex items-center gap-1.5"><Plane className="h-3.5 w-3.5" aria-hidden />Live flight fares</span><span className="flex items-center gap-1.5"><TrainFront className="h-3.5 w-3.5" aria-hidden />Trains between real stations</span><span className="flex items-center gap-1.5"><Bus className="h-3.5 w-3.5" aria-hidden />Bus estimates</span><span className="flex items-center gap-1.5"><Car className="h-3.5 w-3.5" aria-hidden />Cab estimates</span></p>
          </Empty>
        </div>
      )}

      {res && (
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="mt-8 space-y-4">
          <div>
            <h2 className="flex flex-wrap items-center gap-x-3 gap-y-1 font-display text-2xl font-bold sm:text-3xl"><span className="min-w-0 break-words">{fromName}</span><ArrowRight className="h-5 w-5 shrink-0 text-coral sm:h-6 sm:w-6" aria-label="to" /><span className="min-w-0 break-words">{toName}</span></h2>
            {(res.origin.spot || res.destination.spot) && <p className="mt-1 text-sm text-ink/55">{res.origin.spot ? `${res.origin.spot} is in ${res.origin.name}` : ''}{res.origin.spot && res.destination.spot ? ' · ' : ''}{res.destination.spot ? `${res.destination.spot} is in ${res.destination.name}` : ''}</p>}
            <ul className="num mt-3 flex flex-wrap gap-2 text-xs">
              <li className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 shadow-soft"><CalendarDays className="h-3.5 w-3.5 text-ink/50" aria-hidden />{prettyDate(res.date ?? f.date)}</li>
              <li className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 shadow-soft"><Users className="h-3.5 w-3.5 text-ink/50" aria-hidden />{res.travellers ?? f.travellers} traveller{(res.travellers ?? f.travellers) === 1 ? '' : 's'}</li>
              <li className="rounded-full bg-white px-3 py-1.5 shadow-soft">{res.trip === 'round_trip' ? 'Round trip' : 'One way'}</li>
              <li className="rounded-full bg-white px-3 py-1.5 shadow-soft">{res.straight_km} km apart</li>
            </ul>
          </div>
          <p className="max-w-3xl text-sm leading-relaxed text-ink/60">Flight fares are live from Google Flights. Train, bus and cab figures are estimates from distance (marked), because no live inventory is connected: open a route to see it on the map and follow the links for real timings and booking.</p>
          <RouteOptions data={res} />
        </motion.div>
      )}
    </div>
  )
}
