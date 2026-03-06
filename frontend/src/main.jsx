import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
)

// Register PWA service worker
import { registerSW } from 'virtual:pwa-register'

const updateSW = registerSW({
  immediate: true,
  onRegisteredSW(swUrl, registration) {
    console.log('[PWA] Service worker registered:', swUrl)
    // Check for updates every hour
    if (registration) {
      setInterval(() => { registration.update() }, 60 * 60 * 1000)
    }
  },
  onOfflineReady() {
    console.log('[PWA] App is ready to work offline')
  },
  onNeedRefresh() {
    // Auto-update: accept new service worker immediately
    console.log('[PWA] New content available, updating...')
    updateSW(true)
  },
  onRegisterError(error) {
    console.error('[PWA] Service worker registration failed:', error)
  },
})
