import { useState } from 'react'
import { api, Json } from './api'
import { useApp } from './store'

/** Applies a user edit to the open trip (attractions, hotel, pace); the server recomputes routes, meals and budget. */
export function useRebuild() {
  const { tripId, setPlan, reloadTrip } = useApp()
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const run = async (body: Json) => {
    setBusy(true); setErr(null)
    try { const r = await api(`/trips/${tripId}/itinerary/rebuild`, { body }); setPlan(r.plan); await reloadTrip(); return true }
    catch (e) { setErr((e as Error).message); return false } finally { setBusy(false) }
  }
  return { run, err, busy }
}
