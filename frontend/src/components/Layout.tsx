import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, Navigate, useLocation } from 'react-router-dom'
import { AnimatePresence, motion, useScroll, useSpring } from 'framer-motion'
import { Compass, LogOut, Map as MapIcon, Menu, Plane, Send, ShieldCheck, Sparkles, Suitcase, User, X } from './icons'
import { useApp } from '../store'
import TripAssistant from './TripAssistant'

const LINKS: [string, string, typeof Compass][] = [['/workspace', 'Plan', Sparkles], ['/discover', 'Discover', Compass], ['/transport', 'Ways to travel', Plane], ['/trips', 'My trips', Suitcase]]

export function Logo({ light = false }: { light?: boolean }) {
  return (
    <Link to="/" className="group flex items-center gap-2.5 font-display text-[1.45rem] font-bold tracking-tight" aria-label="Plarno.ai home">
      <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-[#ff7a59] to-coral-600 text-white shadow-glow transition-transform duration-300 group-hover:-rotate-12 group-hover:scale-105" aria-hidden><Send className="h-[18px] w-[18px] -translate-x-px translate-y-px" strokeWidth={2.4} /></span>
      <span className={light ? 'text-white' : 'text-ink'}>Plarno<span className="text-coral">.ai</span></span>
    </Link>
  )
}

export default function Layout() {
  const { user, logout } = useApp()
  const [open, setOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const { pathname } = useLocation()
  const landing = pathname === '/'
  const dark = landing && !scrolled && !open
  const { scrollYProgress } = useScroll()
  const bar = useSpring(scrollYProgress, { stiffness: 140, damping: 26, mass: 0.4 })

  useEffect(() => { const f = () => setScrolled(window.scrollY > 12); f(); window.addEventListener('scroll', f, { passive: true }); return () => window.removeEventListener('scroll', f) }, [])
  useEffect(() => { setOpen(false); window.scrollTo({ top: 0 }) }, [pathname])

  const item = (active: boolean) => `relative flex min-h-[40px] items-center gap-2 rounded-full px-3.5 text-sm font-semibold transition-colors ${active ? (dark ? 'text-ink' : 'text-white') : dark ? 'text-white/80 hover:text-white' : 'text-ink/65 hover:text-ink'}`
  const NavItem = ({ to, label, Icon }: { to: string; label: string; Icon: typeof Compass }) => (
    <NavLink to={to} className={({ isActive }) => item(isActive)}>
      {({ isActive }) => (<>
        {isActive && <motion.span layoutId="nav-pill" className={`absolute inset-0 rounded-full ${dark ? 'bg-white' : 'bg-ink'}`} transition={{ type: 'spring', stiffness: 420, damping: 36 }} />}
        <span className="relative z-10 flex items-center gap-2"><Icon className="h-4 w-4" aria-hidden />{label}</span>
      </>)}
    </NavLink>
  )

  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60] focus:rounded-full focus:bg-coral focus:px-4 focus:py-2 focus:text-white">Skip to content</a>
      <motion.div style={{ scaleX: bar }} className="fixed inset-x-0 top-0 z-[55] h-[3px] origin-left bg-gradient-to-r from-coral via-sun to-lagoon" aria-hidden />
      <header className={`sticky top-0 z-40 transition-[background-color,box-shadow,border-color] duration-300 ${dark ? 'border-b border-transparent bg-ink-900' : 'border-b border-ink/[.06] bg-sand/85 shadow-[0_8px_30px_-18px_rgba(11,31,51,.35)] backdrop-blur-xl'}`}>
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-3 px-4">
          <Logo light={dark} />
          <nav aria-label="Main" className="hidden items-center gap-0.5 lg:flex">
            {LINKS.map(([to, l, I]) => <NavItem key={to} to={to} label={l} Icon={I} />)}
            {user?.role === 'admin' && <NavItem to="/admin" label="Suppliers" Icon={ShieldCheck} />}
          </nav>
          <div className="hidden items-center gap-1.5 lg:flex">
            {user ? (<>
              <NavLink to="/profile" className={({ isActive }) => `${item(false)} ${isActive ? '!text-coral' : ''}`}><span className="grid h-7 w-7 place-items-center rounded-full bg-gradient-to-br from-lagoon to-sky text-xs font-bold uppercase text-white" aria-hidden>{(user.name || user.email || '?').slice(0, 1)}</span><span className="max-w-[120px] truncate">{user.name || user.email}</span></NavLink>
              <button onClick={logout} className={item(false)}><LogOut className="h-4 w-4" aria-hidden />Sign out</button>
            </>) : (<>
              <Link to="/auth" className={item(false)}>Sign in</Link>
              <Link to="/auth?mode=register" className="btn btn-primary btn-sm">Get started</Link>
            </>)}
          </div>
          <button className={`grid h-11 w-11 place-items-center rounded-full lg:hidden ${dark ? 'text-white hover:bg-white/10' : 'hover:bg-ink/5'}`} aria-label={open ? 'Close menu' : 'Open menu'} aria-expanded={open} onClick={() => setOpen(o => !o)}>{open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}</button>
        </div>
        <AnimatePresence>
          {open && (
            <motion.nav aria-label="Mobile" initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.25, ease: [0.2, 0.8, 0.2, 1] }} className="overflow-hidden border-t border-ink/10 bg-sand lg:hidden">
              <div className="flex flex-col gap-1 p-3">
                {[...LINKS, ...(user?.role === 'admin' ? [['/admin', 'Suppliers', ShieldCheck] as [string, string, typeof Compass]] : [])].map(([to, l, I], i) => (
                  <motion.div key={to} initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.03 * i }}>
                    <NavLink to={to} className={({ isActive }) => `flex min-h-[48px] items-center gap-3 rounded-2xl px-4 text-[15px] font-semibold ${isActive ? 'bg-ink text-white' : 'text-ink hover:bg-ink/5'}`}><I className="h-[18px] w-[18px]" aria-hidden />{l}</NavLink>
                  </motion.div>
                ))}
                <div className="my-1 h-px bg-ink/10" />
                {user ? (<>
                  <NavLink to="/profile" className="flex min-h-[48px] items-center gap-3 rounded-2xl px-4 text-[15px] font-semibold hover:bg-ink/5"><User className="h-[18px] w-[18px]" aria-hidden />{user.name || user.email}</NavLink>
                  <button onClick={() => { logout(); setOpen(false) }} className="flex min-h-[48px] items-center gap-3 rounded-2xl px-4 text-left text-[15px] font-semibold hover:bg-ink/5"><LogOut className="h-[18px] w-[18px]" aria-hidden />Sign out</button>
                </>) : <Link to="/auth" className="btn btn-primary mt-1 !py-3">Sign in or create account</Link>}
              </div>
            </motion.nav>
          )}
        </AnimatePresence>
      </header>

      <main id="main" className="flex-1">
        <motion.div key={pathname} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: [0.2, 0.8, 0.2, 1] }}><Outlet /></motion.div>
      </main>

      <footer className="mt-16 bg-ink-900 text-white/70">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-14 md:grid-cols-[1.4fr_1fr_1fr_1.3fr]">
          <div><Logo light /><p className="mt-4 max-w-xs text-sm leading-relaxed">Your journey, intelligently planned. Real places, live prices and weather, one plan that updates itself when you change your mind.</p></div>
          <div><p className="text-xs font-bold uppercase tracking-[.14em] text-white/40">Product</p><ul className="mt-4 space-y-1 text-sm">{LINKS.map(([to, l]) => <li key={to}><Link to={to} className="inline-block min-w-[44px] py-1.5 transition hover:text-white">{l}</Link></li>)}</ul></div>
          <div><p className="text-xs font-bold uppercase tracking-[.14em] text-white/40">Account</p><ul className="mt-4 space-y-1 text-sm">
            <li><Link to={user ? '/profile' : '/auth'} className="inline-block py-1.5 transition hover:text-white">{user ? 'Preferences' : 'Sign in'}</Link></li>
            <li><Link to="/trips" className="inline-block py-1.5 transition hover:text-white">Saved trips</Link></li>
            <li><Link to="/discover" className="inline-block py-1.5 transition hover:text-white">Explore a city</Link></li></ul></div>
          <div><p className="text-xs font-bold uppercase tracking-[.14em] text-white/40">Data sources</p>
            <p className="mt-4 text-sm leading-relaxed">Places and hotels: Google Maps and Google Hotels via SerpApi. Flights: Google Flights via SerpApi. Weather: OpenWeather. Air quality: AQICN. Maps © Mapbox © OpenStreetMap contributors.</p></div>
        </div>
        <div className="border-t border-white/10"><div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 px-4 py-5 text-xs text-white/45"><p>© {new Date().getFullYear()} Plarno.ai · Prototype</p><p className="flex items-center gap-1.5"><MapIcon className="h-3.5 w-3.5" aria-hidden />Prices are for planning and can change. Bookings happen on provider websites.</p></div></div>
      </footer>
      <TripAssistant />
    </div>
  )
}

export function Protected({ children }: { children: JSX.Element }) {
  const { user, authReady } = useApp()
  if (!authReady) return <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-16 text-sm text-ink/60" role="status"><span className="h-4 w-4 animate-spin rounded-full border-2 border-ink/20 border-t-coral" />Loading…</div>
  return user ? children : <Navigate to="/auth" replace />
}
