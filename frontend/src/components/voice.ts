// Configurable voice provider architecture. Default provider: browser Web Speech API (no keys, no data sent by us).
// To use a cloud STT/TTS, implement VoiceProvider and register it in `providers`.
export interface VoiceProvider {
  name: string
  supportsSTT: boolean
  supportsTTS: boolean
  listen(opts: { lang: string; onResult: (text: string, final: boolean) => void; onEnd: () => void; onError: (msg: string) => void }): () => void
  speak(text: string, opts: { rate: number; voiceURI?: string; lang: string; onEnd: () => void }): void
  stopSpeaking(): void
}

type SR = { start(): void; stop(): void; abort(): void; lang: string; interimResults: boolean; continuous: boolean
  onresult: (e: any) => void; onerror: (e: any) => void; onend: () => void }

const Ctor = (typeof window !== 'undefined' && ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition)) as (new () => SR) | false

const ERRORS: Record<string, string> = {
  'not-allowed': 'Microphone permission was denied. Allow microphone access in your browser settings to use voice.',
  'service-not-allowed': 'Speech recognition is blocked by the browser or OS.',
  'no-speech': 'I did not hear anything. Try again.',
  'audio-capture': 'No microphone was found.',
  network: 'Speech recognition needs a network connection in this browser.',
}

export const webSpeech: VoiceProvider = {
  name: 'Browser Web Speech API',
  supportsSTT: !!Ctor,
  supportsTTS: typeof window !== 'undefined' && 'speechSynthesis' in window,
  listen({ lang, onResult, onEnd, onError }) {
    if (!Ctor) { onError('Speech recognition is not supported in this browser (try Chrome or Edge).'); onEnd(); return () => {} }
    const rec = new Ctor()
    rec.lang = lang; rec.interimResults = true; rec.continuous = false
    rec.onresult = e => {
      const r = e.results[e.results.length - 1]
      onResult(r[0].transcript, r.isFinal)
    }
    rec.onerror = e => onError(ERRORS[e.error] ?? `Voice error: ${e.error}`)
    rec.onend = onEnd
    try { rec.start() } catch { onError('Could not start the microphone.') }
    return () => { try { rec.abort() } catch { /* ignore */ } }
  },
  speak(text, { rate, voiceURI, lang, onEnd }) {
    if (!this.supportsTTS) { onEnd(); return }
    window.speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text.replace(/[*_#`]/g, ''))
    u.rate = rate; u.lang = lang
    const v = window.speechSynthesis.getVoices().find(v => v.voiceURI === voiceURI)
    if (v) u.voice = v
    u.onend = onEnd; u.onerror = onEnd
    window.speechSynthesis.speak(u)
  },
  stopSpeaking() { if (this.supportsTTS) window.speechSynthesis.cancel() },
}

export const providers: Record<string, VoiceProvider> = { web: webSpeech }
