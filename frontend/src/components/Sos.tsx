import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, Check, MapPin, Phone, Send, Siren, X } from './icons'
import { api, Json } from '../api'
import { useApp } from '../store'

type Phase = 'idle' | 'locating' | 'sending' | 'sharing' | 'error'
const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

/** Emergency button + dialog. Pressing "Send alert" (and only that) reads the device location and sends it, with the person's name and the
 *  emergency contact saved in their profile, to the alert channel; the location then keeps updating while this page stays open. */
export default function Sos({ compact = false }: { compact?: boolean }) {
  const { user, plan, context } = useApp()
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState<Json | null>(null)
  const [phase, setPhase] = useState<Phase>('idle')
  const [msg, setMsg] = useState<string | null>(null)
  const [place, setPlace] = useState<string | null>(null)
  const [left, setLeft] = useState(0)
  const watch = useRef<number | null>(null)
  const last = useRef(0)
  const closeRef = useRef<HTMLButtonElement>(null)

  const stopWatch = () => { if (watch.current != null) { navigator.geolocation.clearWatch(watch.current); watch.current = null } }
  useEffect(() => stopWatch, [])
  useEffect(() => {
    if (!open || !user) return
    api('/sos/status').then(s => { setStatus(s); if (s.active && phase === 'idle') { setPhase('sharing'); setLeft(s.seconds_left) } }).catch(() => setStatus(null))
    closeRef.current?.focus()
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('keydown', esc)
    return () => document.removeEventListener('keydown', esc)
  }, [open, user])
  useEffect(() => {
    if (phase !== 'sharing') return
    const iv = window.setInterval(() => setLeft(s => { if (s <= 1) { stopWatch(); setPhase('idle'); setMsg('Sharing ended after 15 minutes. Send again if you still need help.'); return 0 } return s - 1 }), 1000)
    return () => window.clearInterval(iv)
  }, [phase])
  if (!user) return null

  const numbers: [string, string][] = Object.entries((plan?.safety?.emergency_contacts ?? {}) as Record<string, string>)
  const contact = status?.contact

  function send(test: boolean) {
    setMsg(null)
    if (!('geolocation' in navigator)) { setPhase('error'); setMsg('This browser cannot share a location. Call the emergency number instead.'); return }
    setPhase('locating')
    navigator.geolocation.getCurrentPosition(async pos => {
      setPhase('sending')
      const body = { lat: pos.coords.latitude, lon: pos.coords.longitude, accuracy_m: pos.coords.accuracy, test }
      try {
        const r = await api('/sos', { body })
        setPlace(r.place); setLeft(r.minutes * 60); setPhase('sharing'); last.current = Date.now()
        stopWatch()
        watch.current = navigator.geolocation.watchPosition(p => {  // keep the live pin moving, at most every 15 s
          if (Date.now() - last.current < 15000) return
          last.current = Date.now()
          api('/sos/update', { body: { lat: p.coords.latitude, lon: p.coords.longitude } }).catch(() => { /* next fix will retry */ })
        }, () => { /* keep the last known position */ }, { enableHighAccuracy: true, maximumAge: 10000 })
      } catch (e) { setPhase('error'); setMsg((e as Error).message) }
    }, e => {
      setPhase('error')
      setMsg(e.code === e.PERMISSION_DENIED ? 'Location permission was denied. Allow location for this site, or call the emergency number below.' : 'Could not get your location. Check that location is turned on, or call the emergency number below.')
    }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 })
  }
  async function stop() {
    stopWatch()
    try { await api('/sos/stop', { body: {} }) } catch { /* nothing more to do */ }
    setPhase('idle'); setLeft(0); setMsg('Stopped. Your contact was told you are safe.')
  }
  const busy = phase === 'locating' || phase === 'sending'

  return (
    <>
      <button onClick={() => setOpen(true)} aria-label="Emergency: open SOS" title="Emergency SOS"
        className={`relative inline-flex min-h-[40px] items-center gap-1.5 rounded-full bg-rose-600 font-bold text-white shadow-[0_8px_20px_-8px_rgba(225,29,72,.7)] transition hover:bg-rose-700 active:scale-95 ${compact ? 'px-3 text-xs' : 'px-4 text-sm'}`}>
        {phase === 'sharing' && <span className="absolute inset-0 animate-ping rounded-full bg-rose-500/50" aria-hidden />}
        <Siren className="relative h-4 w-4" aria-hidden /><span className="relative">SOS</span>
      </button>
      {open && createPortal(
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="fixed inset-0 z-[80] flex items-end justify-center bg-ink-900/70 backdrop-blur-sm sm:items-center sm:p-6" onMouseDown={() => setOpen(false)}>
          <motion.div initial={{ y: 40, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ type: 'spring', stiffness: 320, damping: 32 }} role="dialog" aria-modal="true" aria-labelledby="sos-title" onMouseDown={e => e.stopPropagation()}
            className="max-h-[92dvh] w-full max-w-lg overflow-y-auto rounded-t-[2rem] bg-white shadow-lift sm:rounded-[2rem]">
            <div className="flex items-center justify-between bg-rose-600 px-5 py-4 text-white">
              <h2 id="sos-title" className="flex items-center gap-2 font-display text-xl font-bold"><Siren className="h-5 w-5" aria-hidden />Emergency</h2>
              <button ref={closeRef} aria-label="Close" onClick={() => setOpen(false)} className="grid h-10 w-10 place-items-center rounded-full hover:bg-white/15"><X className="h-5 w-5" /></button>
            </div>
            <div className="space-y-4 p-5">
              <div>
                <p className="label">Call first if you are in danger{context?.destination && numbers.length ? ` (${context.destination})` : ''}</p>
                {numbers.length > 0 ? (
                  <ul className="grid gap-2 sm:grid-cols-2">{numbers.map(([k, v]) => { const n = (String(v).match(/\d{2,}/) ?? [''])[0]; return (
                    <li key={k}><a href={n ? `tel:${n}` : undefined} className="flex min-h-[52px] items-center justify-between gap-3 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-900 transition hover:bg-rose-100"><span className="min-w-0">{k}</span><span className="num flex shrink-0 items-center gap-1.5 text-base"><Phone className="h-4 w-4" aria-hidden />{String(v)}</span></a></li>) })}</ul>
                ) : <p className="rounded-2xl bg-sand p-3 text-sm text-ink/70">Emergency numbers differ by country. <b>112</b> works in India, the EU and many other places; <b>911</b> in North America. Open a planned trip to see the numbers for that destination.</p>}
              </div>

              <div className="rounded-2xl border border-ink/10 p-4">
                <p className="flex items-center gap-2 font-display text-lg font-bold"><MapPin className="h-4 w-4 text-rose-600" aria-hidden />Send my live location</p>
                <p className="mt-1 text-sm text-ink/65">Sends an alert with your name, your saved emergency contact and where you are right now. Your location then keeps updating for 15 minutes while this page stays open. Nothing is sent until you press the button.</p>
                <p className="mt-3 rounded-xl bg-sand p-3 text-sm">{contact?.name || contact?.phone
                  ? <>Emergency contact on file: <b>{[contact.name, contact.phone].filter(Boolean).join(' · ')}</b>{contact.phone && <a href={`tel:${contact.phone}`} className="link ml-2 whitespace-nowrap">Call them</a>}</>
                  : <>No emergency contact saved yet. <Link to="/profile" onClick={() => setOpen(false)} className="link">Add one in your profile</Link> so the alert says who to reach.</>}</p>
                {status && !status.configured && <p className="mt-3 flex gap-2 rounded-xl bg-sun-50 p-3 text-sm text-amber-900"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />Alerts are not set up on this server, so nothing can be sent from here. Use the phone numbers above.</p>}

                <AnimatePresence mode="wait">
                  {phase === 'sharing' ? (
                    <motion.div key="on" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-3 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-900" role="status">
                      <p className="flex items-center gap-2 font-semibold"><span className="relative flex h-2.5 w-2.5"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-75" /><span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-600" /></span>Alert sent. Sharing your live location</p>
                      <p className="num mt-1">{place ? `From ${place}. ` : ''}Time left: {mmss(left)}. Keep this page open.</p>
                      <button onClick={() => void stop()} className="btn btn-sm mt-3 border border-emerald-300 bg-white text-emerald-900 hover:bg-emerald-100"><Check className="h-4 w-4" aria-hidden />I am safe, stop sharing</button>
                    </motion.div>
                  ) : (
                    <motion.div key="off" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="mt-3 space-y-2">
                      <button onClick={() => send(false)} disabled={busy || (status ? !status.configured : false)} className="flex min-h-[56px] w-full items-center justify-center gap-2 rounded-2xl bg-rose-600 px-5 text-base font-bold text-white transition hover:bg-rose-700 active:scale-[.98] disabled:opacity-50">
                        <Send className="h-5 w-5" aria-hidden />{phase === 'locating' ? 'Getting your location…' : phase === 'sending' ? 'Sending alert…' : 'Send alert with my location'}</button>
                      <button onClick={() => send(true)} disabled={busy || (status ? !status.configured : false)} className="min-h-[40px] w-full rounded-full text-sm font-semibold text-ink/60 underline underline-offset-4 hover:text-ink disabled:opacity-50">Send a test alert instead (marked as a test)</button>
                    </motion.div>
                  )}
                </AnimatePresence>
                {msg && <p role="alert" className={`mt-3 rounded-xl p-3 text-sm ${phase === 'error' ? 'bg-rose-50 text-rose-800' : 'bg-sand text-ink/70'}`}>{msg}</p>}
              </div>
              <p className="text-xs text-ink/45">Plarno.ai is not an emergency service and cannot guarantee that an alert is seen. Always call the local emergency number when you can.</p>
            </div>
          </motion.div>
        </motion.div>, document.body)}
    </>
  )
}
