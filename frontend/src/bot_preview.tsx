import ReactDOM from 'react-dom/client'
import TripBot, { BotState } from './components/TripBot'

const STATES: BotState[] = ['idle', 'hover', 'listening', 'thinking', 'speaking', 'success', 'error', 'acting']
ReactDOM.createRoot(document.getElementById('root')!).render(
  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, padding: 16, fontFamily: 'sans-serif' }}>
    {STATES.map(s => <div key={s} style={{ textAlign: 'center' }}><TripBot state={s} size={260} /><div>{s}</div></div>)}
  </div>,
)
