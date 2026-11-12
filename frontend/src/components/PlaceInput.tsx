import { useEffect, useId, useRef, useState } from 'react'
import { api, Json } from '../api'
import { GraduationCap, Landmark, MapPin, Plane, TrainFront } from './icons'

/** Icon and label for what kind of thing a suggestion is (a town has none: it is the default). */
const KIND: Record<string, [typeof MapPin, string]> = { college: [GraduationCap, 'college'], school: [GraduationCap, 'school'], station: [TrainFront, 'station'], airport: [Plane, 'airport'], landmark: [Landmark, 'landmark'], port: [MapPin, 'port'] }

export type PlaceSuggestion = { name: string; context: string; label: string; lat: number | null; lon: number | null; broad: boolean; kind?: string }

/** Place search box with real as-you-type suggestions for towns, colleges, stations and airports (OpenStreetMap + Mapbox, via the backend). Accessible combobox: arrows, Enter, Esc. */
export default function PlaceInput({ value, onChange, onPick, placeholder, label, id, required, className = '', ariaLabel }: {
  value: string; onChange: (v: string) => void; onPick?: (s: PlaceSuggestion) => void; placeholder?: string; label?: string; id?: string; required?: boolean; className?: string; ariaLabel?: string
}) {
  const uid = useId()
  const inputId = id ?? 'pi-' + uid
  const [items, setItems] = useState<PlaceSuggestion[]>([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const [loading, setLoading] = useState(false)
  const [source, setSource] = useState('')
  const seq = useRef(0)
  const justPicked = useRef(false)
  const wrap = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (justPicked.current) { justPicked.current = false; return }
    const q = value.trim()
    if (q.length < 2) { setItems([]); setOpen(false); return }
    if (document.activeElement !== inputRef.current) return  // value set by the app (a chip, a swap), not typed: no lookup needed
    const mine = ++seq.current
    const t = setTimeout(async () => {
      setLoading(true)
      try {
        const r = await api(`/geocode/suggest?q=${encodeURIComponent(q)}`)
        if (mine !== seq.current) return  // a newer keystroke superseded this request
        setItems(r.suggestions); setSource(r.source); setActive(-1)
        setOpen(r.suggestions.length > 0 && document.activeElement === inputRef.current)  // a late response must not reopen the list after the user left or pressed Esc
      } catch { if (mine === seq.current) { setItems([]); setOpen(false) } } finally { if (mine === seq.current) setLoading(false) }
    }, 220)
    return () => clearTimeout(t)
  }, [value])

  useEffect(() => {
    const away = (e: MouseEvent) => { if (!wrap.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', away)
    return () => document.removeEventListener('mousedown', away)
  }, [])

  const pick = (s: PlaceSuggestion) => {
    const country = s.context.split(',').pop()?.trim()
    justPicked.current = true
    // a specific spot (a college, a station) keeps its town and state so the planner finds that exact one, not a namesake elsewhere
    onChange(s.kind ? s.label : country && country !== s.name ? `${s.name}, ${country}` : s.name)
    onPick?.(s); setOpen(false); setItems([])
  }
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); if (!open && items.length) setOpen(true); setActive(a => Math.min(items.length - 1, a + 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(a => Math.max(0, a - 1)) }
    else if (e.key === 'Enter' && open && active >= 0) { e.preventDefault(); pick(items[active]) }
    else if (e.key === 'Escape') setOpen(false)
  }
  const listId = inputId + '-list'
  const broadPick = items.find(i => i.broad && value.toLowerCase().startsWith(i.name.toLowerCase()))
  return (
    <div ref={wrap} className="relative">
      {label && <label className="label" htmlFor={inputId}>{label}</label>}
      <div className="relative">
        <MapPin className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink/35" aria-hidden />
        <input ref={inputRef} id={inputId} className={`input !pl-10 ${className}`} value={value} placeholder={placeholder} required={required} autoComplete="off" aria-label={label ? undefined : ariaLabel}
          role="combobox" aria-expanded={open} aria-controls={listId} aria-autocomplete="list" aria-activedescendant={active >= 0 ? `${inputId}-o${active}` : undefined}
          onChange={e => onChange(e.target.value)} onKeyDown={onKey} onFocus={() => items.length && setOpen(true)} onBlur={() => setOpen(false)} />
        {loading && <span className="pointer-events-none absolute right-3.5 top-1/2 -mt-2 h-4 w-4 animate-spin rounded-full border-2 border-ink/15 border-t-coral" aria-hidden />}
      </div>
      {open && (
        <ul id={listId} role="listbox" className="absolute left-0 right-0 top-full z-30 mt-1.5 max-h-72 animate-pop overflow-auto rounded-2xl border border-ink/10 bg-white py-1 shadow-lift">
          {items.map((s, i) => { const [KIcon, kindLabel] = KIND[s.kind ?? ''] ?? [MapPin, '']; return (
            <li key={s.label + i} id={`${inputId}-o${i}`} role="option" aria-selected={i === active} onMouseDown={e => { e.preventDefault(); pick(s) }} onMouseEnter={() => setActive(i)}
              className={`flex cursor-pointer items-center gap-3 px-3 py-2.5 text-sm ${i === active ? 'bg-coral-50' : ''}`}>
              <span aria-hidden className={`grid h-8 w-8 shrink-0 place-items-center rounded-full ${i === active ? 'bg-coral text-white' : 'bg-sand text-ink/50'}`}><KIcon className="h-4 w-4" /></span>
              <span className="min-w-0 flex-1"><span className="block truncate font-medium">{s.name}</span><span className="block truncate text-xs text-ink/55">{s.context || 'Popular destination'}</span></span>
              {kindLabel && <span className="badge bg-sky-50 text-sky-800">{kindLabel}</span>}
              {s.broad && <span className="badge bg-amber-100 text-amber-800">region</span>}
            </li>
          )})}
          <li className="px-3 py-1 text-[10px] text-ink/40" aria-hidden>{source}</li>
        </ul>
      )}
      {broadPick && !open && <p className="mt-1 text-xs text-amber-700">{broadPick.name} is a large region. For the best plan, pick a specific city or town.</p>}
    </div>
  )
}
export type { Json }
