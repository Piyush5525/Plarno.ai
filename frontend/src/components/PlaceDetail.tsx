import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { motion } from 'framer-motion'
import { Check, ChevronLeft, ChevronRight, Clock, Compass, ExternalLink, MapPin, Navigation, Phone, Plus, Ticket, TrainFront, Wallet, X } from './icons'
import { inr, Json } from '../api'
import { MapView, Photo, Prov, Stars } from './ui'

const DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
const todayKey = () => DAYS[(new Date().getDay() + 6) % 7]
const clean = (s?: string) => (s ?? '').replace(/[  ]/g, ' ').replace(/\s*\([^)]*\)/g, '')

/** Full details for a place or hotel: photos, rating, weekday hours, address/phone/links, a pinned map and the actions that matter. */
export default function PlaceDetail({ item, kind, onClose, onAdd, addLabel, onChoose, busy }: {
  item: Json; kind: 'attraction' | 'restaurant' | 'hotel'; onClose: () => void; onAdd?: () => void; addLabel?: string; onChoose?: () => void; busy?: boolean
}) {
  const closeRef = useRef<HTMLButtonElement>(null)
  const box = useRef<HTMLDivElement>(null)
  const [img, setImg] = useState(0)
  const photos: string[] = kind === 'hotel' ? item.images ?? [] : item.thumbnail ? [item.thumbnail] : []
  const hours = item.operating_hours as Record<string, string> | null | undefined
  const types: string[] = item.types ?? []
  const hasGeo = typeof item.lat === 'number' && typeof item.lon === 'number'
  const directions = hasGeo ? `https://www.google.com/maps/dir/?api=1&destination=${item.lat},${item.lon}` : null
  const step = (d: number) => setImg(i => (i + d + photos.length) % photos.length)

  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowRight' && photos.length > 1) step(1)
      if (e.key === 'ArrowLeft' && photos.length > 1) step(-1)
      if (e.key === 'Tab' && box.current) {  // keep keyboard focus inside the dialog
        const f = [...box.current.querySelectorAll<HTMLElement>('button, a[href], input, [tabindex]:not([tabindex="-1"])')].filter(el => !el.hasAttribute('disabled') && el.offsetParent !== null)
        if (!f.length) return
        const first = f[0], last = f[f.length - 1]
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
      }
    }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = ''; prev?.focus?.() }
  }, [])

  return createPortal(
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="fixed inset-0 z-[70] flex items-end justify-center bg-ink-900/70 p-0 backdrop-blur-sm sm:items-center sm:p-6" onMouseDown={onClose}>
      <motion.div ref={box} initial={{ y: 48, opacity: 0, scale: 0.98 }} animate={{ y: 0, opacity: 1, scale: 1 }} transition={{ type: 'spring', stiffness: 320, damping: 32 }} role="dialog" aria-modal="true" aria-labelledby="pd-title" onMouseDown={e => e.stopPropagation()}
        className="max-h-[94dvh] w-full max-w-3xl overflow-y-auto rounded-t-[2rem] bg-white shadow-lift sm:rounded-[2rem]">
        <div className="relative">
          <Photo src={photos[img]} name={item.name} h="h-56 sm:h-80" className="!rounded-none sm:!rounded-t-[2rem]"><div className="pointer-events-none absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-ink-900/60 to-transparent" /></Photo>
          <button ref={closeRef} aria-label="Close details" onClick={onClose} className="absolute right-3 top-3 grid h-11 w-11 place-items-center rounded-full bg-white/95 shadow-soft transition hover:rotate-90 hover:bg-white"><X className="h-5 w-5" /></button>
          {photos.length > 1 && (<>
            <button aria-label="Previous photo" onClick={() => step(-1)} className="absolute left-3 top-1/2 grid h-10 w-10 -translate-y-1/2 place-items-center rounded-full bg-white/90 shadow-soft transition hover:bg-white"><ChevronLeft className="h-5 w-5" /></button>
            <button aria-label="Next photo" onClick={() => step(1)} className="absolute right-3 top-1/2 grid h-10 w-10 -translate-y-1/2 place-items-center rounded-full bg-white/90 shadow-soft transition hover:bg-white"><ChevronRight className="h-5 w-5" /></button>
            <div className="no-scrollbar absolute bottom-3 left-3 right-3 flex gap-2 overflow-x-auto">{photos.slice(0, 8).map((p, i) => <button key={i} aria-label={`Photo ${i + 1}`} aria-pressed={i === img} onClick={() => setImg(i)} className={`h-12 w-12 shrink-0 overflow-hidden rounded-xl border-2 transition ${i === img ? 'scale-105 border-white' : 'border-white/40 opacity-80 hover:opacity-100'}`}><img src={p} alt="" referrerPolicy="no-referrer" className="h-full w-full object-cover" /></button>)}</div>
          </>)}
        </div>
        <div className="space-y-5 p-5 sm:p-7">
          <div>
            <h2 id="pd-title" className="font-display text-3xl font-bold leading-tight">{item.name}</h2>
            <div className="mt-1.5 flex flex-wrap items-center gap-2 text-sm text-ink/60">
              <Stars v={item.rating} n={item.reviews} />
              {kind === 'hotel' ? <span>{item.type ?? 'Hotel'}{item.stars ? ` · ${item.stars}-star` : ''}</span> : <span>{types.slice(0, 3).join(' · ') || item.category}</span>}
              {item.price_level && <span className="badge bg-sun-50 text-amber-800">{item.price_level}</span>}
              {item.provenance && <Prov p={item.provenance} />}
            </div>
          </div>

          {kind === 'hotel' && (
            <div className="grid gap-3 rounded-2xl bg-sand p-4 sm:grid-cols-3">
              <div><p className="label !mb-0">Per night</p><p className="num font-display text-2xl font-bold">{inr(item.price_per_night ?? item.nightly)}</p></div>
              <div><p className="label !mb-0">Check-in / out</p><p className="num mt-1 text-sm font-medium">{item.check_in_time ?? '—'} / {item.check_out_time ?? '—'}</p></div>
              <div><p className="label !mb-0">Score</p><p className="num font-display text-2xl font-bold text-lagoon-700">{item.score ?? '—'}</p></div>
            </div>
          )}
          {item.description && <p className="text-[15px] leading-relaxed text-ink/80">{item.description}</p>}

          <div className="grid gap-5 sm:grid-cols-2">
            <div className="space-y-3 text-sm">
              <h3 className="font-display text-base font-bold">Details</h3>
              {item.address && <p className="flex gap-2.5"><MapPin className="mt-0.5 h-4 w-4 shrink-0 text-ink/45" aria-hidden /><span>{item.address}</span></p>}
              {item.phone && <p className="flex gap-2.5"><Phone className="mt-0.5 h-4 w-4 shrink-0 text-ink/45" aria-hidden /><a className="link" href={`tel:${item.phone}`}>{item.phone}</a></p>}
              {kind !== 'hotel' && item.visit_min && <p className="flex gap-2.5"><Clock className="mt-0.5 h-4 w-4 shrink-0 text-ink/45" aria-hidden /><span>About {item.visit_min} min to visit <span className="text-ink/40">(estimate)</span></span></p>}
              {kind === 'attraction' && <p className="flex gap-2.5"><Ticket className="mt-0.5 h-4 w-4 shrink-0 text-ink/45" aria-hidden /><span>Entry: <span className="text-amber-700">{item.fee_inr === 0 ? 'free' : 'not provided by the data source. Check the official site.'}</span></span></p>}
              {kind === 'restaurant' && <p className="flex gap-2.5"><Wallet className="mt-0.5 h-4 w-4 shrink-0 text-ink/45" aria-hidden /><span>{item.price_for_two ? `About ${inr(item.price_for_two)} for two (estimate)` : 'Price not listed'}</span></p>}
              {kind === 'hotel' && item.amenities?.length > 0 && <div><p className="mb-1.5 font-semibold">Amenities</p><div className="flex flex-wrap gap-1.5">{item.amenities.map((a: string) => <span key={a} className="rounded-full bg-sand px-2.5 py-1 text-xs">{a}</span>)}</div></div>}
              {kind === 'hotel' && item.transit_nearby?.length > 0 && <p className="flex gap-2.5"><TrainFront className="mt-0.5 h-4 w-4 shrink-0 text-ink/45" aria-hidden /><span>Near {item.transit_nearby.join(', ')}</span></p>}
              {kind === 'hotel' && item.avg_km_to_attractions != null && <p className="flex gap-2.5"><Compass className="mt-0.5 h-4 w-4 shrink-0 text-ink/45" aria-hidden /><span>{item.avg_km_to_attractions} km on average from your chosen sights</span></p>}
              {!item.address && !item.phone && kind !== 'hotel' && !item.visit_min && <p className="text-ink/55">No further details were provided for this place.</p>}
            </div>
            <div className="text-sm">
              <h3 className="mb-2 font-display text-base font-bold">Opening hours</h3>
              {hours && Object.keys(hours).length ? (
                <ul className="divide-y divide-ink/5 overflow-hidden rounded-2xl border border-ink/10">
                  {DAYS.filter(d => hours[d]).map(d => (
                    <li key={d} className={`num flex justify-between gap-3 px-3 py-1.5 ${d === todayKey() ? 'bg-coral-50 font-semibold' : ''}`}><span className="capitalize">{d}{d === todayKey() && ' (today)'}</span><span className="text-right">{clean(hours[d])}</span></li>
                  ))}
                </ul>
              ) : <p className="text-ink/60">{kind === 'hotel' ? 'Front desk hours not listed.' : item.hours ? `Right now: ${clean(item.hours)}` : item.hours_note ? clean(item.hours_note) : 'Hours not listed. Check the official site.'}</p>}
              {hours && <p className="mt-1.5 text-xs text-ink/45">Holiday hours can differ. Source: Google Maps listing.</p>}
            </div>
          </div>

          {hasGeo && <MapView pins={[{ lat: item.lat, lon: item.lon, label: item.name, color: '#f4553f', kind: kind === 'hotel' ? 'hotel' : kind === 'restaurant' ? 'meal' : undefined, n: kind === 'attraction' ? '★' : undefined }]} center={[item.lon, item.lat]} height={220} />}

          <div className="sticky bottom-0 -mx-5 -mb-5 flex flex-wrap gap-2 border-t border-ink/10 bg-white/95 p-4 backdrop-blur sm:-mx-7 sm:-mb-7 sm:px-7">
            {onChoose && <button className="btn btn-primary" disabled={busy} onClick={onChoose}><Check className="h-4 w-4" aria-hidden />{busy ? 'Updating…' : 'Choose this hotel'}</button>}
            {onAdd && <button className="btn btn-primary" disabled={busy} onClick={onAdd}><Plus className="h-4 w-4" aria-hidden />{busy ? 'Adding…' : addLabel ?? 'Add to my trip'}</button>}
            {item.booking_url && <a className="btn btn-dark" href={item.booking_url} target="_blank" rel="noreferrer">View &amp; book<ExternalLink className="h-4 w-4" aria-hidden /></a>}
            {directions && <a className="btn btn-ghost" href={directions} target="_blank" rel="noreferrer"><Navigation className="h-4 w-4" aria-hidden />Directions</a>}
            {item.maps_url && <a className="btn btn-ghost" href={item.maps_url} target="_blank" rel="noreferrer">Google Maps<ExternalLink className="h-3.5 w-3.5" aria-hidden /></a>}
            {item.website && <a className="btn btn-ghost" href={item.website} target="_blank" rel="noreferrer">Website<ExternalLink className="h-3.5 w-3.5" aria-hidden /></a>}
          </div>
        </div>
      </motion.div>
    </motion.div>,
    document.body,
  )
}
