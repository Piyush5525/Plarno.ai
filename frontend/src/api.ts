// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Json = any
/** Where the backend lives. Empty in development (Vite proxies /api to :8000). On Vercel set VITE_API_URL to the hosted backend, e.g. https://plarno-api.onrender.com */
const API_BASE = ((import.meta.env.VITE_API_URL as string | undefined) ?? '').trim().replace(/\/+$/, '')
let token: string | null = null
try { token = localStorage.getItem('tp_token') } catch { /* storage blocked */ }
export const getToken = () => token
export function setToken(t: string | null) {
  token = t
  try { t ? localStorage.setItem('tp_token', t) : localStorage.removeItem('tp_token') } catch { /* ignore */ }
}

export class ApiError extends Error {
  constructor(public status: number, msg: string) { super(msg) }
}

export async function api<T = Json>(path: string, opts: { method?: string; body?: unknown } = {}): Promise<T> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 30000)
  try {
    const r = await fetch(API_BASE + '/api' + path, {
      method: opts.method ?? (opts.body ? 'POST' : 'GET'),
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: 'Bearer ' + token } : {}) },
      body: opts.body ? JSON.stringify(opts.body) : undefined,
      signal: ctrl.signal,
    })
    const data = await r.json().catch(() => ({}))
    if (!r.ok) {
      if (r.status === 401) setToken(null)
      const d = data.detail
      throw new ApiError(r.status, typeof d === 'string' ? d : Array.isArray(d) ? d.map((x: Json) => x.msg).join('; ') : r.statusText)
    }
    return data as T
  } catch (e) {
    if (e instanceof ApiError) throw e
    throw new ApiError(0, 'Cannot reach the Plarno.ai server. Is the backend running on port 8000?')
  } finally {
    clearTimeout(timer)
  }
}

export const inr = (v: number | undefined | null) => (v == null ? '—' : (v < 0 ? '−₹' : '₹') + Math.abs(Math.round(v)).toLocaleString('en-IN'))
export const mins = (m: number) => `${Math.floor(m / 60)}h ${String(Math.round(m % 60)).padStart(2, '0')}m`
