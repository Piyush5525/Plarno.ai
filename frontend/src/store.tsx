import { createContext, useCallback, useContext, useEffect, useRef, useState, ReactNode } from 'react'
import { api, getToken, setToken, Json } from './api'

export type Msg = { role: 'user' | 'assistant'; content: string }
export type AssistantAction = { label: string; to?: string }

type Ctx = {
  user: Json | null
  authReady: boolean
  login: (email: string, pw: string, name?: string, register?: boolean) => Promise<void>
  logout: () => void
  tripId: number | null
  plan: Json
  context: Json
  messages: Msg[]
  busy: boolean
  workflow: Json[]
  followUps: string[]
  send: (text: string) => Promise<string | null>
  openTrip: (id: number | null) => Promise<void>
  reloadTrip: () => Promise<void>
  setPlan: (p: Json) => void
  speakReplies: boolean
  setSpeakReplies: (b: boolean) => void
  lastError: string | null
  lastAction: { to?: string } | null
}
const C = createContext<Ctx>(null as unknown as Ctx)
export const useApp = () => useContext(C)

export function AppProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Json | null>(null)
  const [authReady, setAuthReady] = useState(false)
  const [tripId, setTripId] = useState<number | null>(null)
  const [plan, setPlan] = useState<Json>({})
  const [context, setContext] = useState<Json>({})
  const [messages, setMessages] = useState<Msg[]>([])
  const [workflow, setWorkflow] = useState<Json[]>([])
  const [followUps, setFollowUps] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [speakReplies, setSpeakReplies] = useState(false)
  const [lastError, setLastError] = useState<string | null>(null)
  const [lastAction, setLastAction] = useState<{ to?: string } | null>(null)

  useEffect(() => {
    if (!getToken()) { setAuthReady(true); return }
    api('/me').then(async u => {
      setUser(u)
      let saved: string | null = null
      try { saved = localStorage.getItem('plarno_trip') } catch { /* storage blocked */ }
      if (saved) { try { await openTripRef.current(Number(saved)) } catch { try { localStorage.removeItem('plarno_trip') } catch { /* ignore */ } } }
    }).catch(() => setToken(null)).finally(() => setAuthReady(true))
  }, [])
  useEffect(() => { if (tripId) { try { localStorage.setItem('plarno_trip', String(tripId)) } catch { /* ignore */ } } }, [tripId])  // never clears on mount: restore reads it first

  const login = async (email: string, password: string, name?: string, register = false) => {
    const r = await api(register ? '/auth/register' : '/auth/login', { body: { email, password, name } })
    setToken(r.token)
    setUser(r.user)
  }
  const logout = () => { setToken(null); setUser(null); setTripId(null); setPlan({}); setMessages([]); try { localStorage.removeItem('plarno_trip') } catch { /* ignore */ } }

  const openTrip = useCallback(async (id: number | null) => {
    if (id == null) { try { localStorage.removeItem('plarno_trip') } catch { /* ignore */ } setTripId(null); setPlan({}); setContext({}); setMessages([]); setWorkflow([]); setFollowUps([]); return }
    const t = await api(`/trips/${id}`)
    setTripId(id); setPlan(t.plan); setContext(t.context); setFollowUps([])
    setMessages(t.messages.map((m: Json) => ({ role: m.role, content: m.content })))
  }, [])
  const openTripRef = useRef(openTrip)
  openTripRef.current = openTrip
  const reloadTrip = useCallback(async () => { if (tripId) await openTrip(tripId) }, [tripId, openTrip])

  const send = useCallback(async (text: string) => {
    setBusy(true); setLastError(null)
    setMessages(m => [...m, { role: 'user', content: text }])
    try {
      const r = await api('/chat', { body: { message: text, trip_id: tripId } })
      setTripId(r.trip_id); setPlan(r.plan); setContext(r.context); setWorkflow(r.workflow); setFollowUps(r.follow_ups)
      setMessages(m => [...m, { role: 'assistant', content: r.reply }])
      setLastAction(r.action ?? null)
      return r.reply as string
    } catch (e) {
      const msg = (e as Error).message
      setLastError(msg)
      setMessages(m => [...m, { role: 'assistant', content: '⚠ ' + msg }])
      return null
    } finally { setBusy(false) }
  }, [tripId])

  return (
    <C.Provider value={{ user, authReady, login, logout, tripId, plan, context, messages, busy, workflow, followUps, send, openTrip, reloadTrip, setPlan, speakReplies, setSpeakReplies, lastError, lastAction }}>
      {children}
    </C.Provider>
  )
}
