import { useState } from 'react'
import { motion } from 'framer-motion'
import { ArrowLeftRight, ArrowRight, Bus, Car, Plane, Search, TrainFront } from '../components/icons'
import { api, Json } from '../api'
import { Empty, ErrorBox, PageHead } from '../components/ui'
import PlaceInput from '../components/PlaceInput'
import RouteOptions from '../components/RouteOptions'

const tomorrow = (n: number) => new Date(Date.now() + n * 864e5).toISOString().slice(0, 10)
const EXAMPLES: [string, string][] = [['Mumbai', 'Goa'], ['Delhi', 'Jaipur'], ['Bengaluru', 'Singapore'], ['Kolkata', 'Bangkok']]

export default function Transport() {
  const [f, setF] = useState({ origin: '', destination: '', date: tomorrow(21), travellers: 2, budget: '' })
  const [res, setRes] = useState<Json | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  async function search(v = f) {
    if (v.origin.trim().length < 2 || v.destination.trim().length < 2) { setErr('Enter both where you are starting from and where you are going.'); return }
    if (v.origin.trim().toLowerCase() === v.destination.trim().toLowerCase()) { setErr('The start and the destination are the same place.'); return }
    setBusy(true); setErr(null); setRes(null)
    try { setRes(await api(`/routes/options?${new URLSearchParams({ origin: v.origin, destination: v.destination, date: v.date, travellers: String(v.travellers), ...(v.budget ? { budget: v.budget } : {}) })}`)) }
    catch (x) { setErr((x as Error).message) } finally { setBusy(false) }
  }
  return (
    <div className="mx-auto max-w-5xl px-4 py-8 md:py-10">
      <PageHead eyebrow="Ways to travel" title="Door to door, every sensible way" sub="Enter where you are and where you are going (any town or city). You get flights with cab transfers from the nearest airport, direct cab, bus and train, compared by cost, time and comfort." />
      <form onSubmit={e => { e.preventDefault(); void search() }} noValidate className="card grid gap-4 !p-5 sm:grid-cols-6 md:!p-6">
        <div className="grid gap-3 sm:col-span-6 sm:grid-cols-[1fr_auto_1fr] sm:items-start">
          <PlaceInput id="tr-from" label="From" placeholder="Town, college, station or airport" value={f.origin} onChange={v => setF(s => ({ ...s, origin: v }))} />
          <button type="button" aria-label="Swap from and to" title="Swap" onClick={() => setF(s => ({ ...s, origin: s.destination, destination: s.origin }))} className="mx-auto grid h-[42px] w-[42px] place-items-center rounded-full border border-ink/10 bg-white text-ink/60 shadow-soft transition duration-300 hover:rotate-180 hover:border-coral hover:text-coral sm:mt-[1.6rem]"><ArrowLeftRight className="h-4 w-4 rotate-90 sm:rotate-0" /></button>
          <PlaceInput id="tr-to" label="To" placeholder="Where to? Town, college, airport…" value={f.destination} onChange={v => setF(s => ({ ...s, destination: v }))} />
        </div>
        <div className="sm:col-span-2"><label className="label" htmlFor="tr-date">Date</label><input id="tr-date" type="date" className="input num" min={tomorrow(0)} value={f.date} onChange={e => setF({ ...f, date: e.target.value })} required /></div>
        <div><label className="label" htmlFor="tr-n">Travellers</label><input id="tr-n" type="number" inputMode="numeric" min={1} max={20} className="input num" value={f.travellers} onChange={e => setF({ ...f, travellers: Math.max(1, Math.min(20, +e.target.value || 1)) })} /></div>
        <div className="sm:col-span-2"><label className="label" htmlFor="tr-b">Trip budget ₹ <span className="font-medium normal-case tracking-normal text-ink/40">(optional)</span></label><input id="tr-b" type="number" inputMode="numeric" min={500} step={500} className="input num" placeholder="e.g. 60000" value={f.budget} onChange={e => setF({ ...f, budget: e.target.value })} /></div>
        <div className="flex items-end"><button className="btn btn-primary w-full !py-2.5" disabled={busy}><Search className="h-4 w-4" aria-hidden />{busy ? 'Searching…' : 'Compare'}</button></div>
      </form>
      {err && <div className="mt-4"><ErrorBox msg={err} /></div>}

      {busy && (
        <div className="mt-6 space-y-3" role="status" aria-label="Searching">
          <p className="flex items-center gap-3 text-sm text-ink/60"><motion.span animate={{ x: [0, 14, 0] }} transition={{ duration: 1.4, repeat: Infinity }} className="text-coral"><Plane className="h-4 w-4" aria-hidden /></motion.span>Finding the nearest airports, live flight fares and road estimates…</p>
          {[0, 1, 2].map(i => <div key={i} className="skeleton h-36" />)}
        </div>
      )}

      {!res && !busy && !err && (
        <div className="mt-8">
          <Empty title="Compare every way to get there" icon={<div className="flex gap-1"><Plane className="h-5 w-5" /><TrainFront className="h-5 w-5" /></div>}>
            <p>Not sure where to start? Try one of these.</p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">{EXAMPLES.map(([a, b]) => <button key={a + b} className="chip" onClick={() => { const v = { ...f, origin: a, destination: b }; setF(v); void search(v) }}>{a}<ArrowRight className="h-3.5 w-3.5" aria-hidden />{b}</button>)}</div>
            <p className="mt-5 flex flex-wrap items-center justify-center gap-4 text-xs text-ink/45"><span className="flex items-center gap-1.5"><Plane className="h-3.5 w-3.5" aria-hidden />Live flight fares</span><span className="flex items-center gap-1.5"><TrainFront className="h-3.5 w-3.5" aria-hidden />Train estimates</span><span className="flex items-center gap-1.5"><Bus className="h-3.5 w-3.5" aria-hidden />Bus estimates</span><span className="flex items-center gap-1.5"><Car className="h-3.5 w-3.5" aria-hidden />Cab estimates</span></p>
          </Empty>
        </div>
      )}

      {res && (
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="mt-8 space-y-4">
          <h2 className="flex flex-wrap items-center gap-3 font-display text-3xl font-bold">{res.origin.name}<ArrowRight className="h-6 w-6 text-coral" aria-hidden />{res.destination.name}</h2>
          <p className="max-w-3xl text-sm leading-relaxed text-ink/60"><span className="num">{res.straight_km} km</span> apart. Flight fares are live from Google Flights; cab, bus and train are estimates from distance (marked), because no live inventory is connected. Booking is always on the operator's site.</p>
          <RouteOptions data={res} />
        </motion.div>
      )}
    </div>
  )
}
