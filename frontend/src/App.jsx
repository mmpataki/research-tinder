import { useState, useEffect, useCallback, useRef, createContext } from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'
import { Flame, BookOpen, Settings, Archive } from 'lucide-react'
import SwipePage from './pages/SwipePage'
import ReadingListPage from './pages/ReadingListPage'
import SettingsPage from './pages/SettingsPage'
import StashPage from './pages/StashPage'
import { api } from './api'
import { getSwipeQueue, removeFromQueue, isOnline } from './cache'

export const AppContext = createContext()

// Preset accent palettes
export const ACCENT_PRESETS = [
  { label: 'Indigo',  value: '#6366f1' },
  { label: 'Violet',  value: '#8b5cf6' },
  { label: 'Fuchsia', value: '#d946ef' },
  { label: 'Rose',    value: '#f43f5e' },
  { label: 'Sky',     value: '#0ea5e9' },
  { label: 'Teal',    value: '#14b8a6' },
  { label: 'Emerald', value: '#10b981' },
  { label: 'Amber',   value: '#f59e0b' },
]

export default function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem('rt-theme') || 'dark')
  const [font, setFont] = useState(() => localStorage.getItem('rt-font') || 'system')
  const [accent, setAccentRaw] = useState(() => localStorage.getItem('rt-accent') || '#6366f1')
  const [syncToast, setSyncToast] = useState(null)
  const flushing = useRef(false)

  // ── Global offline-queue flush ────────────────────────────────────────────
  const flushQueue = useCallback(async () => {
    if (flushing.current || !isOnline()) return
    const queue = getSwipeQueue()
    if (queue.length === 0) return
    flushing.current = true
    let flushed = 0
    for (const { id, action } of queue) {
      try {
        await api.swipePaper(id, action)
        removeFromQueue(id)
        flushed++
      } catch {
        break
      }
    }
    flushing.current = false
    if (flushed > 0) {
      setSyncToast(`✓ Synced ${flushed} offline swipe${flushed > 1 ? 's' : ''}`)
      setTimeout(() => setSyncToast(null), 3000)
    }
  }, [])

  // Flush on mount, on 'online' event, and on visibility change (tab focus)
  useEffect(() => {
    flushQueue()
    const goOnline = () => flushQueue()
    const onVisibility = () => {
      if (document.visibilityState === 'visible' && isOnline()) flushQueue()
    }
    window.addEventListener('online', goOnline)
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      window.removeEventListener('online', goOnline)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [flushQueue])

  const setAccent = (color) => {
    setAccentRaw(color)
    localStorage.setItem('rt-accent', color)
  }

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('rt-theme', theme)
  }, [theme])

  useEffect(() => {
    document.documentElement.setAttribute('data-font', font)
    localStorage.setItem('rt-font', font)
  }, [font])

  useEffect(() => {
    // Derive hover color by lightening accent slightly (use a fixed offset approach)
    document.documentElement.style.setProperty('--accent', accent)
    document.documentElement.style.setProperty('--accent-hover', accent)
    document.documentElement.style.setProperty('--accent-dim', accent + '26') // 15% opacity
  }, [accent])

  return (
    <AppContext.Provider value={{ theme, setTheme, font, setFont, accent, setAccent }}>
      <div className="app">
        {syncToast && <div className="toast">{syncToast}</div>}
        <Routes>
          <Route path="/" element={<SwipePage />} />
          <Route path="/reading-list" element={<ReadingListPage />} />
          <Route path="/stash" element={<StashPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>

        <nav className="nav">
          <NavLink to="/" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} end>
            <Flame size={22} />
            <span>Swipe</span>
          </NavLink>
          <NavLink to="/reading-list" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <BookOpen size={22} />
            <span>Reading List</span>
          </NavLink>
          <NavLink to="/stash" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <Archive size={22} />
            <span>Stash</span>
          </NavLink>
          <NavLink to="/settings" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <Settings size={22} />
            <span>Settings</span>
          </NavLink>
        </nav>
      </div>
    </AppContext.Provider>
  )
}
