import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useApp } from '../store'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowRight, BedDouble, ChevronDown, Clock, ExternalLink, Globe, Landmark, LayoutGrid, Map as MapIcon, MapPin, Search, SearchX, Sparkles, Utensils, X } from '../components/icons'
import { api, inr, Json } from '../api'
import { Empty, ErrorBox, MapView, PageHead, Photo, Pin, Prov, Segmented, Skeletons, Stars } from '../components/ui'
import { LivePanel } from '../components/Live'
import PlaceInput from '../components/PlaceInput'
import PlaceDetail from '../components/PlaceDetail'

const POPULAR = ['Paris', 'Tokyo', 'Bali', 'New York', 'Dubai', 'Rome', 'Bangkok', 'Goa', 'London', 'Singapore', 'Istanbul', 'Delhi', 'Lisbon', 'Cape Town']
const INTERESTS: [string, string][] = [['', 'Top sights'], ['history', 'History'], ['museum', 'Museums'], ['religious', 'Sacred sites'], ['garden', 'Parks & nature'], ['shopping', 'Markets']]
type Kind = 'attractions' | 'restaurants' | 'hotels'
const KINDS: [Kind, string, typeof Landmark][] = [['attractions', 'Attractions', Landmark], ['restaurants', 'Restaurants', Utensils], ['hotels', 'Hotels', BedDouble]]

export default function Discover() {
  const { openTrip } = useApp()
  const nav = useNavigate()
  const [sp, setSp] = useSearchParams()
  const city = sp.get('city') ?? ''
  const kind = (['attractions', 'restaurants', 'hotels'].includes(sp.get('tab') ?? '') ? sp.get('tab') : sp.get('tab') === 'food' ? 'restaurants' : 'attractions') as Kind
  const interest = sp.get('interest') ?? ''
  const [q, setQ] = useState(city)
  const [rows, setRows] = useState<Json | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [view, setView] = useState<'grid' | 'map'>('grid')
  const [cmp, setCmp] = useState<string[]>([])
  const [sortBy, setSortBy] = useState('best')
  const [openNow, setOpenNow] = useState(false)
  const [maxPrice, setMaxPrice] = useState('')
  const [sel, setSel] = useState<Json | null>(null)
  const [live, setLive] = useState<Json | null>(null)
  const [showLive, setShowLive] = useState(true)
  const [active, setActive] = useState<string | null>(null)

  const set = (patch: Record<string, string>) => { const n = new URLSearchParams(sp); Object.entries(patch).forEach(([k, v]) => v ? n.set(k, v) : n.delete(k)); setSp(n) }
  const load = () => {
    if (!city) { setRows(null); return }
    setLoading(true); setErr(null); setRows(null); setCmp([])
    let dead = false
    api(`/world/discover?${new URLSearchParams({ city, kind, ...(kind === 'attractions' && interest ? { interest } : {}) })}`)
      .then(r => { if (!dead) setRows(r) }).catch(e => { if (!dead) setErr(e.message) }).finally(() => { if (!dead) setLoading(false) })
    return () => { dead = true }
  }
  useEffect(load, [city, kind, interest])
  useEffect(() => { setQ(city); setLive(null) }, [city])
  useEffect(() => { if (sortBy === 'price' && kind === 'attractions') setSortBy('best') }, [kind])
  const glat = rows?.geo?.lat, glon = rows?.geo?.lon
  useEffect(() => {  // live weather, air quality and local time for the searched place
    if (glat == null || glon == null) return
    let dead = false
    api(`/live?lat=${glat}&lon=${glon}`).then(r => { if (!dead) setLive(r) }).catch(() => {})
    return () => { dead = true }
  }, [glat, glon])

  const items: Json[] = useMemo(() => {
    let l: Json[] = rows?.places ?? rows?.hotels ?? []
    if (openNow) l = l.filter(p => /open/i.test(p.hours ?? '') && !/closed/i.test((p.hours ?? '').split('⋅')[0]))
    if (maxPrice && kind === 'hotels') l = l.filter(h => h.nightly <= Number(maxPrice))
    const key: Record<string, (p: Json) => number> = { rating: p => -(p.rating ?? 0), reviews: p => -(p.reviews ?? 0), price: p => p.nightly ?? p.price_for_two ?? 1e9 }
    return sortBy === 'best' || !key[sortBy] ? l : [...l].sort((a, b) => key[sortBy](a) - key[sortBy](b))
  }, [rows, sortBy, openNow, maxPrice, kind])
  const picked = items.filter(r => cmp.includes(r.id))
  const pins: Pin[] = useMemo(() => items.filter(p => typeof p.lat === 'number').map((p, i) => ({ id: p.id, lat: p.lat, lon: p.lon, label: `${p.name}${p.rating ? ' · ' + p.rating : ''}`, n: i + 1, color: kind === 'hotels' ? '#0b1f33' : kind === 'restaurants' ? '#f6b73c' : '#f4553f' })), [items, kind])
  const placeName = rows?.geo?.name ?? city
  const filtered = !!(openNow || maxPrice)

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 md:py-10">
      <PageHead eyebrow="Discover" title={city ? `Explore ${placeName}` : 'Discover anywhere'} sub="Search any city or town in the world for real attractions, restaurants and hotels, with ratings, photos, hours, live conditions and exact map locations." />
      <form className="mb-4 flex flex-col gap-2 sm:flex-row" onSubmit={e => { e.preventDefault(); if (q.trim()) set({ city: q.trim() }) }} role="search">
        <div className="flex-1"><PlaceInput id="dc-city" ariaLabel="Search a place" className="!rounded-full !py-3.5" placeholder="Search a city, town or college, e.g. Lisbon, Kishangarh, IIT Bombay…" value={q} onChange={setQ} onPick={s => { set({ city: s.kind ? s.label : s.name + (s.context ? ', ' + s.context.split(',').pop()!.trim() : '') }) }} /></div>
        <button className="btn btn-primary !px-6 !py-3.5" disabled={!q.trim()}><Search className="h-4 w-4" aria-hidden />Search</button>
      </form>
      <div className="no-scrollbar -mx-4 mb-7 flex gap-2 overflow-x-auto px-4 sm:mx-0 sm:flex-wrap sm:px-0">{POPULAR.map(c => <button key={c} onClick={() => { setQ(c); set({ city: c }) }} aria-pressed={city === c} className={`chip whitespace-nowrap ${city === c ? 'chip-on' : ''}`}>{c}</button>)}</div>

      {!city ? <Empty title="Where to?" icon={<Globe className="h-7 w-7" />}>Pick a popular city above or search any place. Results are fetched live from Google Maps and Google Hotels, then cached to save quota.</Empty> : (
        <>
          {rows?.geo && (
            <section className="mb-7" aria-label={`Live conditions in ${placeName}`}>
              <button className="mb-3 flex min-h-[36px] items-center gap-2 font-display text-xl font-bold" aria-expanded={showLive} onClick={() => setShowLive(s => !s)}>
                <span className="relative flex h-2.5 w-2.5" aria-hidden><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-75" /><span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" /></span>
                Right now in {placeName}<ChevronDown className={`h-4 w-4 text-ink/40 transition-transform ${showLive ? 'rotate-180' : ''}`} aria-hidden /></button>
              <AnimatePresence initial={false}>{showLive && <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden"><LivePanel live={live} place={placeName} /></motion.div>}</AnimatePresence>
            </section>
          )}

          <div className="mb-4 flex flex-wrap items-center gap-3">
            <div className="no-scrollbar flex gap-1 overflow-x-auto rounded-full border border-ink/[.07] bg-white p-1 shadow-soft" role="tablist" aria-label="What to look for">
              {KINDS.map(([k, l, Icon]) => <button key={k} role="tab" aria-selected={kind === k} onClick={() => set({ tab: k, interest: '' })} className={`relative flex min-h-[42px] items-center gap-2 whitespace-nowrap rounded-full px-4 text-sm font-semibold transition-colors ${kind === k ? 'text-white' : 'text-ink/60 hover:text-ink'}`}>
                {kind === k && <motion.span layoutId="dc-kind" className="absolute inset-0 rounded-full bg-ink" transition={{ type: 'spring', stiffness: 400, damping: 34 }} />}<span className="sr-only">{k}</span><span aria-hidden className="relative z-10 flex items-center gap-2"><Icon className="h-4 w-4" />{l}</span></button>)}
            </div>
            <div className="ml-auto"><Segmented id="dcview" label="Layout" value={view} onChange={setView} options={[['grid', <><LayoutGrid className="h-3.5 w-3.5" aria-hidden />List</>], ['map', <><MapIcon className="h-3.5 w-3.5" aria-hidden />Map</>]]} /></div>
          </div>
          {kind === 'attractions' && <div className="mb-4 flex flex-wrap gap-2">{INTERESTS.map(([k, l]) => <button key={k} aria-pressed={interest === k} onClick={() => set({ interest: k })} className={`chip !min-h-[34px] !py-1 ${interest === k ? 'chip-on' : ''}`}>{l}</button>)}</div>}
          <div className="mb-5 flex flex-wrap items-center gap-3 text-sm">
            <label className="flex items-center gap-2 font-medium">Sort<select className="input !w-auto !py-2" value={sortBy} onChange={e => setSortBy(e.target.value)} aria-label="Sort results"><option value="best">Best match</option><option value="rating">Highest rated</option><option value="reviews">Most reviewed</option>{kind !== 'attractions' && <option value="price">Lowest price</option>}</select></label>
            {kind !== 'hotels' && <label className="flex min-h-[36px] cursor-pointer items-center gap-2"><input type="checkbox" className="h-4 w-4 accent-coral" checked={openNow} onChange={e => setOpenNow(e.target.checked)} />Open now</label>}
            {kind === 'hotels' && <label className="flex items-center gap-2">Max ₹/night<input className="input num !w-32 !py-2" type="number" min={0} step={500} value={maxPrice} onChange={e => setMaxPrice(e.target.value)} /></label>}
            {rows && <span className="ml-auto flex flex-wrap items-center gap-2 text-xs text-ink/50"><span className="num">{items.length} result{items.length === 1 ? '' : 's'}</span><span>{rows.geo.display ?? rows.geo.name}</span><Prov p={rows.provenance} />{kind === 'hotels' && rows.dates ? <span className="num">rates for {rows.dates[0]} → {rows.dates[1]}</span> : null}</span>}
          </div>

          {err && <ErrorBox msg={err} retry={load} />}
          {loading && <Skeletons n={6} h="h-72" />}
          {rows?.error && !items.length && !filtered && <ErrorBox msg={rows.error} retry={load} />}
          {rows && !loading && items.length === 0 && (!rows.error || filtered) && <Empty title="Nothing matches" icon={<SearchX className="h-7 w-7" />}>{filtered ? <>No results with these filters. <button className="link" onClick={() => { setOpenNow(false); setMaxPrice('') }}>Clear filters</button></> : 'Try another category or a nearby larger town.'}</Empty>}

          {rows && view === 'map' && items.length > 0 && (
            <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
              <MapView pins={pins} height={560} center={[rows.geo.lon, rows.geo.lat]} activeId={active} onPinClick={id => { setActive(id); const it = items.find(x => x.id === id); if (it) setSel(it) }} />
              <ol className="card max-h-[560px] space-y-1 overflow-y-auto !p-2">
                {items.map((a, i) => <li key={a.id}><button onMouseEnter={() => setActive(a.id)} onFocus={() => setActive(a.id)} onClick={() => setSel(a)} className={`flex w-full items-center gap-3 rounded-2xl p-2 text-left text-sm transition ${active === a.id ? 'bg-coral-50' : 'hover:bg-sand'}`}>
                  <span className="num grid h-7 w-7 shrink-0 place-items-center rounded-full bg-ink text-xs font-bold text-white">{i + 1}</span>
                  <span className="min-w-0 flex-1"><span className="block truncate font-semibold">{a.name}</span><span className="flex items-center gap-2 text-xs text-ink/55"><Stars v={a.rating} n={a.reviews} />{kind === 'hotels' && <span className="num">{inr(a.nightly)}</span>}</span></span></button></li>)}
              </ol>
            </div>
          )}

          {rows && view === 'grid' && <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">{items.map((a, i) => (
            <motion.article key={a.id} initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 9) * 0.04, duration: 0.4 }}
              role="button" tabIndex={0} aria-label={`Details for ${a.name}`} onClick={() => setSel(a)} onKeyDown={e => { if (e.target === e.currentTarget && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); setSel(a) } }}
              className={`card card-hover group flex min-w-0 cursor-pointer flex-col gap-2 !p-3 ${cmp.includes(a.id) ? 'ring-2 ring-coral' : ''}`}>
              <Photo src={kind === 'hotels' ? a.images?.[0] : a.thumbnail} name={a.name} h="h-44" zoom><span className="num absolute left-2.5 top-2.5 grid h-7 w-7 place-items-center rounded-full bg-white/95 text-xs font-bold shadow-soft">{i + 1}</span>
                {kind === 'hotels' && a.nightly != null && <span className="num absolute bottom-2.5 right-2.5 rounded-full bg-ink-900/85 px-3 py-1 text-sm font-bold text-white backdrop-blur">{inr(a.nightly)}<span className="text-xs font-normal text-white/70">/night</span></span>}</Photo>
              <div className="px-1"><h3 className="font-display text-lg font-bold leading-tight">{a.name}</h3>
                <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-ink/60"><Stars v={a.rating} n={a.reviews} /><span className="truncate">{kind === 'hotels' ? (a.type ?? 'hotel') : (a.types?.[0] ?? a.category)}</span></div>
                {kind === 'hotels' ? (a.total ? <p className="num mt-1 text-xs text-ink/55">{inr(a.total)} total for the stay</p> : null)
                  : <>{a.address && <p className="mt-1.5 flex items-start gap-1.5 text-xs text-ink/55"><MapPin className="mt-0.5 h-3 w-3 shrink-0" aria-hidden /><span className="line-clamp-1">{a.address}</span></p>}<p className="mt-1 flex items-start gap-1.5 text-xs text-ink/60"><Clock className="mt-0.5 h-3 w-3 shrink-0" aria-hidden /><span className="line-clamp-1">{a.hours ?? 'Hours: check official site'}{a.price_level ? ` · ${a.price_level}` : ''}</span></p>
                    {kind === 'attractions' && <p className="mt-1 text-xs text-ink/50">~{a.visit_min} min visit (estimate) · Entry: <span className="text-amber-700">check official site</span></p>}</>}
                {kind === 'hotels' && a.amenities?.length > 0 && <p className="mt-1 truncate text-xs text-ink/50">{a.amenities.slice(0, 4).join(' · ')}</p>}
              </div>
              <div className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-ink/[.06] px-1 pt-2 text-xs">
                {a.maps_url && <a onClick={e => e.stopPropagation()} className="link inline-flex items-center gap-1 py-2" href={a.maps_url} target="_blank" rel="noreferrer">Google Maps<ExternalLink className="h-3 w-3" aria-hidden /></a>}
                {a.website && <a onClick={e => e.stopPropagation()} className="link inline-flex items-center gap-1 py-2" href={a.website} target="_blank" rel="noreferrer">Website<ExternalLink className="h-3 w-3" aria-hidden /></a>}
                {a.booking_url && <a onClick={e => e.stopPropagation()} className="btn btn-primary btn-sm !min-h-[32px]" href={a.booking_url} target="_blank" rel="noreferrer">View &amp; book</a>}
                <label onClick={e => e.stopPropagation()} className="ml-auto flex min-h-[36px] cursor-pointer items-center gap-1.5 font-medium"><input type="checkbox" className="h-4 w-4 accent-coral" checked={cmp.includes(a.id)} onChange={e => setCmp(e.target.checked ? [...cmp, a.id].slice(-3) : cmp.filter(x => x !== a.id))} />Compare</label>
              </div>
            </motion.article>))}</div>}

          {rows && items.length > 0 && (
            <div className="mt-8 flex flex-wrap items-center justify-between gap-3 rounded-3xl bg-ink-900 p-5 text-white md:p-6">
              <p className="flex items-center gap-3"><span className="icon-tile bg-coral"><Sparkles className="h-5 w-5" aria-hidden /></span><span><span className="block font-display text-lg font-bold">Like what you see in {placeName}?</span><span className="text-sm text-white/65">Let TRIP turn it into a day-by-day plan with a budget.</span></span></p>
              <button className="btn btn-primary" onClick={async () => { await openTrip(null); nav(`/workspace?to=${encodeURIComponent(placeName)}`) }}>Plan a trip here<ArrowRight className="h-4 w-4" aria-hidden /></button>
            </div>
          )}

          <AnimatePresence>
            {picked.length >= 2 && (
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 20 }} className="card mt-6 overflow-x-auto">
                <div className="mb-2 flex items-center justify-between"><p className="font-display text-lg font-bold">Comparison</p><button className="btn btn-ghost btn-sm" onClick={() => setCmp([])}><X className="h-3.5 w-3.5" aria-hidden />Clear</button></div>
                <table className="w-full min-w-[480px] text-left text-sm"><thead><tr><th className="w-24"><span className="sr-only">Field</span></th>{picked.map(p => <th key={p.id} className="pb-2 pr-4 font-display font-bold">{p.name}</th>)}</tr></thead><tbody>
                  {(kind === 'hotels' ? [['Rating', 'rating'], ['Reviews', 'reviews'], ['Per night', 'nightly'], ['Type', 'type']] : [['Rating', 'rating'], ['Reviews', 'reviews'], ['Type', 'category'], ['Hours', 'hours'], ['Address', 'address']]).map(([l, k]) => <tr key={k} className="border-t border-ink/10"><td className="py-2 pr-4 text-ink/50">{l}</td>{picked.map(p => <td key={p.id} className="num py-2 pr-4">{k === 'nightly' ? inr(p[k]) : k === 'reviews' && p[k] ? Number(p[k]).toLocaleString() : String(p[k] ?? '—')}</td>)}</tr>)}</tbody></table>
              </motion.div>
            )}
          </AnimatePresence>
          {cmp.length === 1 && <p className="mt-4 text-center text-xs text-ink/50" role="status">Tick one more to compare side by side (up to three).</p>}
        </>
      )}
      {sel && <PlaceDetail item={sel} kind={kind === 'hotels' ? 'hotel' : kind === 'restaurants' ? 'restaurant' : 'attraction'} onClose={() => setSel(null)} />}
    </div>
  )
}
