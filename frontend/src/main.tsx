import React, { Suspense, lazy } from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { MotionConfig } from 'framer-motion'
import './index.css'
import { AppProvider } from './store'
import { wakeBackend } from './api'
import Layout, { Protected } from './components/Layout'
import { Empty } from './components/ui'
const Landing = lazy(() => import('./pages/Landing'))
const Auth = lazy(() => import('./pages/Auth'))
const Workspace = lazy(() => import('./pages/Workspace'))
const Discover = lazy(() => import('./pages/Discover'))
const Transport = lazy(() => import('./pages/Transport'))
const Trips = lazy(() => import('./pages/Trips'))
const Profile = lazy(() => import('./pages/Profile'))
const Admin = lazy(() => import('./pages/Admin'))

class Boundary extends React.Component<{ children: React.ReactNode }, { err: Error | null }> {
  state = { err: null as Error | null }
  static getDerivedStateFromError(err: Error) { return { err } }
  render() {
    return this.state.err
      ? <div className="mx-auto mt-16 max-w-lg rounded-3xl border border-rose-200 bg-rose-50 p-8 text-center"><p className="font-display text-2xl font-bold">Something went wrong</p><p className="mt-2 text-sm text-rose-900/80">{this.state.err.message}</p><button className="btn btn-primary mt-5" onClick={() => location.reload()}>Reload the page</button></div>
      : this.props.children
  }
}

const PageLoading = () => <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-16 text-sm text-ink/60" role="status"><span className="h-4 w-4 animate-spin rounded-full border-2 border-ink/20 border-t-coral" />Loading…</div>
const NotFound = () => <div className="mx-auto max-w-xl px-4 py-20"><h1 className="sr-only">Page not found</h1><Empty title="This page took a wrong turn">The address does not match anything on Plarno.ai.<div className="mt-4 flex justify-center gap-2"><Link to="/" className="btn btn-primary">Back home</Link><Link to="/discover" className="btn btn-ghost">Explore a city</Link></div></Empty></div>

wakeBackend()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <Boundary>
    <MotionConfig reducedMotion="user">
      <BrowserRouter>
        <AppProvider>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<Suspense fallback={<PageLoading />}><Landing /></Suspense>} />
              <Route path="/auth" element={<Suspense fallback={<PageLoading />}><Auth /></Suspense>} />
              <Route path="/workspace" element={<Protected><Suspense fallback={<PageLoading />}><Workspace /></Suspense></Protected>} />
              <Route path="/discover" element={<Suspense fallback={<PageLoading />}><Discover /></Suspense>} />
              <Route path="/transport" element={<Suspense fallback={<PageLoading />}><Transport /></Suspense>} />
              <Route path="/trips" element={<Protected><Suspense fallback={<PageLoading />}><Trips /></Suspense></Protected>} />
              <Route path="/profile" element={<Protected><Suspense fallback={<PageLoading />}><Profile /></Suspense></Protected>} />
              <Route path="/admin" element={<Protected><Suspense fallback={<PageLoading />}><Admin /></Suspense></Protected>} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </AppProvider>
      </BrowserRouter>
    </MotionConfig>
  </Boundary>,
)
