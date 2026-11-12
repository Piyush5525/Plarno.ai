import { useEffect, useState } from 'react'
import { api, inr, Json } from '../api'
import { useApp } from '../store'
import { Empty, ErrorBox, Loading, PageHead } from '../components/ui'

const SAMPLE = JSON.stringify([{ listing_id: 'NS-1', name: 'Imperial Vista Hotel New Delhi', lat: 28.6311, lon: 77.2189, room: 'Deluxe King', beds: '1 King', occupancy: 2, meal: 'Breakfast included', price: 11000 }], null, 1)

export default function Admin() {
  const { user } = useApp()
  const [m, setM] = useState<Json | null>(null)
  const [ev, setEv] = useState<Json | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [up, setUp] = useState({ supplier: 'NewSupplier', format: 'json', data: SAMPLE })
  const [msg, setMsg] = useState<string | null>(null)
  const [health, setHealth] = useState<Json[]>([])
  useEffect(() => { api('/providers/health?check=true').then(setHealth).catch(() => {}) }, [])
  const load = () => { setErr(null); api('/admin/matching').then(setM).catch(e => setErr(e.message)); api('/admin/evaluation').then(setEv).catch(() => {}) }
  useEffect(() => { if (user?.role === 'admin') load() }, [user])
  if (user?.role !== 'admin') return <div className="mx-auto max-w-xl px-4 py-16"><Empty title="Admin only">Set PLARNO_ADMIN_EMAILS on the server to grant an account admin access, then register with that email.</Empty></div>
  const decide = async (a: string, b: string, decision: 'approve' | 'reject') => { await api('/admin/matching/decision', { body: { a, b, decision } }); load() }
  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <PageHead title="Supplier intelligence" sub="Duplicate detection (RapidFuzz name similarity + geo gate), room matching and explainable offer ranking. Original supplier records are never modified." />
      {err && <ErrorBox msg={err} retry={load} />}
      {health.length > 0 && <div className="card mb-6"><p className="mb-2 font-display text-lg">Data providers</p><ul className="grid gap-1 text-sm sm:grid-cols-2">{health.map(h => <li key={h.provider} className="flex justify-between gap-3 border-b border-ink/5 py-1"><span>{h.provider} <span className="text-ink/40">· {h.role}</span>{h.note && <span className="block text-xs text-ink/50">{h.note}</span>}</span><span className={`badge h-fit ${h.status === 'verified' ? 'bg-emerald-100 text-emerald-800' : h.status.startsWith('ready') ? 'bg-sky-100 text-sky-800' : h.status === 'sandbox' ? 'bg-violet-100 text-violet-800' : h.status === 'degraded' ? 'bg-rose-100 text-rose-800' : 'bg-amber-100 text-amber-800'}`}>{h.status}</span></li>)}</ul></div>}
      {ev && <div className="mb-6 grid gap-3 sm:grid-cols-4">{[['Precision', ev.precision], ['Recall', ev.recall], ['False-merge rate', ev.false_merge_rate], ['Pairs (tp/fp/fn)', `${ev.pairs.tp}/${ev.pairs.fp}/${ev.pairs.fn}`]].map(([k, v]) => <div key={String(k)} className="card py-4"><p className="text-xs uppercase text-ink/50">{k}</p><p className="font-display text-2xl">{String(v)}</p></div>)}</div>}
      <p className="mb-6 text-xs text-ink/50">Metrics are measured on the small labelled synthetic dataset (14 listings); they demonstrate the method, not production accuracy.</p>
      {!m && !err && <Loading />}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          {m?.clusters.map((c: Json, i: number) => (
            <div key={i} className="card"><p className="font-display text-lg">{c.canonical_name} <span className="text-sm text-ink/50">· {c.members.length} listing{c.members.length > 1 ? 's' : ''}</span></p>
              <table className="mt-2 w-full text-left text-xs"><thead className="text-ink/50"><tr><th>Supplier</th><th>Room</th><th>Meal</th><th>Price</th><th>Score</th><th>Why</th></tr></thead><tbody>{c.ranked_offers.map((o: Json) => <tr key={o.listing_id} className="border-t border-ink/10"><td className="py-1">{o.supplier}</td><td>{o.room}</td><td>{o.meal}</td><td>{inr(o.price)}</td><td><b>{o.offer_score}</b></td><td className="text-ink/50">{o.why}</td></tr>)}</tbody></table>
              {c.members.length > 1 && <div className="mt-2 text-xs text-ink/60">Match evidence: {m.evidence.filter((e: Json) => e.pair.every((id: string) => c.members.some((x: Json) => x.listing_id === id))).map((e: Json) => <p key={e.pair.join()}>{e.pair.join(' ↔ ')}: {e.score} ({e.reasons.join('; ')}) <button className="ml-2 text-rose-700 underline" onClick={() => void decide(e.pair[0], e.pair[1], 'reject')}>Separate</button></p>)}</div>}
            </div>))}
        </div>
        <div className="space-y-4">
          <div className="card"><p className="font-display text-lg">Needs human review</p>
            {m?.needs_review.length === 0 && <p className="mt-2 text-sm text-ink/50">Nothing pending.</p>}
            {m?.needs_review.map((r: Json) => <div key={r.a + r.b} className="mt-2 rounded-lg bg-sand p-2 text-xs"><p>{r.a} ↔ {r.b} · score {r.score}</p><p className="text-ink/50">{r.reasons.join('; ')}{r.blocked_by ? ` · ${r.blocked_by}` : ''}</p><div className="mt-1 flex gap-2"><button className="underline" onClick={() => void decide(r.a, r.b, 'approve')}>Approve merge</button><button className="underline text-rose-700" onClick={() => void decide(r.a, r.b, 'reject')}>Reject</button></div></div>)}</div>
          <form className="card space-y-2" onSubmit={async e => { e.preventDefault(); setMsg(null); try { const r = await api('/admin/suppliers/upload', { body: up }); setMsg(`Accepted ${r.accepted}, rejected ${r.rejected.length}`); load() } catch (x) { setMsg((x as Error).message) } }}>
            <p className="font-display text-lg">Upload supplier data</p>
            <input className="input" value={up.supplier} onChange={e => setUp({ ...up, supplier: e.target.value })} />
            <select className="input" value={up.format} onChange={e => setUp({ ...up, format: e.target.value })}><option>json</option><option>csv</option></select>
            <textarea className="input h-40 font-mono text-xs" value={up.data} onChange={e => setUp({ ...up, data: e.target.value })} />
            <button className="btn btn-primary">Upload</button>{msg && <p className="text-xs">{msg}</p>}
          </form>
        </div>
      </div>
    </div>
  )
}
