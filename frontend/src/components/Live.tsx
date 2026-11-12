import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Clock, Cloud, CloudDrizzle, CloudFog, CloudLightning, CloudRain, CloudSnow, CloudSun, Droplets, Sun, Sunrise, Sunset, Umbrella, Wind } from './icons'
import { Json } from '../api'
import { CountUp, Prov } from './ui'

/** Picks a weather glyph from the provider's condition text. */
export function WeatherIcon({ text, className = 'h-5 w-5' }: { text?: string | null; className?: string }) {
  const t = (text ?? '').toLowerCase()
  const I = /thunder|storm/.test(t) ? CloudLightning : /snow|sleet/.test(t) ? CloudSnow : /drizzle/.test(t) ? CloudDrizzle : /rain|shower/.test(t) ? CloudRain
    : /mist|fog|haze|smoke|dust/.test(t) ? CloudFog : /overcast|broken|cloud/.test(t) ? (/few|scattered|partly/.test(t) ? CloudSun : Cloud) : /clear|sun/.test(t) ? Sun : CloudSun
  return <I className={className} aria-hidden />
}

const AQI_STYLE: [number, string, string][] = [[50, '#16a34a', 'bg-emerald-50 text-emerald-800'], [100, '#65a30d', 'bg-lime-50 text-lime-800'], [200, '#d97706', 'bg-amber-50 text-amber-800'], [300, '#ea580c', 'bg-orange-50 text-orange-800'], [400, '#dc2626', 'bg-rose-50 text-rose-800'], [9999, '#7f1d1d', 'bg-rose-100 text-rose-900']]
export const aqiStyle = (v: number) => AQI_STYLE.find(([hi]) => v <= hi) ?? AQI_STYLE[5]

/** Ticking wall clock for a place, from its UTC offset. */
export function useLocalClock(offsetMin: number | null | undefined) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => { const iv = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(iv) }, [])
  if (offsetMin == null) return null
  const d = new Date(now + offsetMin * 60000)
  const p = (n: number) => String(n).padStart(2, '0')
  return { hm: `${p(d.getUTCHours())}:${p(d.getUTCMinutes())}`, s: p(d.getUTCSeconds()), day: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][d.getUTCDay()], hour: d.getUTCHours() }
}

function Tile({ children, delay = 0, className = '' }: { children: React.ReactNode; delay?: number; className?: string }) {
  return <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay, duration: 0.45, ease: [0.2, 0.8, 0.2, 1] }} className={`rounded-3xl border border-ink/[.07] bg-white p-4 shadow-soft ${className}`}>{children}</motion.div>
}

/** Live conditions for a place: weather now, air quality, local time, daylight and the 5-day forecast. Anything a provider did not return is
 *  said so in words; nothing is filled in. `highlight` marks forecast dates that belong to the trip. */
export function LivePanel({ live, place, highlight = [] }: { live: Json | null; place?: string; highlight?: string[] }) {
  const clock = useLocalClock(live?.utc_offset_min)
  if (!live) return <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" role="status" aria-label="Loading live conditions">{[0, 1, 2, 3].map(i => <div key={i} className="skeleton h-32" />)}</div>
  const wx = live.weather?.available ? live.weather : null
  const aq = live.aqi
  const fc: Json[] = live.forecast?.days ?? []
  const [aqColor, aqClass] = aq ? [aqiStyle(aq.value)[1], aqiStyle(aq.value)[2]] : ['', '']
  const night = clock ? clock.hour < 6 || clock.hour >= 20 : false
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Tile className="relative overflow-hidden !border-0 bg-gradient-to-br from-ink-700 to-ink-900 text-white">
          <div className="pointer-events-none absolute -right-6 -top-6 h-28 w-28 rounded-full bg-sky/30 blur-2xl" aria-hidden />
          <p className="flex items-center justify-between text-[11px] font-bold uppercase tracking-[.12em] text-white/55">Weather now{wx && <Prov p={wx.provenance} />}</p>
          {wx ? (<>
            <div className="mt-2 flex items-center gap-3"><WeatherIcon text={wx.summary} className="h-10 w-10 text-sun" /><p className="font-display text-5xl font-bold leading-none"><CountUp value={wx.temp_c} />°<span className="text-2xl text-white/50">C</span></p></div>
            <p className="mt-2 text-sm capitalize text-white/80">{wx.summary} · feels {Math.round(wx.feels_like_c)}°</p>
            <p className="mt-1 flex gap-3 text-xs text-white/55"><span className="flex items-center gap-1"><Droplets className="h-3 w-3" aria-hidden />{wx.humidity}%</span>{wx.wind_ms != null && <span className="flex items-center gap-1"><Wind className="h-3 w-3" aria-hidden />{Math.round(wx.wind_ms * 3.6)} km/h</span>}</p>
          </>) : <p className="mt-3 text-sm text-white/70">{live.weather?.note ?? 'Weather is not available for this place right now.'}</p>}
        </Tile>

        <Tile delay={0.06}>
          <p className="flex items-center justify-between text-[11px] font-bold uppercase tracking-[.12em] text-ink/50">Air quality{aq && <Prov p={aq.provenance} />}</p>
          {aq ? (<>
            <div className="mt-2 flex items-end gap-2"><p className="font-display text-5xl font-bold leading-none" style={{ color: aqColor }}><CountUp value={aq.value} /></p><span className={`badge mb-1 ${aqClass}`}>{aq.band}</span></div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-gradient-to-r from-emerald-400 via-amber-400 to-rose-600" aria-hidden><motion.div initial={{ left: 0 }} animate={{ left: `${Math.min(98, (aq.value / 400) * 100)}%` }} transition={{ duration: 1, ease: [0.2, 0.8, 0.2, 1] }} className="relative h-2 w-1 -translate-x-1/2 rounded bg-ink ring-2 ring-white" /></div>
            <p className="mt-2 truncate text-xs text-ink/50" title={aq.station}>Station: {aq.station ?? 'nearest available'}</p>
          </>) : <p className="mt-3 text-sm text-ink/60">No monitoring station reported data near here.</p>}
        </Tile>

        <Tile delay={0.12}>
          <p className="text-[11px] font-bold uppercase tracking-[.12em] text-ink/50">Local time{place ? ` in ${place}` : ''}</p>
          {clock ? (<>
            <p className="num mt-2 font-display text-5xl font-bold leading-none">{clock.hm}<span className="ml-1 text-xl text-ink/35">{clock.s}</span></p>
            <p className="mt-2 flex items-center gap-1.5 text-sm text-ink/60"><Clock className="h-3.5 w-3.5" aria-hidden />{clock.day} · {night ? 'night' : 'daytime'} · UTC{live.utc_offset_min >= 0 ? '+' : '−'}{Math.floor(Math.abs(live.utc_offset_min) / 60)}{Math.abs(live.utc_offset_min) % 60 ? ':' + String(Math.abs(live.utc_offset_min) % 60).padStart(2, '0') : ''}</p>
          </>) : <p className="mt-3 text-sm text-ink/60">Time zone not available.</p>}
        </Tile>

        <Tile delay={0.18}>
          <p className="text-[11px] font-bold uppercase tracking-[.12em] text-ink/50">Daylight</p>
          {live.sunrise ? (
            <div className="mt-3 space-y-2.5">
              <p className="flex items-center justify-between text-sm"><span className="flex items-center gap-2 text-ink/60"><Sunrise className="h-5 w-5 text-sun" aria-hidden />Sunrise</span><span className="num font-display text-xl font-bold">{live.sunrise}</span></p>
              <p className="flex items-center justify-between text-sm"><span className="flex items-center gap-2 text-ink/60"><Sunset className="h-5 w-5 text-coral" aria-hidden />Sunset</span><span className="num font-display text-xl font-bold">{live.sunset}</span></p>
              <p className="text-xs text-ink/45">Plan outdoor sights inside this window.</p>
            </div>
          ) : <p className="mt-3 text-sm text-ink/60">Sunrise and sunset not available.</p>}
        </Tile>
      </div>

      {fc.length > 0 && (
        <Tile delay={0.22} className="!p-3">
          <div className="mb-2 flex items-center justify-between px-1"><p className="text-[11px] font-bold uppercase tracking-[.12em] text-ink/50">Forecast</p><Prov p={live.forecast.provenance} /></div>
          <ul className="no-scrollbar flex gap-2 overflow-x-auto">
            {fc.map((d, i) => {
              const on = highlight.includes(d.date)
              return (
                <motion.li key={d.date} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 + i * 0.05 }} title={on ? 'One of your trip days' : undefined}
                  className={`min-w-[104px] flex-1 rounded-2xl p-3 text-center ${on ? 'bg-coral-50 ring-1 ring-coral/40' : 'bg-sand'}`}>
                  <p className="text-xs font-bold">{d.weekday}<span className="ml-1 font-normal text-ink/45">{d.date.slice(8)}/{d.date.slice(5, 7)}</span></p>
                  <WeatherIcon text={d.summary || d.condition} className="mx-auto my-2 h-7 w-7 text-ink/70" />
                  <p className="num text-sm font-bold">{d.max_c}°<span className="ml-1 font-normal text-ink/45">{d.min_c}°</span></p>
                  <p className={`mt-1 flex items-center justify-center gap-1 text-[11px] ${d.pop >= 0.55 ? 'font-semibold text-sky' : 'text-ink/45'}`}><Umbrella className="h-3 w-3" aria-hidden />{Math.round(d.pop * 100)}%</p>
                  {on && <p className="mt-1 text-[10px] font-bold uppercase tracking-wide text-coral-600">your trip</p>}
                </motion.li>
              )
            })}
          </ul>
        </Tile>
      )}
    </div>
  )
}
