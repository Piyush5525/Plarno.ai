import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Banknote, Cross, LocateFixed, MapPin, Navigation, Phone, Pill, ShieldCheck, ShoppingBasket } from './icons'
import { api, Json } from '../api'
import { Prov } from './ui'

const KINDS: [string, string, typeof Pill][] = [['pharmacy', 'Pharmacy', Pill], ['hospital', 'Hospital', Cross], ['grocery', 'Grocery', ShoppingBasket], ['atm', 'ATM', Banknote], ['police', 'Police', ShieldCheck]]
const dist = (km: number) => (km < 1 ? `${Math.round(km * 1000)} m` : `${km.toFixed(1)} km`)

/** Everyday essentials near a point (your stay, or wherever you are right now): pharmacies, hospitals, groceries, ATMs, police.
 *  Real listings with distance, a call button when the listing has a phone number, and directions. */
export default function Nearby({ lat, lon, label }: { lat: number; lon: number; label: string }) {
  const [kind, setKind] = useState('pharmacy')
  const [me, setMe] = useState<{ lat: number; lon: number } | null>(null)
  const [locErr, setLocErr] = useState<string | null>(null)
  const [locating, setLocating] = useState(false)
  const [res, setRes] = useState<Json | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const at = me ?? { lat, lon }

  useEffect(() => {
    let dead = false
    setRes(null); setErr(null)
    api(`/nearby?lat=${at.lat}&lon=${at.lon}&kind=${kind}`).then(r => { if (!dead) setRes(r) }).catch(e => { if (!dead) setErr(e.message) })
    return () => { dead = true }
  }, [kind, at.lat, at.lon])

  const nearMe = () => {
    if (me) { setMe(null); return }
    setLocErr(null)
    if (!('geolocation' in navigator)) { setLocErr('This browser cannot share a location.'); return }
    setLocating(true)
    navigator.geolocation.getCurrentPosition(p => { setMe({ lat: p.coords.latitude, lon: p.coords.longitude }); setLocating(false) },
      e => { setLocating(false); setLocErr(e.code === e.PERMISSION_DENIED ? 'Location permission was denied. Allow it in your browser to search around you.' : 'Could not get your location.') }, { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 })
  }
  const places: Json[] = res?.places ?? []

  return (
    <section aria-label="Essentials nearby" className="card !p-4 sm:!p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0"><h2 className="font-display text-xl font-bold">Essentials nearby</h2><p className="text-sm text-ink/60">Around {me ? 'where you are now' : label}. Handy when you are new to a place.</p></div>
        <button onClick={nearMe} disabled={locating} aria-pressed={!!me} className={`chip !min-h-[40px] ${me ? 'chip-on' : ''}`}><LocateFixed className="h-4 w-4" aria-hidden />{locating ? 'Locating…' : me ? 'Using my location' : 'Near me instead'}</button>
      </div>
      {locErr && <p role="alert" className="mt-2 text-xs text-rose-700">{locErr}</p>}
      <div className="no-scrollbar -mx-4 mt-3 flex gap-2 overflow-x-auto px-4 sm:mx-0 sm:flex-wrap sm:px-0" role="tablist" aria-label="What to look for">
        {KINDS.map(([k, l, Icon]) => <button key={k} role="tab" aria-selected={kind === k} onClick={() => setKind(k)} className={`chip !min-h-[40px] shrink-0 ${kind === k ? 'chip-on' : ''}`}><Icon className="h-4 w-4" aria-hidden />{l}</button>)}
      </div>
      <div className="mt-3">
        {!res && !err && <div className="grid gap-2 sm:grid-cols-2" role="status" aria-label="Loading nearby places">{[0, 1, 2, 3].map(i => <div key={i} className="skeleton h-24" />)}</div>}
        {err && <p role="alert" className="rounded-2xl bg-rose-50 p-3 text-sm text-rose-800">{err}</p>}
        {res?.error && <p className="rounded-2xl bg-sun-50 p-3 text-sm text-amber-900">{res.error}</p>}
        {res && !res.error && places.length === 0 && <p className="rounded-2xl bg-sand p-3 text-sm text-ink/60">Nothing listed within 25 km. Try another category, or ask at your hotel.</p>}
        <ul className="grid gap-2 sm:grid-cols-2">
          {places.map((p, i) => (
            <motion.li key={p.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 8) * 0.03 }} className="flex min-w-0 flex-col gap-2 rounded-2xl bg-sand p-3">
              <div className="flex items-start justify-between gap-2">
                <p className="min-w-0 font-semibold leading-snug">{p.name}</p>
                <span className="num shrink-0 rounded-full bg-white px-2.5 py-0.5 text-xs font-bold text-lagoon-700">{dist(p.distance_km)}</span>
              </div>
              {p.address && <p className="flex items-start gap-1.5 text-xs text-ink/60"><MapPin className="mt-0.5 h-3 w-3 shrink-0" aria-hidden /><span className="line-clamp-2">{p.address}</span></p>}
              <div className="mt-auto flex flex-wrap gap-2">
                {p.phone && <a href={`tel:${p.phone}`} className="inline-flex min-h-[38px] items-center gap-1.5 rounded-full bg-lagoon px-3.5 text-xs font-semibold text-white transition hover:bg-lagoon-600"><Phone className="h-3.5 w-3.5" aria-hidden />Call<span className="num hidden sm:inline">{p.phone}</span></a>}
                <a href={p.maps_url} target="_blank" rel="noreferrer" className="inline-flex min-h-[38px] items-center gap-1.5 rounded-full border border-ink/15 bg-white px-3.5 text-xs font-semibold transition hover:border-coral hover:text-coral-600"><Navigation className="h-3.5 w-3.5" aria-hidden />Directions</a>
              </div>
            </motion.li>
          ))}
        </ul>
        {res && places.length > 0 && <p className="mt-3 flex flex-wrap items-center gap-2 text-xs text-ink/45"><Prov p={res.provenance} />Listings can be out of date: call ahead to check they are open. In an emergency, use the local emergency number.</p>}
      </div>
    </section>
  )
}
