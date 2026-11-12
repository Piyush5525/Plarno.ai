import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion, useScroll, useTransform } from 'framer-motion'
import { ArrowRight, CloudSun, Compass, Globe, Map as MapIcon, Mic, Plane, Route, ShieldCheck, Sparkles, Wallet, Wind, Hand } from '../components/icons'
import TripBot, { BotState } from '../components/Bot'
import TripBuilder from '../components/TripBuilder'
import { CountUp, Prov, Reveal } from '../components/ui'
import { WeatherIcon } from '../components/Live'
import { api, Json } from '../api'

const FEATURES: [typeof Globe, string, string, string][] = [
  [Globe, 'Anywhere in the world', 'Real attractions, restaurants and hotels for any city or small town, with coordinates, ratings, photos and nightly rates for your dates.', 'md:col-span-2'],
  [Plane, 'Live flight fares', 'Real Google Flights fares from your nearest airport, folded into the total cost.', ''],
  [Route, 'Routes that make sense', 'Sights are grouped by area, ordered to cut backtracking and drawn on a real road map.', ''],
  [CloudSun, 'A live guide, not a static plan', 'Forecast matched to each day, air quality, opening hours and warnings before they become problems.', 'md:col-span-2'],
  [Wallet, 'A budget you can trust', 'Every number is labelled live, estimated or demo. Go over and Plarno re-plans, telling you what it relaxed.', ''],
  [Mic, 'Talk to TRIP', 'Type or speak. TRIP runs real searches, changes your plan and explains why.', ''],
  [ShieldCheck, 'You stay in control', 'Nothing is booked for you. You approve every change and book on the provider\'s own site.', 'md:col-span-4'],
]
const STEPS: [string, string][] = [['Tell us about the trip', 'Fill the short form or just say it to TRIP in your own words.'], ['Agents team up', 'Places, hotels, flights, weather and routes are gathered and scored together.'], ['Review and tweak', 'Swap hotels, reorder days, change the pace. Costs and routes update at once.'], ['Book at the source', 'Jump to the airline or hotel with your choices ready.']]
const CITIES: [string, number, number][] = [['Paris', 48.8566, 2.3522], ['Tokyo', 35.6762, 139.6503], ['New York', 40.7128, -74.006], ['Dubai', 25.2048, 55.2708]]
const MARQUEE = ['Paris', 'Kyoto', 'Bali', 'Lisbon', 'Jaipur', 'New York', 'Istanbul', 'Cape Town', 'Goa', 'Rome', 'Bangkok', 'Reykjavik', 'Singapore', 'Marrakech', 'Sydney', 'Udaipur']

function localTime(offsetMin: number | null | undefined, now: number) {
  if (offsetMin == null) return null
  const d = new Date(now + offsetMin * 60000)
  return `${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}`
}

/** Real conditions for four cities, fetched from the same live providers the planner uses. Hidden entirely if none respond. */
function LiveCities() {
  const [rows, setRows] = useState<(Json | null)[]>(CITIES.map(() => null))
  const [now, setNow] = useState(Date.now())
  const [failed, setFailed] = useState(0)
  useEffect(() => {
    let dead = false
    CITIES.forEach(([, lat, lon], i) => api(`/live?lat=${lat}&lon=${lon}`).then(r => { if (!dead) setRows(x => x.map((v, k) => (k === i ? r : v))) }).catch(() => { if (!dead) setFailed(f => f + 1) }))
    const iv = window.setInterval(() => setNow(Date.now()), 30000)
    return () => { dead = true; window.clearInterval(iv) }
  }, [])
  if (failed === CITIES.length) return null
  return (
    <section className="mx-auto max-w-7xl px-4 pt-20">
      <Reveal><p className="eyebrow">Live right now</p><h2 className="h-section mt-2 max-w-2xl">The same live data that shapes <span className="font-serif font-normal italic text-coral">your</span> plan.</h2>
        <p className="mt-3 max-w-2xl text-ink/60">These readings are fetched as you load this page. Tap a city to explore it.</p></Reveal>
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {CITIES.map(([name], i) => {
          const r = rows[i]; const wx = r?.weather?.available ? r.weather : null
          return (
            <Reveal key={name} delay={i * 0.06}>
              <Link to={`/discover?city=${encodeURIComponent(name)}`} className="card card-hover group block !p-5">
                <div className="flex items-start justify-between"><div><p className="font-display text-xl font-bold">{name}</p><p className="num mt-0.5 text-xs text-ink/50">{r ? `${localTime(r.utc_offset_min, now) ?? '--:--'} local time` : 'Checking…'}</p></div>
                  <div className="grid h-11 w-11 place-items-center rounded-2xl bg-sky-50 text-sky transition-transform duration-500 group-hover:rotate-12 group-hover:scale-110">{wx ? <WeatherIcon text={wx.summary} className="h-6 w-6" /> : <CloudSun className="h-6 w-6 opacity-40" />}</div></div>
                {!r ? <div className="skeleton mt-4 h-12" /> : (
                  <div className="mt-4 flex items-end justify-between gap-2">
                    <p className="font-display text-4xl font-bold leading-none">{wx ? <><CountUp value={wx.temp_c} />°</> : '—'}</p>
                    <div className="text-right text-xs text-ink/60"><p className="capitalize">{wx?.summary ?? 'Weather unavailable'}</p>{r.aqi && <p className="mt-0.5 flex items-center justify-end gap-1"><Wind className="h-3 w-3" aria-hidden />AQI {r.aqi.value} · {r.aqi.band}</p>}</div>
                  </div>)}
                <div className="mt-4 flex items-center justify-between border-t border-ink/[.06] pt-3">{wx ? <Prov p={wx.provenance} /> : <span />}<span className="flex items-center gap-1 text-xs font-semibold text-coral-600 opacity-0 transition group-hover:opacity-100">Explore<ArrowRight className="h-3.5 w-3.5" /></span></div>
              </Link>
            </Reveal>
          )
        })}
      </div>
    </section>
  )
}

export default function Landing() {
  const [bot, setBot] = useState<BotState>('idle')
  const hero = useRef<HTMLElement>(null)
  const { scrollYProgress } = useScroll({ target: hero, offset: ['start start', 'end start'] })
  const botY = useTransform(scrollYProgress, [0, 1], [0, 90])
  const glowY = useTransform(scrollYProgress, [0, 1], [0, -120])
  const word = { hidden: { opacity: 0, y: 28 }, show: { opacity: 1, y: 0, transition: { duration: 0.7, ease: [0.2, 0.8, 0.2, 1] } } }

  return (
    <>
      <section ref={hero} className="relative overflow-hidden bg-ink-900 text-white">
        <motion.div style={{ y: glowY }} className="pointer-events-none absolute inset-0" aria-hidden>
          <div className="absolute -right-32 -top-32 h-[560px] w-[560px] animate-aurora rounded-full bg-coral/30 blur-[120px]" />
          <div className="absolute -left-40 top-1/3 h-[520px] w-[520px] animate-aurora rounded-full bg-lagoon/25 blur-[130px] [animation-delay:-5s]" />
          <div className="absolute bottom-0 left-1/2 h-[360px] w-[360px] animate-aurora rounded-full bg-sky/20 blur-[110px] [animation-delay:-9s]" />
        </motion.div>
        <div className="grid-bg pointer-events-none absolute inset-0 [mask-image:radial-gradient(ellipse_at_center,black,transparent_75%)]" aria-hidden />

        <div className="relative mx-auto grid max-w-7xl items-center gap-4 px-4 pb-8 pt-12 md:grid-cols-[1.15fr_.85fr] md:pt-20">
          <motion.div initial="hidden" animate="show" transition={{ staggerChildren: 0.09 }}>
            <motion.p variants={word} className="glass mb-6 inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-[13px] font-medium text-white/90"><span className="relative flex h-2 w-2"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" /><span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" /></span>Live data from Google Maps, Flights and Hotels</motion.p>
            <h1 className="font-display text-[3.1rem] font-extrabold leading-[.95] tracking-tightest sm:text-7xl lg:text-[5.4rem]">
              <motion.span variants={word} className="block">Your journey,</motion.span>
              <motion.span variants={word} className="block"><span className="text-gradient pr-2 font-serif font-normal italic tracking-normal">intelligently</span></motion.span>
              <motion.span variants={word} className="block">planned.</motion.span>
            </h1>
            <motion.p variants={word} className="mt-6 max-w-xl text-lg leading-relaxed text-white/70">Tell Plarno where you want to go. It finds real places, hotels and flights, builds a day-by-day route on a map, keeps it inside your budget and watches the weather for you.</motion.p>
            <motion.div variants={word} className="mt-8 flex flex-wrap gap-3">
              <a href="#plan" className="btn btn-primary !px-7 !py-3.5 text-base">Plan my trip<ArrowRight className="h-4 w-4" aria-hidden /></a>
              <Link to="/discover" className="btn btn-glass !px-7 !py-3.5 text-base"><Compass className="h-4 w-4" aria-hidden />Explore a city</Link>
            </motion.div>
            <motion.ul variants={word} className="mt-9 flex flex-wrap gap-x-6 gap-y-2 text-sm text-white/55">
              {['No made-up places or prices', 'Any city or small town', 'Free to try'].map(t => <li key={t} className="flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-coral" aria-hidden />{t}</li>)}
            </motion.ul>
          </motion.div>

          <motion.div style={{ y: botY }} className="relative mx-auto flex h-[340px] w-full max-w-[420px] items-center justify-center md:h-[440px]">
            <div className="absolute h-64 w-64 rounded-full bg-gradient-to-br from-coral/40 to-lagoon/30 blur-3xl md:h-80 md:w-80" aria-hidden />
            <div className="absolute h-[300px] w-[300px] rounded-full border border-white/10 md:h-[380px] md:w-[380px]" aria-hidden />
            <div className="absolute h-[230px] w-[230px] rounded-full border border-dashed border-white/10 md:h-[290px] md:w-[290px]" aria-hidden />
            <motion.div initial={{ opacity: 0, scale: 0.7 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.8, delay: 0.25, ease: [0.2, 0.8, 0.2, 1] }} onMouseEnter={() => setBot('hover')} onMouseLeave={() => setBot('idle')}>
              <div className="animate-floaty"><TripBot state={bot} size={330} interactive /></div>
            </motion.div>
            <motion.div initial={{ opacity: 0, x: -30 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.9 }} className="glass absolute left-0 top-6 hidden items-center gap-2.5 rounded-2xl px-3.5 py-2.5 text-sm sm:flex"><span className="grid h-8 w-8 place-items-center rounded-xl bg-lagoon/90"><Route className="h-4 w-4" aria-hidden /></span><span><span className="block font-semibold leading-tight">Road routes</span><span className="text-xs text-white/60">drawn day by day</span></span></motion.div>
            <motion.div initial={{ opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 1.05 }} className="glass absolute bottom-10 right-0 hidden items-center gap-2.5 rounded-2xl px-3.5 py-2.5 text-sm sm:flex"><span className="grid h-8 w-8 place-items-center rounded-xl bg-coral"><CloudSun className="h-4 w-4" aria-hidden /></span><span><span className="block font-semibold leading-tight">Live forecast</span><span className="text-xs text-white/60">matched to each day</span></span></motion.div>
            <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.6 }} className="absolute -bottom-1 flex items-center gap-1.5 text-xs text-white/45"><Hand className="h-3.5 w-3.5" aria-hidden />Click TRIP for a trick, drag to spin</motion.p>
          </motion.div>
        </div>

        <div className="mask-fade-x relative overflow-hidden border-y border-white/[.07] py-4" aria-label="Popular destinations">
          <div className="flex w-max animate-marquee gap-3 hover:[animation-play-state:paused]">
            {[...MARQUEE, ...MARQUEE].map((c, i) => <Link key={i} to={`/discover?city=${encodeURIComponent(c)}`} tabIndex={i >= MARQUEE.length ? -1 : 0} aria-hidden={i >= MARQUEE.length} className="flex min-h-[40px] items-center gap-2 whitespace-nowrap rounded-full border border-white/10 bg-white/[.04] px-4 text-sm text-white/70 transition hover:border-coral/60 hover:bg-coral/10 hover:text-white"><MapIcon className="h-3.5 w-3.5 text-coral" aria-hidden />{c}</Link>)}
          </div>
        </div>

        <div id="plan" className="relative mx-auto max-w-5xl scroll-mt-24 px-4 pb-20 pt-12">
          <Reveal><p className="mb-4 flex items-center justify-center gap-2 text-center text-sm font-medium text-white/60"><Sparkles className="h-4 w-4 text-sun" aria-hidden />Start here. It takes under a minute.</p><TripBuilder /></Reveal>
        </div>
      </section>

      <LiveCities />

      <section className="mx-auto max-w-7xl px-4 pt-24">
        <Reveal><p className="eyebrow">Why Plarno</p><h2 className="h-section mt-2 max-w-3xl">Not a chatbot. A <span className="font-serif font-normal italic text-coral">travel team</span> that shares one plan.</h2>
          <p className="mt-3 max-w-2xl text-ink/60">Specialist agents work on the same trip, so a change in one place updates everything that depends on it.</p></Reveal>
        <div className="mt-10 grid gap-4 md:grid-cols-4">
          {FEATURES.map(([Icon, t, d, span], i) => (
            <Reveal key={t} delay={(i % 4) * 0.05} className={span}>
              <div className="card card-hover group relative h-full overflow-hidden !p-6">
                <div className="absolute -right-10 -top-10 h-32 w-32 rounded-full bg-coral/[.07] transition-transform duration-500 group-hover:scale-[2.2]" aria-hidden />
                <div className="icon-tile relative bg-ink text-white transition-colors duration-300 group-hover:bg-coral"><Icon className="h-5 w-5" aria-hidden /></div>
                <p className="relative mt-5 font-display text-xl font-bold">{t}</p><p className="relative mt-1.5 text-sm leading-relaxed text-ink/60">{d}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 pt-24">
        <Reveal><p className="eyebrow">How it works</p><h2 className="h-section mt-2">From idea to itinerary in four steps.</h2></Reveal>
        <ol className="relative mt-10 grid gap-5 md:grid-cols-4">
          <motion.div aria-hidden initial={{ scaleX: 0 }} whileInView={{ scaleX: 1 }} viewport={{ once: true, margin: '-80px' }} transition={{ duration: 1.2, ease: [0.2, 0.8, 0.2, 1] }} className="absolute left-0 right-0 top-7 hidden h-px origin-left bg-gradient-to-r from-coral via-sun to-lagoon md:block" />
          {STEPS.map(([t, d], i) => (
            <Reveal key={t} delay={i * 0.12}><li className="relative">
              <span className="num relative grid h-14 w-14 place-items-center rounded-2xl bg-ink font-display text-xl font-bold text-white shadow-lift">{i + 1}</span>
              <p className="mt-4 font-display text-lg font-bold">{t}</p><p className="mt-1 text-sm leading-relaxed text-ink/60">{d}</p></li></Reveal>
          ))}
        </ol>
      </section>

      <section className="mx-auto max-w-7xl px-4 pt-24">
        <Reveal>
          <div className="relative overflow-hidden rounded-[2.5rem] bg-ink-900 px-6 py-14 text-center text-white md:px-16 md:py-20">
            <div className="pointer-events-none absolute -left-20 -top-24 h-72 w-72 animate-aurora rounded-full bg-coral/35 blur-[100px]" aria-hidden />
            <div className="pointer-events-none absolute -bottom-24 -right-16 h-72 w-72 animate-aurora rounded-full bg-lagoon/30 blur-[100px] [animation-delay:-6s]" aria-hidden />
            <h2 className="relative font-display text-4xl font-extrabold leading-none tracking-tightest md:text-6xl">Ready when <span className="text-gradient font-serif font-normal italic tracking-normal">you</span> are.</h2>
            <p className="relative mx-auto mt-4 max-w-lg text-white/65">Create a free account, then plan your first trip in under a minute.</p>
            <div className="relative mt-8 flex flex-wrap justify-center gap-3"><Link to="/auth?mode=register" className="btn btn-primary !px-8 !py-3.5 text-base">Get started free<ArrowRight className="h-4 w-4" aria-hidden /></Link><Link to="/discover" className="btn btn-glass !px-8 !py-3.5 text-base">Explore a city</Link></div>
          </div>
        </Reveal>
      </section>
    </>
  )
}
