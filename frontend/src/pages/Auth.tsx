import { useState } from 'react'
import { Navigate, useSearchParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowRight, Check, Eye, EyeOff, Lock, Mail, User } from '../components/icons'
import { useApp } from '../store'
import { ErrorBox } from '../components/ui'
import TripBot from '../components/Bot'
import { PENDING } from '../components/TripBuilder'

const PERKS = ['Real places, hotel rates and flight fares', 'A live guide with weather matched to each day', 'Every trip saved automatically']

export default function Auth() {
  const { user, login } = useApp()
  const [sp] = useSearchParams()
  const [reg, setReg] = useState(sp.get('mode') === 'register')
  const [f, setF] = useState({ email: '', password: '', name: '' })
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [show, setShow] = useState(false)
  const [focus, setFocus] = useState(false)
  let pending = false
  try { pending = !!sessionStorage.getItem(PENDING) } catch { /* ignore */ }
  if (user) return <Navigate to="/workspace" replace />

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(f.email.trim())) { setErr('Enter a valid email address.'); return }
    if (f.password.length < 8) { setErr('Your password needs at least 8 characters.'); return }
    setBusy(true); setErr(null)
    try { await login(f.email.trim(), f.password, f.name.trim() || undefined, reg) }
    catch (x) { const m = (x as Error).message; setErr(m === 'Invalid credentials' ? 'That email and password do not match. Try again, or create an account.' : m === 'Email already registered' ? 'That email already has an account. Sign in instead.' : m) }
    finally { setBusy(false) }
  }
  return (
    <div className="mx-auto grid max-w-5xl items-stretch gap-6 px-4 py-10 md:grid-cols-2 md:py-16">
      <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} className="relative hidden overflow-hidden rounded-[2rem] bg-ink-900 p-8 text-white md:flex md:flex-col">
        <div className="pointer-events-none absolute -left-16 -top-16 h-64 w-64 animate-aurora rounded-full bg-coral/35 blur-[90px]" aria-hidden />
        <div className="pointer-events-none absolute -bottom-20 -right-10 h-64 w-64 animate-aurora rounded-full bg-lagoon/30 blur-[90px] [animation-delay:-6s]" aria-hidden />
        <p className="relative font-display text-3xl font-bold leading-tight">{pending ? 'One step from your plan.' : 'Your next trip starts here.'}</p>
        <div className="relative mx-auto my-2 flex flex-1 items-center"><TripBot state={busy ? 'thinking' : err ? 'error' : focus ? 'listening' : 'hover'} size={260} interactive /></div>
        <ul className="relative space-y-2.5 text-sm text-white/80">{PERKS.map((p, i) => <motion.li key={p} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 + i * 0.1 }} className="flex items-center gap-2.5"><span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-lagoon text-white"><Check className="h-3 w-3" aria-hidden /></span>{p}</motion.li>)}</ul>
      </motion.div>

      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="card flex flex-col justify-center !p-6 md:!p-9">
        <div className="mb-6 inline-flex w-full rounded-2xl bg-sand p-1" role="group" aria-label="Sign in or create account">
          {([[false, 'Sign in'], [true, 'Create account']] as [boolean, string][]).map(([v, l]) => (
            <button key={l} type="button" aria-pressed={reg === v} onClick={() => { setReg(v); setErr(null) }} className={`relative min-h-[42px] flex-1 rounded-xl text-sm font-semibold transition-colors ${reg === v ? 'text-ink' : 'text-ink/55 hover:text-ink'}`}>
              {reg === v && <motion.span layoutId="auth-mode" className="absolute inset-0 rounded-xl bg-white shadow-soft" transition={{ type: 'spring', stiffness: 420, damping: 34 }} />}<span className="relative z-10">{l}</span></button>))}
        </div>
        <h1 className="font-display text-3xl font-bold">{reg ? 'Create your account' : 'Welcome back'}</h1>
        <p className="mt-1.5 text-sm text-ink/60">{pending ? 'Your trip request is saved. Sign in and Plarno will start planning right away.' : reg ? 'Free, and it takes a few seconds.' : 'Plan, save and manage your trips.'}</p>
        <form className="mt-6 space-y-4" noValidate onSubmit={submit} onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}>
          <AnimatePresence initial={false}>
            {reg && <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden"><label className="label" htmlFor="au-name">Name</label><div className="relative"><User className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink/35" aria-hidden /><input id="au-name" className="input !pl-10" placeholder="Your name" autoComplete="name" value={f.name} onChange={e => setF({ ...f, name: e.target.value })} /></div></motion.div>}
          </AnimatePresence>
          <div><label className="label" htmlFor="au-email">Email</label><div className="relative"><Mail className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink/35" aria-hidden /><input id="au-email" className="input !pl-10" type="email" required placeholder="you@example.com" autoComplete="email" value={f.email} onChange={e => setF({ ...f, email: e.target.value })} /></div></div>
          <div><label className="label" htmlFor="au-pw">Password</label><div className="relative"><Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink/35" aria-hidden />
            <input id="au-pw" className="input !pl-10 !pr-12" type={show ? 'text' : 'password'} required minLength={8} placeholder="At least 8 characters" autoComplete={reg ? 'new-password' : 'current-password'} value={f.password} onChange={e => setF({ ...f, password: e.target.value })} />
            <button type="button" aria-label={show ? 'Hide password' : 'Show password'} aria-pressed={show} onClick={() => setShow(s => !s)} className="absolute right-1 top-1/2 grid h-10 w-10 -translate-y-1/2 place-items-center rounded-full text-ink/45 hover:text-ink">{show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button></div>
            {reg && f.password.length > 0 && <div className="mt-2 flex items-center gap-2 text-xs text-ink/50"><div className="h-1 flex-1 overflow-hidden rounded bg-ink/10"><div className={`h-full rounded transition-all duration-300 ${f.password.length >= 12 ? 'w-full bg-emerald-500' : f.password.length >= 8 ? 'w-2/3 bg-sun' : 'w-1/3 bg-coral'}`} /></div>{f.password.length >= 12 ? 'Strong' : f.password.length >= 8 ? 'Good' : `${8 - f.password.length} more`}</div>}
          </div>
          {err && <ErrorBox msg={err} />}
          <button className="btn btn-primary w-full !py-3.5 text-base" disabled={busy}>{busy ? 'Please wait…' : reg ? 'Sign up' : 'Sign in'}{!busy && <ArrowRight className="h-4 w-4" aria-hidden />}</button>
        </form>
        <p className="mt-5 text-center text-sm text-ink/60">{reg ? 'Already have an account?' : 'New to Plarno?'} <button className="min-h-[36px] font-semibold text-coral-600 underline underline-offset-4" onClick={() => { setReg(!reg); setErr(null) }}>{reg ? 'I already have an account' : 'Create an account'}</button></p>
      </motion.div>
    </div>
  )
}
