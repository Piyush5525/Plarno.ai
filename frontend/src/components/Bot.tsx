import { ComponentProps, Suspense, lazy } from 'react'

const TripBot = lazy(() => import('./TripBot'))
export type { BotState, BotTrick } from './TripBot'

/** TRIP, loaded on demand: the 3D engine is large, so pages paint first and the bot pops in a moment later. */
export default function Bot(props: ComponentProps<typeof TripBot>) {
  const size = props.size ?? 120
  return (
    <Suspense fallback={<div style={{ width: size, height: size }} className="grid place-items-center" role="img" aria-label="TRIP is waking up"><span className="h-1/2 w-1/2 animate-pulse rounded-full bg-gradient-to-br from-coral/50 to-lagoon/50" /></div>}>
      <TripBot {...props} />
    </Suspense>
  )
}
