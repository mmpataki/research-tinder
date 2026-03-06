import { useState, useEffect, useCallback, useRef } from 'react'
import { X, Heart, ExternalLink, RefreshCw, WifiOff } from 'lucide-react'
import { api } from '../api'
import SwipeCard from '../components/SwipeCard'
import {
  cacheFeed, getCachedFeed,
  cacheFavs, getCachedFavs,
  enqueueSwipe, getSwipeQueue,
  removePaperFromCache,
  isOnline,
} from '../cache'

export default function SwipePage() {
  const [papers, setPapers] = useState([])
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState(null)
  const [favoriteAuthors, setFavoriteAuthors] = useState([])
  const [online, setOnline] = useState(isOnline())
  const [queueLen, setQueueLen] = useState(() => getSwipeQueue().length)

  // ── helpers ─────────────────────────────────────────────────────────────────

  const refreshQueueLen = () => setQueueLen(getSwipeQueue().length)

  const showToast = (msg, duration = 3000) => {
    setToast(msg)
    setTimeout(() => setToast(null), duration)
  }

  // ── network event listeners ──────────────────────────────────────────────────

  useEffect(() => {
    const goOnline = () => { setOnline(true); refreshQueueLen() }
    const goOffline = () => setOnline(false)
    window.addEventListener('online', goOnline)
    window.addEventListener('offline', goOffline)
    return () => {
      window.removeEventListener('online', goOnline)
      window.removeEventListener('offline', goOffline)
    }
  }, [])

  // ── feed loading ─────────────────────────────────────────────────────────────

  const loadFeed = useCallback(async () => {
    setLoading(true)
    if (!isOnline()) {
      // Serve from cache
      const cached = getCachedFeed()
      const cachedFavs = getCachedFavs()
      setPapers((cached || []).map(p => ({ ...p, _forceSwipe: null })))
      setFavoriteAuthors(cachedFavs)
      setLoading(false)
      return
    }
    try {
      const [feedData, favData] = await Promise.all([
        api.getFeed(10),
        api.getFavoriteAuthors().catch(() => ({ authors: [] })),
      ])
      const papers = feedData.papers || []
      const favs = favData.authors || []
      setPapers(papers.map(p => ({ ...p, _forceSwipe: null })))
      setFavoriteAuthors(favs)
      // Update caches
      cacheFeed(papers)
      cacheFavs(favs)
    } catch {
      // Network failed — fall back to cache
      const cached = getCachedFeed()
      if (cached && cached.length > 0) {
        setPapers(cached.map(p => ({ ...p, _forceSwipe: null })))
        setFavoriteAuthors(getCachedFavs())
        showToast('⚠️ Offline — showing cached feed')
      } else {
        showToast('Could not load feed and no cache available')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadFeed() }, [loadFeed])

  // ── re-fetch on tab focus (cross-device consistency) ────────────────────────

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === 'visible' && isOnline()) loadFeed()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [loadFeed])

  // ── swipe handler ─────────────────────────────────────────────────────────────

  const handleSwipe = async (action) => {
    if (papers.length === 0) return
    const paper = papers[papers.length - 1]

    // Optimistically remove from UI + cache immediately
    setPapers(prev => prev.slice(0, -1))
    removePaperFromCache(paper.id)

    if (!isOnline()) {
      // Queue for later
      enqueueSwipe(paper.id, action)
      refreshQueueLen()
    } else {
      try {
        await api.swipePaper(paper.id, action)
      } catch {
        // Commit failed — push to queue so it retries
        enqueueSwipe(paper.id, action)
        refreshQueueLen()
      }
      // Pre-fetch more cards when running low
      if (papers.length <= 3) {
        try {
          const data = await api.getFeed(10)
          const fresh = data.papers || []
          setPapers(prev => {
            const existingIds = new Set(prev.map(p => p.id))
            const newOnes = fresh.filter(p => !existingIds.has(p.id))
            return [...newOnes.map(p => ({ ...p, _forceSwipe: null })), ...prev]
          })
          cacheFeed(fresh)
        } catch {}
      }
    }
  }

  const handleButtonSwipe = (action) => {
    if (papers.length === 0) return
    setPapers(prev => {
      const updated = [...prev]
      updated[updated.length - 1] = { ...updated[updated.length - 1], _forceSwipe: action }
      return updated
    })
  }

  const topPaper = papers.length > 0 ? papers[papers.length - 1] : null

  return (
    <div className="page" style={{ display: 'flex', flexDirection: 'column', height: 'calc(100% - 58px)' }}>
      {/* Offline banner */}
      {!online && (
        <div className="offline-banner">
          <WifiOff size={14} />
          Offline — swiping from cache
          {queueLen > 0 && (
            <span className="offline-queue">{queueLen} swipe{queueLen > 1 ? 's' : ''} queued</span>
          )}
        </div>
      )}


      <div className="header">
        <h1>Research Tinder</h1>
        <div className="subtitle">Swipe through today's papers</div>
      </div>

      {toast && <div className="toast">{toast}</div>}

      {loading ? (
        <div className="loading"><div className="spinner" /></div>
      ) : papers.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📄</div>
          <h3>No papers to swipe</h3>
          <p>{online ? 'Fetch new papers from Settings, or wait for the daily scrape.' : 'You\'ve gone through all cached papers. Connect to load more.'}</p>
          <button className="btn btn-primary" onClick={loadFeed}>
            <RefreshCw size={16} /> Refresh
          </button>
        </div>
      ) : (
        <>
          <div className="card-stack">
            {papers.slice(-3).map((paper, i, arr) => (
              <SwipeCard
                key={paper.id}
                paper={paper}
                isTop={i === arr.length - 1}
                onSwipe={handleSwipe}
                favoriteAuthors={favoriteAuthors}
                style={{
                  scale: 1 - (arr.length - 1 - i) * 0.03,
                  translateY: (arr.length - 1 - i) * 8,
                }}
              />
            ))}
          </div>

          <div className="swipe-actions">
            <button className="action-btn pass-btn" onClick={() => handleButtonSwipe('pass')} title="Skip">
              <X size={28} />
            </button>
            {topPaper && (
              <a href={topPaper.pdf_url} target="_blank" rel="noopener noreferrer" className="action-btn link-btn" title="Open PDF">
                <ExternalLink size={18} />
              </a>
            )}
            <button className="action-btn like-btn" onClick={() => handleButtonSwipe('like')} title="Add to reading list">
              <Heart size={28} />
            </button>
          </div>
        </>
      )}
    </div>
  )
}

