import { Fragment, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { CloudSun, Dices, Mic, Plus, Send, Settings, Sparkles, Square, Volume2, VolumeX, X } from './icons'
import TripBot, { BotState, BotTrick } from './Bot'
import { providers } from './voice'
import { useApp } from '../store'
import { PENDING } from './TripBuilder'

/** Client-side UI commands: ONLY bare "open X" requests. Everything else goes to the agent backend, which runs the real tools. */
const SP = String.fromCharCode(92) + 's' // regex whitespace class, built explicitly to avoid string-escape pitfalls
const OPEN = `(?:open|go to|take me to|show|display)(?: me)?(?: the| my)?${SP}*`
const cmd = (words: string) => new RegExp(`^${SP}*${OPEN}(?:${words})${SP}*(?:page|tab)?[.!]?${SP}*$`, 'i')
const NAV: [RegExp, string, string][] = [
  [cmd('live guide|guide|overview'), '/workspace?tab=guide', 'Opening your live guide'],
  [cmd('map|routes?'), '/workspace?tab=map', 'Opening the map and routes'],
  [cmd('hotels?'), '/workspace?tab=hotels', 'Here are the hotels'],
  [cmd('budget|costs?'), '/workspace?tab=budget', 'Opening your budget'],
  [cmd('itinerary|schedule'), '/workspace?tab=itinerary', 'Opening your itinerary'],
  [cmd('safety|emergency info'), '/workspace?tab=safety', 'Opening safety information'],
  [cmd('bookings?|vouchers?'), '/workspace?tab=bookings', 'Opening your bookings'],
  [cmd('transport|trains?|flights?|buses'), '/transport', 'Opening ways to travel'],
  [cmd('restaurants?|food'), '/discover?tab=food', 'Opening restaurants'],
  [cmd('destinations?|attractions?|places'), '/discover', 'Opening destination discovery'],
]
const START_CHIPS = ['Plan 5 days in Paris from Mumbai, budget ₹250000', 'A relaxed weekend in Goa for two, budget ₹30000', 'Plan 6 days in Tokyo for two, budget ₹300000, love food and temples']
const PLAN_CHIPS = ['Make it cheaper', 'Find hotels under ₹10,000', 'Show historical places nearby', "Explain today's weather and pollution", 'Show the best route for these attractions']
const SURPRISE = ['Plan 4 days in Lisbon for two, budget ₹220000, love food and history', 'Plan 5 days in Bali for two, budget ₹180000, relaxed pace, nature and temples', 'Plan 3 days in Udaipur for two, budget ₹40000, history and good food',
  'Plan 5 days in Istanbul for two, budget ₹200000, markets, history and food', 'Plan 4 days in Kyoto for two, budget ₹260000, temples and gardens', 'Plan 3 days in Jaipur for two, budget ₹35000, forts and markets']
/** One friendly pointer per page, shown once per session. */
const HINTS: Record<string, string> = {
  '/discover': 'Tap any card for opening hours, photos and a map.',
  '/transport': 'Give me two places and I will compare flights, trains, buses and cabs.',
  '/trips': 'Open a saved trip and I will pick up right where we left off.',
  '/workspace': 'Tell me what to change, like “make it cheaper” or “add more sightseeing”.',
  '/profile': 'Your preferences here become the defaults for every new trip.',
}
const TRICK_LINE: Record<BotTrick, string> = { spin: 'Wheee! Round the world in one second.', jump: 'Boing! Ready for take-off.', dance: 'That is my holiday dance.', wink: 'Got your back on this trip.', love: 'Aww, thank you!', nod: 'Yes! Let\'s plan something.', peek: 'Peekaboo!' }
const speakable = (t: string) => t.replace(/[*_#`]/g, '').replace(/\n+/g, '. ').replace(/- /g, '').slice(0, 320)

/** Minimal safe formatting for assistant replies: **bold** and "- " bullets. Never injects HTML. */
function Rich({ text }: { text: string }) {
  const bold = (s: string) => s.split(/\*\*(.+?)\*\*/g).map((p, i) => (i % 2 ? <strong key={i} className="font-semibold">{p}</strong> : <Fragment key={i}>{p}</Fragment>))
  return <>{text.split('\n').map((line, i) => {
    const m = /^\s*[-•]\s+(.*)$/.exec(line)
    if (m) return <div key={i} className="flex gap-2 pl-1"><span className="mt-[0.55em] h-1 w-1 shrink-0 rounded-full bg-coral" aria-hidden /><span>{bold(m[1])}</span></div>
    return line.trim() ? <p key={i}>{bold(line)}</p> : <div key={i} className="h-2" />
  })}</>
}

export default function TripAssistant() {
  const nav = useNavigate()
  const loc = useLocation()
  const { user, messages, send, busy, speakReplies, setSpeakReplies, lastAction, plan, context, openTrip } = useApp()
  const [open, setOpen] = useState(false)
  const [hover, setHover] = useState(false)
  const [orb, setOrb] = useState<BotState>('idle')
  const [text, setText] = useState('')
  const [listening, setListening] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [voiceErr, setVoiceErr] = useState<string | null>(null)
  const [rate, setRate] = useState(1)
  const [lang, setLang] = useState('en-IN')
  const [showSettings, setShowSettings] = useState(false)
  const [greet, setGreet] = useState(false)
  const [hint, setHint] = useState<string | null>(null)
  const [quip, setQuip] = useState<string | null>(null)
  const [trick, setTrick] = useState<{ name: BotTrick; id: number } | null>(null)
  const stopListen = useRef<(() => void) | null>(null)
  const scroller = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLInputElement>(null)
  const flash = useRef<number>()
  const voice = providers.web
  const hasPlan = !!plan?.itinerary
  const [small, setSmall] = useState(typeof window !== 'undefined' && window.matchMedia('(max-width: 640px)').matches)
  useEffect(() => { const mq = window.matchMedia('(max-width: 640px)'); const f = () => setSmall(mq.matches); mq.addEventListener('change', f); return () => mq.removeEventListener('change', f) }, [])

  useEffect(() => { scroller.current?.scrollTo({ top: 1e6, behavior: 'smooth' }) }, [messages, open, busy])
  useEffect(() => { if (open) window.setTimeout(() => input.current?.focus(), 250) }, [open])
  useEffect(() => { if (!open) return; const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }; window.addEventListener('keydown', esc); return () => window.removeEventListener('keydown', esc) }, [open])
  useEffect(() => { if (lastAction?.to && !(lastAction.to === '/workspace' && loc.pathname === '/workspace')) nav(lastAction.to) }, [lastAction])
  useEffect(() => {  // friendly one-time greeting bubble
    let seen = false
    try { seen = sessionStorage.getItem('plarno_greeted') === '1' } catch { /* ignore */ }
    if (seen || user) return  // signed-in users already know TRIP: no intro bubble over their content
    const show = window.setTimeout(() => setGreet(true), 1800)
    const hide = window.setTimeout(() => setGreet(false), 11000)  // never lingers over the page
    return () => { window.clearTimeout(show); window.clearTimeout(hide) }
  }, [user])
  useEffect(() => {  // a trip request typed before signing in is resumed after login
    if (!user) return
    let p: string | null = null
    try { p = sessionStorage.getItem(PENDING); sessionStorage.removeItem(PENDING) } catch { /* ignore */ }
    if (p) { nav('/workspace'); void send(p) }
  }, [user])
  useEffect(() => {
    if (listening) setOrb('listening')
    else if (busy) setOrb('thinking')
    else if (speaking) setOrb('speaking')
    else if (!flash.current) setOrb(hover ? 'hover' : 'idle')
  }, [listening, busy, speaking, hover])
  useEffect(() => {  // the bot perks up on every page change and offers one pointer per page
    setHint(null)
    if (loc.pathname !== '/' && !busy) pulse('acting', 900)
    const h = HINTS[loc.pathname]
    if (!h || open) return
    let seen = false
    try { seen = sessionStorage.getItem('plarno_hint_' + loc.pathname) === '1' } catch { /* ignore */ }
    if (seen || (loc.pathname === '/workspace' && !hasPlan)) return
    const show = window.setTimeout(() => { setHint(h); try { sessionStorage.setItem('plarno_hint_' + loc.pathname, '1') } catch { /* ignore */ } }, 1400)
    const hide = window.setTimeout(() => setHint(null), 9000)
    return () => { window.clearTimeout(show); window.clearTimeout(hide) }
  }, [loc.pathname])

  useEffect(() => { if (!greet && !hint) return; const off = () => { setGreet(false); setHint(null) }; window.addEventListener('keydown', off, { once: true }); window.addEventListener('scroll', off, { once: true }); return () => { window.removeEventListener('keydown', off); window.removeEventListener('scroll', off) } }, [greet, hint])
  const dismissGreeting = () => { setGreet(false); setHint(null); try { sessionStorage.setItem('plarno_greeted', '1') } catch { /* ignore */ } }
  function pulse(s: BotState, ms = 1800) {
    setOrb(s); window.clearTimeout(flash.current)
    flash.current = window.setTimeout(() => { flash.current = undefined; setOrb('idle') }, ms)
  }
  const speak = (t: string) => {
    if (!voice.supportsTTS) return
    setSpeaking(true); voice.speak(speakable(t), { rate, lang, onEnd: () => setSpeaking(false) })
  }
  const celebrate = (name: BotTrick) => setTrick({ name, id: Date.now() })

  async function submit(raw: string, viaVoice = false) {
    const msg = raw.trim()
    if (!msg || busy) return
    setText(''); dismissGreeting(); setQuip(null)
    const hit = NAV.find(([re]) => re.test(msg))
    if (hit) {
      setOrb('acting'); nav(hit[1]); pulse('success')
      if (speakReplies || viaVoice) speak(hit[2])
      return
    }
    if (!user) {
      try { sessionStorage.setItem(PENDING, msg) } catch { /* ignore */ }
      pulse('success'); setVoiceErr('Sign in (or create a free account) and I will plan that for you right away.'); nav('/auth'); return
    }
    setVoiceErr(null)
    const hadPlan = hasPlan
    const reply = await send(msg)
    if (reply === null || reply.startsWith('⚠')) pulse('error', 2500)
    else { pulse('success'); if (!hadPlan) celebrate('dance'); if (speakReplies || viaVoice) speak(reply) }
  }

  function toggleMic() {
    setVoiceErr(null); dismissGreeting()
    if (listening) { stopListen.current?.(); return }
    voice.stopSpeaking(); setSpeaking(false); setOpen(true)
    setListening(true)
    stopListen.current = voice.listen({
      lang,
      onResult: (t, final) => { setText(t); if (final) { stopListen.current?.(); setSpeakReplies(true); void submit(t, true) } },
      onEnd: () => setListening(false),
      onError: m => { setVoiceErr(m); setListening(false); pulse('error', 2500) },
    })
  }

  const quick: [string, typeof Sparkles, () => void][] = [
    ['Plan a trip', Sparkles, () => { setOpen(true) }],
    ...(hasPlan ? [[`Weather in ${context.destination}`, CloudSun, () => { setOpen(true); void submit("Explain today's weather and pollution") }] as [string, typeof Sparkles, () => void]] : []),
    ['Surprise me', Dices, () => { setOpen(true); void submit(SURPRISE[Math.floor(Math.random() * SURPRISE.length)]) }],
  ]
  const status = listening ? 'Listening…' : busy ? 'Planning with live data…' : speaking ? 'Speaking…' : 'Your travel buddy · ask me anything'

  return (
    <div className="pointer-events-none fixed bottom-3 right-3 z-50 flex flex-col items-end gap-2 sm:bottom-5 sm:right-5" style={{ maxWidth: 'calc(100vw - 1.5rem)' }}>
      <AnimatePresence>
        {open && (
          <motion.section initial={{ opacity: 0, y: 24, scale: 0.94 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 24, scale: 0.94 }} transition={{ type: 'spring', stiffness: 380, damping: 32 }} style={{ transformOrigin: 'bottom right' }}
            className="pointer-events-auto flex h-[min(620px,calc(100dvh-7rem))] w-[min(410px,calc(100vw-1.5rem))] flex-col overflow-hidden rounded-[1.75rem] border border-ink/10 bg-white shadow-lift"
            aria-label="TRIP assistant chat">
            <header className="relative flex items-center justify-between overflow-hidden bg-ink-900 px-3 py-2 text-white">
              <div className="pointer-events-none absolute -left-8 -top-10 h-32 w-32 rounded-full bg-coral/40 blur-2xl" aria-hidden />
              <div className="pointer-events-none absolute -bottom-12 right-10 h-28 w-28 rounded-full bg-lagoon/40 blur-2xl" aria-hidden />
              <div className="relative flex min-w-0 items-center gap-1">
                <TripBot state={orb} size={68} interactive trick={trick} say={false} onTrick={t => setQuip(TRICK_LINE[t])} />
                <div className="min-w-0"><p className="font-display text-xl font-bold leading-none">TRIP</p><p className="mt-1 truncate text-[11px] text-white/70" aria-live="polite">{status}</p></div>
              </div>
              <div className="relative flex shrink-0 items-center">
                {speaking && <button className="mr-1 flex items-center gap-1 rounded-full bg-white/20 px-2.5 py-1.5 text-xs font-semibold hover:bg-white/30" onClick={() => { voice.stopSpeaking(); setSpeaking(false) }}><Square className="h-3 w-3 fill-current" aria-hidden />Stop</button>}
                {messages.length > 0 && <button aria-label="Start a new trip" title="Start a new trip" disabled={busy} className="grid h-10 w-10 place-items-center rounded-full hover:bg-white/15 disabled:opacity-40" onClick={() => { void openTrip(null); nav('/workspace') }}><Plus className="h-[18px] w-[18px]" /></button>}
                <button aria-label={speakReplies ? 'Turn spoken replies off' : 'Turn spoken replies on'} aria-pressed={speakReplies} title="Spoken replies" disabled={!voice.supportsTTS} onClick={() => { setSpeakReplies(!speakReplies); if (speakReplies) { voice.stopSpeaking(); setSpeaking(false) } }} className="grid h-10 w-10 place-items-center rounded-full hover:bg-white/15 disabled:opacity-40">{speakReplies ? <Volume2 className="h-[18px] w-[18px]" /> : <VolumeX className="h-[18px] w-[18px]" />}</button>
                <button aria-label="Voice settings" aria-expanded={showSettings} className="grid h-10 w-10 place-items-center rounded-full hover:bg-white/15" onClick={() => setShowSettings(s => !s)}><Settings className="h-[18px] w-[18px]" /></button>
                <button aria-label="Collapse" className="grid h-10 w-10 place-items-center rounded-full hover:bg-white/15" onClick={() => setOpen(false)}><X className="h-[18px] w-[18px]" /></button>
              </div>
            </header>
            <AnimatePresence>
              {showSettings && (
                <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden border-b border-ink/5 bg-sand text-xs">
                  <div className="space-y-2 px-4 py-3">
                    <label className="flex items-center justify-between gap-3">Speed {rate.toFixed(1)}×<input type="range" min={0.7} max={1.4} step={0.1} value={rate} onChange={e => setRate(+e.target.value)} className="h-8 accent-coral" /></label>
                    <label className="flex items-center justify-between gap-3">Voice language
                      <select className="rounded-lg border border-ink/15 bg-white px-2 py-1.5" value={lang} onChange={e => setLang(e.target.value)}>
                        <option value="en-IN">English (India)</option><option value="en-US">English (US)</option><option value="en-GB">English (UK)</option><option value="hi-IN">हिन्दी (voice input)</option><option value="fr-FR">Français</option><option value="es-ES">Español</option><option value="de-DE">Deutsch</option><option value="ja-JP">日本語</option>
                      </select></label>
                    <p className="text-ink/50">Voice uses your browser ({voice.name}). {!voice.supportsSTT && 'Speech input is not supported in this browser: try Chrome or Edge, or just type.'} Replies are in English.</p>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
            <div ref={scroller} className="flex-1 space-y-3 overflow-y-auto bg-sand-100 px-4 py-4 text-sm leading-relaxed" aria-live="polite">
              {messages.length === 0 && (
                <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
                  <div className="rounded-2xl rounded-bl-md bg-white p-3.5 shadow-soft">Hi, I'm <b>TRIP</b>! Tell me where you want to go anywhere in the world, with your budget and what you love. Type it, or tap the mic and just talk. <span className="text-ink/50">Psst: click me for a trick.</span></div>
                  <div className="flex flex-col gap-2">{START_CHIPS.map((c, i) => <motion.button key={c} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 + i * 0.07 }} onClick={() => void submit(c)} className="rounded-2xl border border-ink/10 bg-white px-3.5 py-2.5 text-left text-[13px] transition hover:border-coral/60 hover:text-coral-600">{c}</motion.button>)}</div>
                </motion.div>
              )}
              {messages.map((m, i) => (
                <motion.div key={i} initial={i >= messages.length - 2 ? { opacity: 0, y: 10, scale: 0.97 } : false} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.25 }}
                  className={m.role === 'user' ? 'ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-ink px-3.5 py-2.5 text-white' : 'mr-6 space-y-1 rounded-2xl rounded-bl-md bg-white px-3.5 py-2.5 shadow-soft'}>
                  {m.role === 'user' ? m.content : <Rich text={m.content} />}
                </motion.div>
              ))}
              {quip && !busy && <motion.div key={quip} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="mr-6 w-fit rounded-2xl rounded-bl-md bg-coral-50 px-3.5 py-2 text-coral-700">{quip}</motion.div>}
              {busy && <div className="mr-6 flex items-center gap-2 rounded-2xl rounded-bl-md bg-white px-3.5 py-3 text-ink/60 shadow-soft" role="status"><span className="inline-flex gap-1" aria-hidden><i className="h-2 w-2 animate-bounce rounded-full bg-coral" /><i className="h-2 w-2 animate-bounce rounded-full bg-sun [animation-delay:.15s]" /><i className="h-2 w-2 animate-bounce rounded-full bg-lagoon [animation-delay:.3s]" /></span>Working with live data… new cities can take up to ~30 s.</div>}
              {messages.length > 0 && !busy && <div className="flex flex-wrap gap-1.5 pt-1">{(hasPlan ? PLAN_CHIPS : START_CHIPS).slice(0, 4).map(c => <button key={c} onClick={() => void submit(c)} className="chip !min-h-[32px] !px-2.5 !py-1 !text-xs">{c}</button>)}</div>}
            </div>
            {voiceErr && <p role="alert" className="mx-3 mb-1 mt-1 rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">{voiceErr}</p>}
            {listening && <div className="mx-3 mb-1 mt-1 flex items-center gap-2 rounded-xl bg-sky-50 px-3 py-2 text-xs text-sky-800" role="status"><span className="flex items-end gap-0.5" aria-hidden>{[0, 1, 2, 3, 4].map(i => <i key={i} className="w-1 animate-bounce rounded bg-sky" style={{ height: 8 + (i % 3) * 5, animationDelay: `${i * 0.1}s` }} />)}</span>Listening… speak now{text && <span className="truncate text-sky-900">“{text}”</span>}</div>}
            <form className="flex items-center gap-2 border-t border-ink/5 bg-white p-3" onSubmit={e => { e.preventDefault(); void submit(text) }}>
              <button type="button" onClick={toggleMic} disabled={!voice.supportsSTT} title={voice.supportsSTT ? 'Talk to TRIP' : 'Speech input is not supported in this browser'}
                aria-pressed={listening} aria-label={listening ? 'Stop listening' : 'Start voice input'}
                className={`grid h-11 w-11 shrink-0 place-items-center rounded-full transition ${listening ? 'animate-pulse bg-sky text-white' : 'bg-lagoon-50 text-lagoon-700 hover:bg-lagoon/20'} disabled:opacity-40`}><Mic className="h-5 w-5" /></button>
              <input ref={input} value={text} onChange={e => setText(e.target.value)} placeholder={listening ? 'Listening…' : 'Ask TRIP anything…'} aria-label="Message TRIP" className="min-w-0 flex-1 rounded-full border border-ink/10 bg-sand px-4 py-2.5 text-sm outline-none transition focus:border-coral focus:ring-4 focus:ring-coral/15" />
              <button disabled={busy || !text.trim()} aria-label="Send message" className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-coral text-white shadow-glow transition hover:bg-coral-600 active:scale-95 disabled:opacity-40 disabled:shadow-none"><Send className="h-[18px] w-[18px]" /></button>
            </form>
          </motion.section>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {(greet || hint) && !open && (
          <motion.div key={greet ? 'greet' : 'hint'} initial={{ opacity: 0, y: 10, scale: 0.9 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} className="pointer-events-auto relative mr-2 max-w-[260px] rounded-2xl rounded-br-md border border-ink/[.06] bg-white p-3.5 text-sm shadow-lift" role="status">
            <button aria-label="Dismiss" className="absolute -right-3 -top-3 grid h-9 w-9 place-items-center rounded-full bg-ink text-white shadow-soft" onClick={dismissGreeting}><X className="h-4 w-4" /></button>
            {greet ? (<>
              <p><b>Hi, I'm TRIP!</b> Where should we go next? Type it, or tap the mic and talk to me.</p>
              <div className="mt-2.5 flex gap-2"><button className="btn btn-primary btn-sm" onClick={() => { dismissGreeting(); setOpen(true) }}>Chat</button><button className="btn btn-ghost btn-sm" onClick={toggleMic} disabled={!voice.supportsSTT}><Mic className="h-3.5 w-3.5" aria-hidden />Talk</button></div>
            </>) : <p className="pr-3">{hint}</p>}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="pointer-events-auto flex items-end gap-2" onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}>
        <AnimatePresence>
          {hover && !open && !small && !greet && !hint && (
            <motion.div initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 16 }} className="mb-3 flex flex-col items-end gap-1.5">
              {quick.map(([l, Icon, fn], i) => <motion.button key={l} initial={{ opacity: 0, x: 14 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }} onClick={fn} className="flex min-h-[36px] items-center gap-2 whitespace-nowrap rounded-full border border-ink/10 bg-white px-3.5 text-[13px] font-semibold shadow-soft transition hover:border-coral hover:text-coral-600"><Icon className="h-3.5 w-3.5 text-coral" aria-hidden />{l}</motion.button>)}
            </motion.div>
          )}
        </AnimatePresence>
        <motion.button onClick={() => { dismissGreeting(); setOpen(o => !o) }} onFocus={() => setHover(true)} onBlur={() => setHover(false)} whileHover={{ scale: 1.06 }} whileTap={{ scale: 0.94 }}
          aria-label={open ? 'Collapse TRIP assistant' : 'Open TRIP assistant'} aria-expanded={open}
          className="relative rounded-full bg-white/95 p-0.5 shadow-lift ring-1 ring-ink/10 backdrop-blur">
          {busy && !open && <span className="absolute inset-0 animate-ping rounded-full bg-coral/30" aria-hidden />}
          <TripBot state={orb} size={open ? 60 : small ? 76 : 100} trick={open ? null : trick} say={false} />
        </motion.button>
      </div>
    </div>
  )
}
