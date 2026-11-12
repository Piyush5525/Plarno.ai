import { ReactNode, useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import { animate, motion, useInView, useReducedMotion } from 'framer-motion'
import { AlertTriangle, Compass, RefreshCw as RotateCw, Star } from './icons'
import { api, Json } from '../api'

const KIND_STYLE: Record<string, string> = {
  live: 'bg-emerald-100 text-emerald-800', cached: 'bg-sky-100 text-sky-800',
  estimated: 'bg-amber-100 text-amber-800', simulated: 'bg-violet-100 text-violet-800', 'no data': 'bg-ink/10 text-ink/60',
}
const KIND_TIP: Record<string, string> = {
  live: 'Fetched live from the provider', cached: 'Recently fetched from the provider (served from cache)', estimated: 'Estimate, not a measurement',
  simulated: 'Demo data, not real', 'no data': 'The provider returned no data for this',
}
/** Every number in the product that is not live data is labelled. */
export function Prov({ p, label }: { p?: Json | string; label?: string }) {
  const kind = typeof p === 'string' ? 'simulated' : p?.kind ?? 'simulated'
  const tip = typeof p === 'string' ? p : p ? `${KIND_TIP[kind] ?? ''}${p.source ? ' · ' + p.source : ''}${p.fetched_at ? ' · ' + p.fetched_at : ''}${p.note ? ' · ' + p.note : ''}` : KIND_TIP.simulated
  return <span title={tip} className={`badge ${KIND_STYLE[kind] ?? KIND_STYLE.simulated}`}>{kind === 'live' && <span className="relative flex h-1.5 w-1.5" aria-hidden><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-75" /><span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-600" /></span>}{label ?? kind}</span>
}

export function Loading({ text = 'Loading…' }: { text?: string }) {
  return <div className="flex items-center gap-3 py-10 text-sm text-ink/60" role="status"><span className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-ink/20 border-t-coral" />{text}</div>
}
export function Skeletons({ n = 6, h = 'h-56' }: { n?: number; h?: string }) {
  return <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3" role="status" aria-label="Loading">{Array.from({ length: n }).map((_, i) => <div key={i} className={`skeleton ${h}`} />)}</div>
}
export function ErrorBox({ msg, retry }: { msg: string; retry?: () => void }) {
  return (
    <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} role="alert" className="flex flex-wrap items-center gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
      <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden /><span className="min-w-0 flex-1">{msg}</span>
      {retry && <button onClick={retry} className="btn btn-sm border border-rose-300 bg-white text-rose-800 hover:bg-rose-100"><RotateCw className="h-3.5 w-3.5" aria-hidden />Try again</button>}
    </motion.div>
  )
}
export function Empty({ title, children, icon }: { title: string; children?: ReactNode; icon?: ReactNode }) {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="rounded-3xl border border-dashed border-ink/20 bg-white/60 p-10 text-center">
      <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-coral-50 text-coral-600" aria-hidden>{icon ?? <Compass className="h-7 w-7" />}</div>
      <p className="mt-3 font-display text-xl font-semibold">{title}</p><div className="mx-auto mt-2 max-w-md text-sm text-ink/60">{children}</div>
    </motion.div>
  )
}
export function PageHead({ title, sub, right, eyebrow }: { title: string; sub?: string; right?: ReactNode; eyebrow?: string }) {
  return (
    <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, ease: [0.2, 0.8, 0.2, 1] }} className="mb-7 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">{eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}<h1 className="font-display text-[2rem] font-bold leading-[1.05] md:text-[2.75rem]">{title}</h1>{sub && <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-ink/60">{sub}</p>}</div>{right}
    </motion.div>
  )
}

/** Fades and lifts its children in the first time they scroll into view. */
export function Reveal({ children, delay = 0, className = '', y = 22 }: { children: ReactNode; delay?: number; className?: string; y?: number }) {
  return <motion.div className={className} initial={{ opacity: 0, y }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: '-60px' }} transition={{ duration: 0.6, delay, ease: [0.2, 0.8, 0.2, 1] }}>{children}</motion.div>
}

/** Counts up to `value` once visible. `format` turns the running number into text. */
export function CountUp({ value, format = v => Math.round(v).toLocaleString('en-IN'), duration = 0.9 }: { value: number; format?: (v: number) => string; duration?: number }) {
  const ref = useRef<HTMLSpanElement>(null)
  const seen = useInView(ref, { once: true })
  const reduce = useReducedMotion()
  const from = useRef(0)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (!seen || reduce) { el.textContent = format(value); from.current = value; return }
    const c = animate(from.current, value, { duration, ease: [0.2, 0.8, 0.2, 1], onUpdate: v => { el.textContent = format(v) } })
    from.current = value
    return () => c.stop()
  }, [value, seen, reduce])
  return <span ref={ref} className="num">{format(value)}</span>
}

/** Segmented control with a sliding highlight. */
export function Segmented<T extends string>({ value, onChange, options, id, label }: { value: T; onChange: (v: T) => void; options: [T, ReactNode][]; id: string; label: string }) {
  return (
    <div className="inline-flex rounded-full border border-ink/10 bg-white p-1 shadow-soft" role="group" aria-label={label}>
      {options.map(([k, l]) => (
        <button key={k} type="button" aria-pressed={value === k} onClick={() => onChange(k)} className={`relative min-h-[36px] rounded-full px-3.5 text-sm font-semibold transition-colors ${value === k ? 'text-white' : 'text-ink/60 hover:text-ink'}`}>
          {value === k && <motion.span layoutId={`seg-${id}`} className="absolute inset-0 rounded-full bg-ink" transition={{ type: 'spring', stiffness: 420, damping: 34 }} />}
          <span className="relative z-10 inline-flex items-center gap-1.5">{l}</span>
        </button>
      ))}
    </div>
  )
}

const GRADS = ['from-coral to-sun', 'from-lagoon to-sky', 'from-indigo-500 to-sky', 'from-emerald-500 to-lagoon', 'from-fuchsia-500 to-coral']
const hash = (s: string) => [...s].reduce((a, c) => a + c.charCodeAt(0), 0)

/** Real photo (provider thumbnail) with a graceful gradient fallback. */
export function Photo({ src, name, h = 'h-36', className = '', children, zoom = false }: { src?: string | null; name: string; h?: string; className?: string; children?: ReactNode; zoom?: boolean }) {
  const [bad, setBad] = useState(false)
  const [ok, setOk] = useState(false)
  const g = GRADS[hash(name) % GRADS.length]
  useEffect(() => { setBad(false); setOk(false) }, [src])
  return (
    <div className={`relative ${h} overflow-hidden rounded-2xl bg-gradient-to-br ${g} ${className}`}>
      {src && !bad ? <img src={src} alt={name} loading="lazy" referrerPolicy="no-referrer" onLoad={() => setOk(true)} onError={() => setBad(true)} className={`h-full w-full object-cover transition duration-700 ${ok ? 'opacity-100' : 'opacity-0'} ${zoom ? 'group-hover:scale-[1.06]' : ''}`} /> :
        <div className="flex h-full items-end p-3 font-display text-lg font-semibold leading-tight text-white drop-shadow">{name}</div>}
      {children}
    </div>
  )
}

export function Stars({ v, n }: { v?: number | null; n?: number | null }) {
  if (!v) return <span className="text-xs text-ink/40">no rating</span>
  return <span className="num inline-flex items-center gap-1 text-xs font-semibold text-ink/75" title={`${v} out of 5${n ? ` from ${n.toLocaleString()} Google reviews` : ''}`}><Star className="h-3.5 w-3.5 fill-sun text-sun" aria-hidden />{v.toFixed(1)}{n ? <span className="font-normal text-ink/45">({n >= 1000 ? Math.round(n / 100) / 10 + 'k' : n})</span> : null}</span>
}

let configOnce: Promise<Json> | null = null
/** Public browser config (map token). Fetched once per page load and shared by every map. */
const getConfig = () => (configOnce ??= api('/config').catch(() => { configOnce = null; return { mapbox_token: null } }))

export type Pin = { id?: string; lat: number; lon: number; label: string; color?: string; n?: number | string; kind?: string }
const SVG_BED = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M2 4v16"/><path d="M2 8h18a2 2 0 0 1 2 2v10"/><path d="M2 17h20"/><path d="M6 8v9"/></svg>'
const SVG_FORK = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2"/><path d="M7 2v20"/><path d="M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7"/></svg>'

/** MapLibre map; Mapbox tiles when a public token is configured, else OpenStreetMap. Pins are real provider coordinates.
 *  `activeId` highlights a pin (and flies to it), `traveller` runs a dot along the route, and the locate control shows the user's own live position. */
export function MapView({ pins, route, height = 420, center, activeId, onPinClick, traveller = false, className = '' }: {
  pins: Pin[]; route?: [number, number][][]; height?: number | string; center?: [number, number]; activeId?: string | null; onPinClick?: (id: string) => void; traveller?: boolean; className?: string
}) {
  const el = useRef<HTMLDivElement>(null)
  const map = useRef<maplibregl.Map | null>(null)
  const markers = useRef<{ m: maplibregl.Marker; el: HTMLElement; pin: Pin }[]>([])
  const click = useRef(onPinClick)
  click.current = onPinClick
  const [ready, setReady] = useState(0)
  const [failed, setFailed] = useState(false)
  const reduce = useReducedMotion()

  useEffect(() => {
    if (!el.current || map.current) return
    let dead = false
    getConfig().then((cfg: Json) => {
      if (dead || !el.current) return
      const tiles = cfg.mapbox_token ? [`https://api.mapbox.com/styles/v1/mapbox/streets-v12/tiles/256/{z}/{x}/{y}@2x?access_token=${cfg.mapbox_token}`] : ['https://tile.openstreetmap.org/{z}/{x}/{y}.png']
      try {
        map.current = new maplibregl.Map({
          container: el.current, center: center ?? [0, 20], zoom: center ? 10.5 : 1.4, attributionControl: { compact: true },
          style: { version: 8, sources: { base: { type: 'raster', tiles, tileSize: 256, attribution: cfg.mapbox_token ? '© Mapbox © OpenStreetMap contributors' : '© OpenStreetMap contributors' } }, layers: [{ id: 'base', type: 'raster', source: 'base' }] },
        })
        map.current.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
        map.current.addControl(new maplibregl.FullscreenControl(), 'top-right')
        map.current.addControl(new maplibregl.GeolocateControl({ positionOptions: { enableHighAccuracy: true }, trackUserLocation: true }), 'top-right')
        map.current.addControl(new maplibregl.ScaleControl({ maxWidth: 90 }), 'bottom-left')
        setReady(r => r + 1)
      } catch { setFailed(true) }
    })
    return () => { dead = true; map.current?.remove(); map.current = null }
  }, [])

  useEffect(() => {
    const m = map.current
    if (!m) return
    markers.current.forEach(x => x.m.remove()); markers.current = []
    const b = new maplibregl.LngLatBounds()
    pins.forEach((p, i) => {
      if (typeof p.lat !== 'number' || typeof p.lon !== 'number') return
      const wrap = document.createElement('div')
      const d = document.createElement('div')
      d.className = `pl-pin${p.kind === 'hotel' ? ' is-hotel' : ''}`
      d.style.background = p.color ?? '#0fa596'
      d.style.animationDelay = `${Math.min(i, 14) * 40}ms`
      if (p.kind === 'hotel') d.innerHTML = SVG_BED
      else if (p.kind === 'meal') d.innerHTML = SVG_FORK
      else d.textContent = p.n != null ? String(p.n) : ''
      wrap.title = p.label
      wrap.appendChild(d)
      const mk = new maplibregl.Marker({ element: wrap }).setLngLat([p.lon, p.lat]).setPopup(new maplibregl.Popup({ offset: 18, closeButton: false }).setText(p.label)).addTo(m)
      if (p.id) wrap.addEventListener('click', () => click.current?.(p.id!))
      markers.current.push({ m: mk, el: d, pin: p })
      b.extend([p.lon, p.lat])
    })
    let raf = 0
    let dot: maplibregl.Marker | null = null
    const draw = () => {
      for (const id of ['route-line', 'route-casing']) if (m.getLayer(id)) m.removeLayer(id)
      if (m.getSource('route-line')) m.removeSource('route-line')
      if (route?.length) {
        route.forEach(r => r.forEach(c => b.extend(c)))
        m.addSource('route-line', { type: 'geojson', data: { type: 'FeatureCollection', features: route.map(r => ({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: r } })) } })
        m.addLayer({ id: 'route-casing', type: 'line', source: 'route-line', layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': '#ffffff', 'line-width': 7, 'line-opacity': 0.9 } })
        m.addLayer({ id: 'route-line', type: 'line', source: 'route-line', layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': '#f4553f', 'line-width': 4 } })
        const path = route[0]
        if (traveller && !reduce && path.length > 1) {  // a dot that keeps travelling the day's route
          const node = document.createElement('div'); node.className = 'pl-me'; node.style.background = '#0b1f33'
          dot = new maplibregl.Marker({ element: node }).setLngLat(path[0]).addTo(m)
          const seg = path.slice(1).map((c, i) => Math.hypot(c[0] - path[i][0], c[1] - path[i][1]))
          const total = seg.reduce((a, x) => a + x, 0) || 1
          const t0 = performance.now()
          const step = (now: number) => {
            let dist = (((now - t0) / 9000) % 1) * total
            let i = 0
            while (i < seg.length - 1 && dist > seg[i]) { dist -= seg[i]; i++ }
            const f = seg[i] ? Math.min(1, dist / seg[i]) : 0
            dot?.setLngLat([path[i][0] + (path[i + 1][0] - path[i][0]) * f, path[i][1] + (path[i + 1][1] - path[i][1]) * f])
            raf = requestAnimationFrame(step)
          }
          raf = requestAnimationFrame(step)
        }
      }
      if (!b.isEmpty()) m.fitBounds(b, { padding: 64, maxZoom: 14.5, duration: 700 })
    }
    if (m.loaded()) draw(); else m.once('load', draw)
    return () => { cancelAnimationFrame(raf); dot?.remove(); m.off('load', draw) }
  }, [pins, route, ready, traveller])

  useEffect(() => {  // highlight without rebuilding the markers
    const m = map.current
    if (!m) return
    markers.current.forEach(x => {
      const on = !!activeId && x.pin.id === activeId
      x.el.classList.toggle('is-active', on)
      x.m.getElement().style.zIndex = on ? '5' : ''
      if (on) m.easeTo({ center: [x.pin.lon, x.pin.lat], duration: 600 })
    })
  }, [activeId, ready, pins])

  if (failed) return <div style={{ height }} className="grid place-items-center rounded-3xl border border-ink/10 bg-white p-6 text-center text-sm text-ink/60">Map unavailable (WebGL is disabled in this browser). Use the list view.</div>
  return <div ref={el} style={{ height }} className={`w-full overflow-hidden rounded-3xl border border-ink/10 shadow-soft ${className}`} role="application" aria-label="Interactive map" />
}

/** Backwards-compatible alias used by older pages. */
export const Cover = Photo
