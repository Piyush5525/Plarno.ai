import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowRight, CalendarDays, Luggage, Plus, Trash2 } from '../components/icons'
import { api, Json } from '../api'
import { useApp } from '../store'
import { Empty, ErrorBox, PageHead } from '../components/ui'

const GRADS = ['from-coral to-sun', 'from-lagoon to-sky', 'from-indigo-500 to-sky', 'from-emerald-500 to-lagoon', 'from-fuchsia-500 to-coral']
const when = (s: string) => { const d = new Date(s.replace(' ', 'T') + 'Z'); return isNaN(+d) ? s : d.toLocaleString([], { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) }

export default function Trips() {
  const [rows, setRows] = useState<Json[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [ask, setAsk] = useState<number | null>(null)
  const [busy, setBusy] = useState<number | null>(null)
  const { openTrip, tripId } = useApp()
  const nav = useNavigate()
  const load = () => api('/trips').then(r => { setRows(r); setErr(null) }).catch(e => setErr(e.message))
  useEffect(() => { void load() }, [])
  const open = async (id: number) => { setBusy(id); setErr(null); try { await openTrip(id); nav('/workspace') } catch (e) { setErr((e as Error).message) } finally { setBusy(null) } }
  const del = async (id: number) => {
    setBusy(id); setErr(null)
    try { await api(`/trips/${id}`, { method: 'DELETE' }); if (id === tripId) await openTrip(null); setAsk(null); await load() }
    catch (e) { setErr((e as Error).message) } finally { setBusy(null) }
  }
  const fresh = async () => { await openTrip(null); nav('/workspace') }
  return (
    <div className="mx-auto max-w-5xl px-4 py-8 md:py-10">
      <PageHead eyebrow="Saved" title="My trips" sub="Every plan is saved automatically. Open one to keep refining it." right={<button className="btn btn-primary" onClick={() => void fresh()}><Plus className="h-4 w-4" aria-hidden />New trip</button>} />
      {err && <div className="mb-4"><ErrorBox msg={err} retry={() => void load()} /></div>}
      {!rows && !err && <div className="grid gap-4 sm:grid-cols-2" role="status" aria-label="Loading trips">{[0, 1, 2, 3].map(i => <div key={i} className="skeleton h-36" />)}</div>}
      {rows?.length === 0 && <Empty title="No trips yet" icon={<Luggage className="h-7 w-7" />}><p>Start by telling TRIP about your next journey.</p><button className="btn btn-primary mt-4" onClick={() => void fresh()}>Plan my first trip<ArrowRight className="h-4 w-4" aria-hidden /></button></Empty>}
      <ul className="grid gap-4 sm:grid-cols-2">
        <AnimatePresence>
          {rows?.map((t, i) => (
            <motion.li key={t.id} layout initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95 }} transition={{ delay: Math.min(i, 8) * 0.04 }} className="card card-hover group relative overflow-hidden !p-0">
              <div className={`h-2 bg-gradient-to-r ${GRADS[t.id % GRADS.length]}`} aria-hidden />
              <div className="p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0"><p className="truncate font-display text-xl font-bold" title={t.title}>{t.title || 'Untitled trip'}</p><p className="num mt-1 flex items-center gap-1.5 text-xs text-ink/50"><CalendarDays className="h-3.5 w-3.5" aria-hidden />Updated {when(t.updated_at)}</p></div>
                  {t.id === tripId && <span className="badge shrink-0 bg-lagoon-50 text-lagoon-700">Open now</span>}
                </div>
                {ask === t.id ? (
                  <div className="mt-4 rounded-2xl bg-rose-50 p-3 text-sm text-rose-900" role="alertdialog" aria-label="Confirm delete"><p className="font-semibold">Delete this trip for good?</p><p className="text-xs">Its chat and expenses are removed too. This cannot be undone.</p>
                    <div className="mt-2 flex gap-2"><button className="btn btn-sm bg-rose-600 text-white hover:bg-rose-700" disabled={busy === t.id} onClick={() => void del(t.id)}>{busy === t.id ? 'Deleting…' : 'Yes, delete'}</button><button className="btn btn-ghost btn-sm" onClick={() => setAsk(null)}>Keep it</button></div></div>
                ) : (
                  <div className="mt-4 flex items-center gap-2">
                    <button className="btn btn-dark btn-sm" disabled={busy === t.id} onClick={() => void open(t.id)}>{busy === t.id ? 'Opening…' : 'Open'}<ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" aria-hidden /></button>
                    <button className="ml-auto grid h-10 w-10 place-items-center rounded-full text-ink/40 transition hover:bg-rose-50 hover:text-rose-600" aria-label={`Delete ${t.title || 'trip'}`} onClick={() => setAsk(t.id)}><Trash2 className="h-4 w-4" /></button>
                  </div>
                )}
              </div>
            </motion.li>
          ))}
        </AnimatePresence>
      </ul>
    </div>
  )
}
