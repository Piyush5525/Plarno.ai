import { MutableRefObject, useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { Sparkles } from '@react-three/drei'
import { AnimatePresence, motion } from 'framer-motion'
import * as THREE from 'three'

export type BotState = 'idle' | 'hover' | 'listening' | 'thinking' | 'speaking' | 'success' | 'error' | 'acting'
/** Short one-off performances the bot plays when you poke it. */
export type BotTrick = 'spin' | 'jump' | 'dance' | 'wink' | 'love' | 'nod' | 'peek'
const TRICKS: BotTrick[] = ['jump', 'spin', 'wink', 'dance', 'love', 'nod', 'peek']
const TRICK_MS: Record<BotTrick, number> = { spin: 1100, jump: 900, dance: 2200, wink: 900, love: 1800, nod: 900, peek: 1400 }
const TRICK_SAY: Record<BotTrick, string> = { spin: 'Wheee!', jump: 'Boing!', dance: 'Holiday mode!', wink: 'Gotcha', love: 'Aww, thanks!', nod: 'Yes, let\'s go!', peek: 'Peekaboo!' }

const EYE: Record<BotState, string> = {
  idle: '#7cf5e1', hover: '#a7f3d0', listening: '#7dd3fc', thinking: '#c4b5fd', speaking: '#7cf5e1', success: '#bef264', error: '#fda4af', acting: '#fde68a',
}
const reduceMotion = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/** Live input shared between the DOM wrapper and the render loop without re-rendering React. */
type Ctl = { px: number; py: number; yaw: number; dragging: boolean; asleep: boolean; wokeAt: number; trick: BotTrick | null; trickAt: number }

function Bot({ state, ctl }: { state: BotState; ctl: MutableRefObject<Ctl> }) {
  const root = useRef<THREE.Group>(null)
  const spin = useRef<THREE.Group>(null)
  const body = useRef<THREE.Group>(null)
  const head = useRef<THREE.Group>(null)
  const eyes = useRef<THREE.Group>(null)
  const eyeL = useRef<THREE.Mesh>(null)
  const eyeR = useRef<THREE.Mesh>(null)
  const happy = useRef<THREE.Group>(null)
  const open = useRef<THREE.Group>(null)
  const smile = useRef<THREE.Mesh>(null)
  const prop = useRef<THREE.Group>(null)
  const armL = useRef<THREE.Group>(null)
  const armR = useRef<THREE.Group>(null)
  const earL = useRef<THREE.Mesh>(null)
  const earR = useRef<THREE.Mesh>(null)
  const bulb = useRef<THREE.Mesh>(null)
  const dots = useRef<THREE.Group>(null)
  const sweat = useRef<THREE.Mesh>(null)
  const shadow = useRef<THREE.Mesh>(null)
  const plane = useRef<THREE.Group>(null)
  const scarf = useRef<THREE.Mesh>(null)
  const tint = useMemo(() => new THREE.Color(EYE.idle), [])
  const target = useMemo(() => new THREE.Color(), [])
  const yaw = useRef(0)

  useFrame(({ clock }, dt) => {
    const t = clock.getElapsedTime()
    const c = ctl.current
    const m = reduceMotion ? 0.15 : 1
    const now = performance.now()
    const tk = c.trick && now - c.trickAt < TRICK_MS[c.trick] ? c.trick : null
    const k = tk ? (now - c.trickAt) / TRICK_MS[tk] : 0  // 0..1 through the trick
    const asleep = c.asleep && state === 'idle' && !tk
    const startled = now - c.wokeAt < 500
    target.set(tk === 'love' ? '#fda4af' : EYE[state]); tint.lerp(target, 0.15)
    const isHappy = state === 'hover' || state === 'success' || tk === 'love' || tk === 'dance' || tk === 'jump'

    let bounce = state === 'success' ? Math.abs(Math.sin(t * 7)) * 0.42 : state === 'speaking' ? Math.abs(Math.sin(t * 9)) * 0.08 : Math.sin(t * (asleep ? 1.1 : 2.1)) * 0.07 * m
    if (tk === 'jump') bounce = Math.sin(k * Math.PI) * 1.05
    if (tk === 'dance') bounce = Math.abs(Math.sin(t * 9)) * 0.22
    if (tk === 'peek') bounce = -Math.sin(k * Math.PI) * 0.9
    if (root.current) {
      root.current.position.y = THREE.MathUtils.lerp(root.current.position.y, bounce, tk ? 0.5 : 0.35)
      root.current.position.x = state === 'error' ? Math.sin(t * 38) * 0.05 : tk === 'dance' ? Math.sin(t * 4.5) * 0.28 : THREE.MathUtils.lerp(root.current.position.x, 0, 0.2)
      root.current.rotation.z = state === 'error' ? Math.sin(t * 20) * 0.05 : tk === 'dance' ? Math.sin(t * 9) * 0.22 : Math.sin(t * 1.3) * 0.03 * m
    }
    if (spin.current) {  // drag to turn, springs back when released; the spin trick does a full turn
      yaw.current = THREE.MathUtils.lerp(yaw.current, c.dragging ? c.yaw : 0, c.dragging ? 0.35 : 0.08)
      const ease = 1 - Math.pow(1 - k, 3)
      spin.current.rotation.y = yaw.current + (tk === 'spin' ? ease * Math.PI * 2 : 0)
    }
    if (body.current) {  // squash & stretch
      let s = Math.sin(t * 2.1) * 0.025 * m + (state === 'success' ? Math.sin(t * 7) * 0.05 : 0)
      if (tk === 'jump') s = k < 0.15 ? -0.16 : k > 0.85 ? -0.14 : 0.1
      body.current.scale.set(1 - s, 1 + s, 1 - s)
    }
    if (head.current) {  // look at the pointer anywhere on the page
      let tx = state === 'thinking' ? -0.35 : c.px * 0.6
      let ty = state === 'thinking' ? 0.25 : -c.py * 0.38
      if (asleep) { tx = 0.12; ty = 0.34 }
      if (tk === 'nod') ty = Math.sin(k * Math.PI * 4) * 0.4
      head.current.rotation.y = THREE.MathUtils.lerp(head.current.rotation.y, tx, 0.1)
      head.current.rotation.x = THREE.MathUtils.lerp(head.current.rotation.x, ty, tk === 'nod' ? 0.35 : 0.1)
      head.current.rotation.z = THREE.MathUtils.lerp(head.current.rotation.z, tk === 'wink' ? -0.18 : state === 'listening' ? 0.12 : 0, 0.15)
    }
    const blink = !isHappy && (t % 3.6) > 3.47 ? 0.08 : 1
    ;[eyeL.current, eyeR.current].forEach((e, i) => {
      if (!e) return
      e.visible = !isHappy
      const wide = startled ? 1.35 : state === 'listening' ? 1.15 : state === 'error' ? 0.7 : 1
      const shut = asleep ? 0.06 : tk === 'wink' && i === 0 ? 0.06 : blink
      e.scale.set(startled ? 1.2 : 1, shut * wide, 1)
      ;(e.material as THREE.MeshStandardMaterial).emissive.copy(tint)
    })
    if (eyes.current) {
      eyes.current.position.x = THREE.MathUtils.lerp(eyes.current.position.x, asleep ? 0 : c.px * 0.08, 0.12)
      eyes.current.position.y = THREE.MathUtils.lerp(eyes.current.position.y, state === 'thinking' ? 0.08 : asleep ? -0.03 : -c.py * 0.06, 0.12)
    }
    if (happy.current) {
      happy.current.visible = isHappy
      happy.current.children.forEach(ch => { ((ch as THREE.Mesh).material as THREE.MeshStandardMaterial).emissive.copy(tint) })
    }
    if (smile.current) {
      smile.current.visible = state !== 'speaking'
      smile.current.rotation.z = state === 'error' ? 0 : Math.PI  // frown on error, smile otherwise
      smile.current.scale.setScalar(isHappy ? 1.35 : asleep ? 0.7 : 1)
      ;(smile.current.material as THREE.MeshStandardMaterial).emissive.copy(tint)
    }
    if (open.current) {
      open.current.visible = state === 'speaking'
      open.current.scale.set(1, 0.35 + Math.abs(Math.sin(t * 13)) * 0.9, 1)
    }
    if (prop.current) prop.current.rotation.y += dt * (tk === 'jump' || tk === 'spin' ? 30 : state === 'thinking' || state === 'acting' ? 22 : state === 'success' ? 14 : asleep ? 0.6 : 3) * (reduceMotion ? 0.3 : 1)
    const waving = state === 'hover' || state === 'success' || tk === 'love'
    const wave = waving ? Math.sin(t * 12) * 0.5 : state === 'acting' ? Math.sin(t * 16) * 0.4 : 0
    let aR = (waving ? -2.3 : -0.45) + wave
    let aL = (state === 'success' ? 2.3 : 0.45) + (state === 'acting' ? -wave : 0)
    if (tk === 'dance') { aR = -1.6 + Math.sin(t * 9) * 0.9; aL = 1.6 + Math.sin(t * 9) * 0.9 }
    if (tk === 'jump') { aR = -2.6; aL = 2.6 }
    if (tk === 'peek') { aR = -2.9; aL = 2.9 }
    if (asleep) { aR = -0.2; aL = 0.2 }
    if (armR.current) armR.current.rotation.z = THREE.MathUtils.lerp(armR.current.rotation.z, aR, 0.2)
    if (armL.current) armL.current.rotation.z = THREE.MathUtils.lerp(armL.current.rotation.z, aL, 0.2)
    const glow = state === 'listening' ? 0.6 + Math.abs(Math.sin(t * 6)) * 1.6 : 0.15
    ;[earL.current, earR.current].forEach(e => { if (e) { (e.material as THREE.MeshStandardMaterial).emissive.set(state === 'listening' ? '#38bdf8' : '#ff6f61'); (e.material as THREE.MeshStandardMaterial).emissiveIntensity = glow; e.scale.setScalar(state === 'listening' ? 1 + Math.sin(t * 6) * 0.12 : 1) } })
    if (bulb.current) (bulb.current.material as THREE.MeshStandardMaterial).emissiveIntensity = asleep ? 0.15 : 0.6 + Math.sin(t * (state === 'thinking' ? 10 : 3)) * 0.4
    if (dots.current) { dots.current.visible = state === 'thinking'; dots.current.rotation.y = t * 3.2 }
    if (sweat.current) { sweat.current.visible = state === 'error'; sweat.current.position.y = 0.55 - ((t * 1.4) % 1) * 0.35 }
    if (shadow.current) { const sc = 1 - (root.current?.position.y ?? 0) * 0.5; shadow.current.scale.set(1.2 * Math.max(0.4, sc), 0.28 * Math.max(0.4, sc), 1) }
    if (plane.current) {  // a paper plane circling the bot: faster while it works on something
      const busy = state === 'thinking' || state === 'acting'
      plane.current.visible = !asleep
      const a = t * (busy ? 3.4 : 0.9) * (reduceMotion ? 0.3 : 1)
      plane.current.position.set(Math.cos(a) * 1.75, 0.55 + Math.sin(a * 2) * 0.22, Math.sin(a) * 1.75)
      plane.current.rotation.set(Math.sin(a * 2) * 0.25, -a, 0.35)
    }
    if (scarf.current) scarf.current.rotation.z = Math.sin(t * 2.4) * 0.04
  })

  const glossy = { roughness: 0.28, metalness: 0.05 }
  return (
    <group>
      <mesh ref={shadow} position={[0, -1.35, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[1, 32]} /><meshBasicMaterial color="#0b3b4a" transparent opacity={0.22} />
      </mesh>
      <group ref={plane}>
        <mesh rotation={[0, 0, -Math.PI / 2]}><coneGeometry args={[0.1, 0.34, 3]} /><meshStandardMaterial color="#ffffff" emissive="#bfe9ff" emissiveIntensity={0.5} flatShading /></mesh>
        <mesh position={[-0.2, 0, 0]}><sphereGeometry args={[0.03, 8, 8]} /><meshBasicMaterial color="#ffc24b" /></mesh>
      </group>
      <group ref={root}>
        <group ref={spin}>
          <group ref={body}>
            {/* torso */}
            <mesh position={[0, -0.55, 0]} scale={[0.78, 0.68, 0.7]}><sphereGeometry args={[1, 32, 32]} /><meshStandardMaterial color="#ffffff" emissive="#fff1dc" emissiveIntensity={0.3} {...glossy} /></mesh>
            <mesh position={[0, -0.5, 0.58]} scale={[0.36, 0.3, 0.2]}><sphereGeometry args={[1, 24, 24]} /><meshStandardMaterial color="#ffc24b" emissive="#ffc24b" emissiveIntensity={0.25} {...glossy} /></mesh>
            {/* travel backpack (seen when you turn it around) */}
            <mesh position={[0, -0.45, -0.62]} scale={[0.5, 0.52, 0.3]}><sphereGeometry args={[1, 20, 20]} /><meshStandardMaterial color="#0fa596" {...glossy} /></mesh>
            <mesh position={[0, -0.6, -0.9]} scale={[0.28, 0.2, 0.1]}><sphereGeometry args={[1, 16, 16]} /><meshStandardMaterial color="#ffc24b" {...glossy} /></mesh>
            {[-0.3, 0.3].map(x => <mesh key={x} position={[x, -0.28, 0.05]} rotation={[0.25, 0, x < 0 ? 0.28 : -0.28]}><torusGeometry args={[0.52, 0.035, 8, 24, Math.PI]} /><meshStandardMaterial color="#0b8a7e" /></mesh>)}
            {/* scarf */}
            <mesh ref={scarf} position={[0, -0.02, 0.02]} rotation={[Math.PI / 2, 0, 0]} scale={[1, 0.92, 1]}><torusGeometry args={[0.6, 0.1, 12, 32]} /><meshStandardMaterial color="#f4553f" {...glossy} /></mesh>
            <mesh position={[0.34, -0.3, 0.52]} rotation={[0, 0, -0.25]} scale={[0.1, 0.26, 0.05]}><sphereGeometry args={[1, 12, 12]} /><meshStandardMaterial color="#f4553f" {...glossy} /></mesh>
            {/* feet */}
            {[-0.34, 0.34].map(x => <mesh key={x} position={[x, -1.18, 0.1]} scale={[0.3, 0.17, 0.38]}><sphereGeometry args={[1, 16, 16]} /><meshStandardMaterial color="#ff6f61" {...glossy} /></mesh>)}
            {/* arms */}
            <group ref={armL} position={[-0.72, -0.35, 0]}><mesh position={[-0.02, -0.28, 0]}><capsuleGeometry args={[0.12, 0.3, 6, 12]} /><meshStandardMaterial color="#fff7ed" {...glossy} /></mesh><mesh position={[0, -0.6, 0]}><sphereGeometry args={[0.15, 16, 16]} /><meshStandardMaterial color="#ff6f61" {...glossy} /></mesh></group>
            <group ref={armR} position={[0.72, -0.35, 0]}><mesh position={[0.02, -0.28, 0]}><capsuleGeometry args={[0.12, 0.3, 6, 12]} /><meshStandardMaterial color="#fff7ed" {...glossy} /></mesh><mesh position={[0, -0.6, 0]}><sphereGeometry args={[0.15, 16, 16]} /><meshStandardMaterial color="#ff6f61" {...glossy} /></mesh></group>
            {/* head */}
            <group ref={head} position={[0, 0.38, 0]}>
              <mesh scale={[1.12, 0.98, 1.0]}><sphereGeometry args={[1, 40, 40]} /><meshPhysicalMaterial color="#ffffff" roughness={0.25} clearcoat={0.8} clearcoatRoughness={0.2} emissive="#dff6ff" emissiveIntensity={0.35} /></mesh>
              {/* ears */}
              {[-1, 1].map(s => <mesh key={s} ref={s < 0 ? earL : earR} position={[s * 1.1, 0, 0]} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[0.26, 0.26, 0.14, 24]} /><meshStandardMaterial color="#ff6f61" emissive="#ff6f61" emissiveIntensity={0.15} {...glossy} /></mesh>)}
              {/* visor */}
              <mesh position={[0, -0.02, 0.5]} scale={[0.88, 0.66, 0.55]}><sphereGeometry args={[1, 40, 40]} /><meshStandardMaterial color="#10283f" roughness={0.12} metalness={0.4} /></mesh>
              <group ref={eyes} position={[0, 0.06, 0.98]}>
                {[-0.34, 0.34].map(x => (
                  <group key={x} position={[x, 0, 0]}>
                    <mesh ref={x < 0 ? eyeL : eyeR}><sphereGeometry args={[0.19, 24, 24]} /><meshStandardMaterial color="#06201f" emissive={EYE.idle} emissiveIntensity={1.5} toneMapped={false} /></mesh>
                    <mesh position={[0.06, 0.07, 0.15]}><sphereGeometry args={[0.055, 12, 12]} /><meshBasicMaterial color="#ffffff" /></mesh>
                    <mesh position={[-0.05, -0.06, 0.16]}><sphereGeometry args={[0.025, 10, 10]} /><meshBasicMaterial color="#ffffff" /></mesh>
                  </group>
                ))}
                <group ref={happy}>
                  {[-0.34, 0.34].map(x => <mesh key={x} position={[x, -0.04, 0.05]}><torusGeometry args={[0.15, 0.045, 10, 24, Math.PI]} /><meshStandardMaterial color="#06201f" emissive={EYE.hover} emissiveIntensity={1.5} toneMapped={false} /></mesh>)}
                </group>
              </group>
              {/* cheeks */}
              {[-0.66, 0.66].map(x => <mesh key={x} position={[x, -0.22, 0.88]} rotation={[0, x < 0 ? -0.45 : 0.45, 0]}><circleGeometry args={[0.12, 20]} /><meshBasicMaterial color="#ff8fa3" transparent opacity={0.85} /></mesh>)}
              {/* mouth */}
              <mesh ref={smile} position={[0, -0.28, 0.99]}><torusGeometry args={[0.1, 0.022, 8, 20, Math.PI]} /><meshStandardMaterial color="#06201f" emissive={EYE.idle} emissiveIntensity={1.5} toneMapped={false} /></mesh>
              <group ref={open} position={[0, -0.3, 0.99]}><mesh><sphereGeometry args={[0.1, 16, 16]} /><meshStandardMaterial color="#ff7a90" emissive="#ff7a90" emissiveIntensity={0.5} /></mesh></group>
              {/* propeller beanie */}
              <mesh position={[0, 0.82, 0]} scale={[1, 0.72, 1]}><sphereGeometry args={[0.62, 28, 16, 0, Math.PI * 2, 0, Math.PI / 2]} /><meshStandardMaterial color="#ff6f61" {...glossy} /></mesh>
              <mesh position={[0, 0.8, 0]}><torusGeometry args={[0.6, 0.05, 10, 32]} /><meshStandardMaterial color="#ffc24b" {...glossy} /></mesh>
              <mesh position={[0, 1.34, 0]}><cylinderGeometry args={[0.03, 0.03, 0.14, 8]} /><meshStandardMaterial color="#fff7ed" /></mesh>
              <group ref={prop} position={[0, 1.44, 0]}>
                <mesh position={[0.28, 0, 0]} rotation={[0, 0, 0.1]}><boxGeometry args={[0.56, 0.025, 0.14]} /><meshStandardMaterial color="#38bdf8" {...glossy} /></mesh>
                <mesh position={[-0.28, 0, 0]} rotation={[0, 0, -0.1]}><boxGeometry args={[0.56, 0.025, 0.14]} /><meshStandardMaterial color="#ffc24b" {...glossy} /></mesh>
              </group>
              <mesh ref={bulb} position={[0, 1.5, 0]}><sphereGeometry args={[0.05, 12, 12]} /><meshStandardMaterial color="#ffffff" emissive="#fde68a" emissiveIntensity={0.8} /></mesh>
              {/* thinking dots + sweat */}
              <group ref={dots} position={[0, 1.15, 0]}>{[0, 1, 2].map(i => <mesh key={i} position={[Math.cos((i * 2 * Math.PI) / 3) * 0.85, 0, Math.sin((i * 2 * Math.PI) / 3) * 0.85]}><sphereGeometry args={[0.07, 10, 10]} /><meshStandardMaterial color="#c4b5fd" emissive="#c4b5fd" emissiveIntensity={1} /></mesh>)}</group>
              <mesh ref={sweat} position={[0.85, 0.5, 0.6]} scale={[0.7, 1, 0.7]}><sphereGeometry args={[0.08, 10, 10]} /><meshStandardMaterial color="#7dd3fc" emissive="#7dd3fc" emissiveIntensity={0.6} /></mesh>
            </group>
          </group>
        </group>
      </group>
    </group>
  )
}

/** TRIP the travel bot. Its head and eyes follow the cursor across the whole page, it dozes off when left alone and wakes when you
 *  come back, and with `interactive` you can click it for a random trick or drag sideways to turn it around (there is a backpack). */
export default function TripBot({ state, size = 120, interactive = false, trick, onTrick, say = true }: {
  state: BotState; size?: number; interactive?: boolean; trick?: { name: BotTrick; id: number } | null; onTrick?: (t: BotTrick) => void; say?: boolean
}) {
  const wrap = useRef<HTMLDivElement>(null)
  const ctl = useRef<Ctl>({ px: 0, py: 0, yaw: 0, dragging: false, asleep: false, wokeAt: 0, trick: null, trickAt: 0 })
  const lastMove = useRef(performance.now())
  const drag = useRef<{ x: number; moved: boolean } | null>(null)
  const next = useRef(0)
  const [asleep, setAsleep] = useState(false)
  const [fx, setFx] = useState<{ id: number; trick: BotTrick } | null>(null)

  useEffect(() => {  // follow the pointer anywhere on the page, and notice when nobody is around
    const move = (e: PointerEvent) => {
      const r = wrap.current?.getBoundingClientRect()
      if (!r) return
      ctl.current.px = Math.max(-1, Math.min(1, (e.clientX - (r.left + r.width / 2)) / (window.innerWidth / 2)))
      ctl.current.py = Math.max(-1, Math.min(1, (e.clientY - (r.top + r.height / 2)) / (window.innerHeight / 2)))
      lastMove.current = performance.now()
      if (ctl.current.asleep) { ctl.current.asleep = false; ctl.current.wokeAt = performance.now(); setAsleep(false) }
    }
    const wake = () => { lastMove.current = performance.now(); if (ctl.current.asleep) { ctl.current.asleep = false; ctl.current.wokeAt = performance.now(); setAsleep(false) } }
    window.addEventListener('pointermove', move, { passive: true })
    window.addEventListener('keydown', wake)
    const iv = window.setInterval(() => {
      if (!ctl.current.asleep && performance.now() - lastMove.current > 28000) { ctl.current.asleep = true; setAsleep(true) }
    }, 1000)
    return () => { window.removeEventListener('pointermove', move); window.removeEventListener('keydown', wake); window.clearInterval(iv) }
  }, [])

  const play = (name: BotTrick) => {
    ctl.current.trick = name; ctl.current.trickAt = performance.now()
    const id = Date.now()
    setFx({ id, trick: name }); onTrick?.(name)
    window.setTimeout(() => setFx(f => (f?.id === id ? null : f)), Math.max(1500, TRICK_MS[name]))
  }
  useEffect(() => { if (trick) play(trick.name) }, [trick?.id])

  const handlers = interactive ? {
    onPointerDown: (e: React.PointerEvent) => { drag.current = { x: e.clientX, moved: false }; (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId) },
    onPointerMove: (e: React.PointerEvent) => {
      if (!drag.current) return
      const dx = e.clientX - drag.current.x
      if (Math.abs(dx) > 6) { drag.current.moved = true; ctl.current.dragging = true }
      ctl.current.yaw = (dx / size) * 3.2
    },
    onPointerUp: () => {
      const d = drag.current; drag.current = null; ctl.current.dragging = false
      if (d && !d.moved) { play(TRICKS[next.current % TRICKS.length]); next.current++ }
    },
    onPointerCancel: () => { drag.current = null; ctl.current.dragging = false },
    onKeyDown: (e: React.KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); play(TRICKS[next.current % TRICKS.length]); next.current++ } },
  } : {}

  const sleeping = asleep && state === 'idle'
  return (
    <div ref={wrap} style={{ width: size, height: size, touchAction: interactive ? 'pan-y' : undefined }} className={`relative select-none ${interactive ? 'cursor-grab active:cursor-grabbing' : ''}`}
      role={interactive ? 'button' : 'img'} tabIndex={interactive ? 0 : undefined}
      aria-label={interactive ? 'TRIP the travel bot. Press to see a trick, drag to turn it around.' : `TRIP, your travel assistant, is ${sleeping ? 'napping' : state}`} {...handlers}>
      <Canvas camera={{ position: [0, 0.15, 6.2], fov: 36 }} dpr={[1, 1.75]} gl={{ alpha: true, antialias: true }} style={{ pointerEvents: 'none' }}>
        <ambientLight intensity={1.15} />
        <directionalLight position={[3, 5, 5]} intensity={2.2} color="#fff4e0" />
        <pointLight position={[-4, 1, 3]} intensity={18} color="#7dd3fc" />
        <pointLight position={[3, -2, 4]} intensity={10} color="#ff9f8a" />
        <Bot state={state} ctl={ctl} />
        {(state === 'success' || state === 'hover' || fx) && <Sparkles count={fx ? 26 : 14} scale={[3.2, 3.2, 1]} size={fx ? 6 : 4} speed={1.4} color={fx?.trick === 'love' ? '#ff8fa3' : '#ffc24b'} />}
      </Canvas>
      {/* overlays: crisp HTML on top of the 3D canvas */}
      <AnimatePresence>
        {sleeping && [0, 1, 2].map(i => (
          <motion.span key={'z' + i} aria-hidden className="pointer-events-none absolute font-display font-bold text-sky" style={{ right: '18%', top: '16%', fontSize: size * (0.07 + i * 0.025) }}
            initial={{ opacity: 0, x: 0, y: 0 }} animate={{ opacity: [0, 1, 0], x: 8 + i * size * 0.05, y: -(10 + i * size * 0.07) }} exit={{ opacity: 0 }} transition={{ duration: 2.4, repeat: Infinity, delay: i * 0.6 }}>z</motion.span>
        ))}
        {fx?.trick === 'love' && [0, 1, 2, 3, 4].map(i => (
          <motion.span key={fx.id + 'h' + i} aria-hidden className="pointer-events-none absolute text-coral" style={{ left: `${30 + i * 10}%`, top: '34%', fontSize: size * 0.1 }}
            initial={{ opacity: 0, y: 0, scale: 0.4 }} animate={{ opacity: [0, 1, 0], y: -size * (0.3 + (i % 3) * 0.08), scale: 1.1, x: (i - 2) * 6 }} transition={{ duration: 1.4, delay: i * 0.12 }}>♥</motion.span>
        ))}
        {fx && say && size >= 150 && (
          <motion.span key={fx.id + 'say'} aria-hidden className="pointer-events-none absolute left-1/2 top-[2%] whitespace-nowrap rounded-full bg-white px-3 py-1 text-xs font-bold text-ink shadow-lift"
            initial={{ opacity: 0, y: 8, x: '-50%', scale: 0.8 }} animate={{ opacity: 1, y: 0, x: '-50%', scale: 1 }} exit={{ opacity: 0, y: -6, x: '-50%' }}>{TRICK_SAY[fx.trick]}</motion.span>
        )}
      </AnimatePresence>
    </div>
  )
}
