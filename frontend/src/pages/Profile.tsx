import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Check, Gauge, Leaf, MapPin, Salad, ShieldCheck, Star } from '../components/icons'
import { api, Json } from '../api'
import { useApp } from '../store'
import { ErrorBox, PageHead } from '../components/ui'

const PRIORITIES: [string, string, string][] = [['', 'Balanced', 'A bit of everything'], ['family', 'Family', 'Safety, quiet, connectivity'], ['budget', 'Budget', 'Lowest sensible cost'], ['sightseeing', 'Sightseeing', 'Close to the sights'], ['peaceful', 'Peaceful', 'Calm and green']]

function Toggle({ checked, onChange, label, sub }: { checked: boolean; onChange: (v: boolean) => void; label: string; sub?: string }) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-4 rounded-2xl p-3 transition hover:bg-sand">
      <span><span className="block text-sm font-semibold">{label}</span>{sub && <span className="block text-xs text-ink/55">{sub}</span>}</span>
      <span className="relative inline-flex h-7 w-12 shrink-0 items-center">
        <input type="checkbox" className="peer sr-only" checked={checked} onChange={e => onChange(e.target.checked)} />
        <span className="absolute inset-0 rounded-full bg-ink/15 transition peer-checked:bg-lagoon peer-focus-visible:ring-2 peer-focus-visible:ring-coral peer-focus-visible:ring-offset-2" />
        <span className="relative ml-1 h-5 w-5 rounded-full bg-white shadow transition-transform peer-checked:translate-x-5" />
      </span>
    </label>
  )
}

export default function Profile() {
  const { user } = useApp()
  const [p, setP] = useState<Json>({ vegetarian: false, vegan: false, pace: 'balanced', priority_preset: '', share_location_consent: false, trusted_contact: '', emergency_name: '', emergency_phone: '' })
  const [saved, setSaved] = useState(false)
  const [busy, setBusy] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { api('/me').then(m => setP((x: Json) => ({ ...x, ...m.preferences }))).catch(e => setErr(e.message)).finally(() => setLoaded(true)) }, [])
  const upd = (patch: Json) => { setP({ ...p, ...patch }); setSaved(false) }
  async function save(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null)
    try { await api('/me/preferences', { method: 'PUT', body: p }); setSaved(true); window.setTimeout(() => setSaved(false), 3500) }
    catch (x) { setErr((x as Error).message) } finally { setBusy(false) }
  }
  return (
    <div className="mx-auto max-w-2xl px-4 py-8 md:py-10">
      <PageHead eyebrow="Account" title="Preferences" sub="Used as defaults when TRIP plans a new trip. Location is never shared without your consent." />
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="card mb-5 flex items-center gap-4">
        <span className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-lagoon to-sky font-display text-2xl font-bold uppercase text-white" aria-hidden>{(user?.name || user?.email || '?').slice(0, 1)}</span>
        <div className="min-w-0"><p className="truncate font-display text-xl font-bold">{user?.name || 'Traveller'}</p><p className="truncate text-sm text-ink/55">{user?.email}</p></div>
        {user?.role === 'admin' && <span className="badge ml-auto bg-ink text-white"><ShieldCheck className="h-3 w-3" aria-hidden />Admin</span>}
      </motion.div>
      <form className={`space-y-5 transition-opacity ${loaded ? '' : 'pointer-events-none opacity-50'}`} onSubmit={save}>
        <section className="card !p-3"><h2 className="flex items-center gap-2 px-3 pt-2 font-display text-lg font-bold"><Salad className="h-4 w-4 text-lagoon" aria-hidden />Food</h2>
          <Toggle label="Vegetarian" sub="Only suggest restaurants with vegetarian options" checked={!!p.vegetarian} onChange={v => upd({ vegetarian: v, vegan: v ? p.vegan : false })} />
          <Toggle label="Vegan" sub="Stricter: implies vegetarian" checked={!!p.vegan} onChange={v => upd({ vegan: v, vegetarian: v ? true : p.vegetarian })} />
        </section>
        <section className="card"><h2 className="flex items-center gap-2 font-display text-lg font-bold"><Gauge className="h-4 w-4 text-coral" aria-hidden />Travel pace</h2>
          <div className="mt-3 inline-flex w-full rounded-2xl bg-sand p-1" role="group" aria-label="Travel pace">{['relaxed', 'balanced', 'packed'].map(x => (
            <button key={x} type="button" aria-pressed={p.pace === x} onClick={() => upd({ pace: x })} className={`relative min-h-[42px] flex-1 rounded-xl text-sm font-semibold capitalize transition-colors ${p.pace === x ? 'text-ink' : 'text-ink/55 hover:text-ink'}`}>
              {p.pace === x && <motion.span layoutId="pf-pace" className="absolute inset-0 rounded-xl bg-white shadow-soft" transition={{ type: 'spring', stiffness: 420, damping: 34 }} />}<span className="relative z-10">{x}</span></button>))}</div>
        </section>
        <section className="card"><h2 className="flex items-center gap-2 font-display text-lg font-bold"><Star className="h-4 w-4 text-sun" aria-hidden />What matters most</h2>
          <div className="mt-3 grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="What matters most">{PRIORITIES.map(([k, l, d]) => (
            <button key={k} type="button" role="radio" aria-checked={(p.priority_preset ?? '') === k} onClick={() => upd({ priority_preset: k })} className={`flex items-center justify-between gap-3 rounded-2xl border p-3 text-left transition ${(p.priority_preset ?? '') === k ? 'border-coral bg-coral-50' : 'border-ink/10 hover:border-ink/30'}`}>
              <span><span className="block text-sm font-semibold">{l}</span><span className="block text-xs text-ink/55">{d}</span></span>
              <span className={`grid h-5 w-5 shrink-0 place-items-center rounded-full border-2 transition ${(p.priority_preset ?? '') === k ? 'border-coral bg-coral text-white' : 'border-ink/20'}`} aria-hidden>{(p.priority_preset ?? '') === k && <Check className="h-3 w-3" />}</span></button>))}</div>
        </section>
        <section className="card"><h2 className="flex items-center gap-2 font-display text-lg font-bold"><MapPin className="h-4 w-4 text-sky" aria-hidden />Emergency contact</h2>
          <p className="mt-1 text-sm text-ink/60">Who should be reached if you press the red <b>SOS</b> button. Their name and number go into the alert together with your live location.</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <div><label className="label" htmlFor="pf-ename">Emergency contact name</label><input id="pf-ename" className="input" maxLength={80} autoComplete="off" value={p.emergency_name ?? ''} onChange={e => upd({ emergency_name: e.target.value })} placeholder="e.g. Mum, or a friend" /></div>
            <div><label className="label" htmlFor="pf-ephone">Their phone number</label><input id="pf-ephone" className="input num" type="tel" inputMode="tel" maxLength={20} autoComplete="off" value={p.emergency_phone ?? ''} onChange={e => upd({ emergency_phone: e.target.value })} placeholder="+91 98765 43210" /></div>
          </div>
          <p className="mt-2 text-xs text-ink/50">Your location is only ever sent when you press SOS and confirm. Save your changes below, then try “Send a test alert” from the SOS button.</p>
        </section>
        {err && <ErrorBox msg={err} />}
        <div className="sticky bottom-4 z-10 flex items-center gap-3 rounded-full border border-ink/[.07] bg-white/90 p-2 pl-5 shadow-lift backdrop-blur">
          <p className="flex min-w-0 flex-1 items-center gap-2 text-sm text-ink/60" role="status"><AnimatePresence mode="wait">{saved ? <motion.span key="s" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="flex items-center gap-2 font-semibold text-lagoon-700"><Check className="h-4 w-4" aria-hidden />Saved</motion.span> : <motion.span key="n" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex items-center gap-2 truncate"><Leaf className="h-4 w-4 shrink-0" aria-hidden />Applies to new trips</motion.span>}</AnimatePresence></p>
          <button className="btn btn-primary" disabled={busy}>{busy ? 'Saving…' : 'Save preferences'}</button>
        </div>
      </form>
    </div>
  )
}
