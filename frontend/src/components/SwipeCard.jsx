import { useState, useRef, useCallback, useEffect } from 'react'
import { Link } from 'lucide-react'

/**
 * SwipeCard — a draggable card that detects left/right swipe gestures.
 * Uses pointer events for cross-platform (mouse + touch) support.
 */
export default function SwipeCard({ paper, onSwipe, style, isTop, favoriteAuthors = [] }) {
  const cardRef = useRef(null)
  const startX = useRef(0)
  const startY = useRef(0)
  const currentX = useRef(0)
  const [dragX, setDragX] = useState(0)
  const [dragging, setDragging] = useState(false)
  const [exiting, setExiting] = useState(null) // 'left' | 'right' | null
  const directionLocked = useRef(null) // 'horizontal' | 'vertical' | null

  const SWIPE_THRESHOLD = 100
  const LOCK_THRESHOLD = 8 // px before we decide scroll vs swipe

  const handlePointerDown = useCallback((e) => {
    if (!isTop) return
    startX.current = e.clientX
    startY.current = e.clientY
    currentX.current = e.clientX
    directionLocked.current = null
    setDragging(true)
  }, [isTop])

  const handlePointerMove = useCallback((e) => {
    if (!dragging) return
    const dx = e.clientX - startX.current
    const dy = e.clientY - startY.current

    // Lock direction on first significant movement
    if (!directionLocked.current) {
      if (Math.abs(dx) > LOCK_THRESHOLD || Math.abs(dy) > LOCK_THRESHOLD) {
        directionLocked.current = Math.abs(dx) > Math.abs(dy) ? 'horizontal' : 'vertical'
        if (directionLocked.current === 'horizontal') {
          // Capture pointer to prevent scroll and get all future events
          cardRef.current?.setPointerCapture(e.pointerId)
        }
      }
      return
    }

    // Vertical → let browser scroll, don't drag card
    if (directionLocked.current === 'vertical') return

    currentX.current = e.clientX
    setDragX(dx)
  }, [dragging])

  const handlePointerUp = useCallback((e) => {
    if (!dragging) return
    setDragging(false)
    const wasHorizontal = directionLocked.current === 'horizontal'
    directionLocked.current = null

    if (!wasHorizontal) {
      setDragX(0)
      return
    }

    const dx = currentX.current - startX.current

    if (Math.abs(dx) > SWIPE_THRESHOLD) {
      const direction = dx > 0 ? 'right' : 'left'
      setExiting(direction)
      setTimeout(() => {
        onSwipe(direction === 'right' ? 'like' : 'pass')
      }, 300)
    } else {
      setDragX(0)
    }
  }, [dragging, onSwipe])

  // Programmatic swipe (from buttons)
  useEffect(() => {
    if (paper._forceSwipe) {
      setExiting(paper._forceSwipe === 'like' ? 'right' : 'left')
      setTimeout(() => {
        onSwipe(paper._forceSwipe)
      }, 300)
    }
  }, [paper._forceSwipe])

  const rotation = dragX * 0.08
  const opacity = exiting ? 0 : 1

  let transform = `translateX(${dragX}px) rotate(${rotation}deg)`
  if (exiting === 'right') transform = 'translateX(120%) rotate(20deg)'
  if (exiting === 'left') transform = 'translateX(-120%) rotate(-20deg)'

  // Single score: prefer recommendation_score (blended), fall back to raw LLM score
  const displayScore = paper.recommendation_score ?? paper.relevance_score
  const scoreColor = displayScore == null ? 'var(--text-muted)'
    : displayScore >= 0.7 ? 'var(--green)'
    : displayScore >= 0.4 ? 'var(--yellow)'
    : 'var(--red)'
  const scoreLabel = paper.recommendation_score != null ? '✨ match' : 'relevance'

  const showLike = dragX > 40
  const showPass = dragX < -40

  const favSet = new Set(favoriteAuthors.map(a => a.toLowerCase()))
  const hasFavoriteAuthor = (paper.authors || []).some(a => favSet.has(a.toLowerCase()))

  const pubDate = paper.published_date
    ? new Date(paper.published_date).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
    : null

  const source = paper.source || 'arxiv'
  const artifactLinks = paper.artifact_links || []

  return (
    <div
      ref={cardRef}
      className="swipe-card"
      style={{
        ...style,
        transform,
        opacity,
        transition: dragging ? 'none' : 'transform 0.3s ease, opacity 0.3s ease',
        zIndex: isTop ? 10 : 1,
      }}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
    >
      {showLike && <div className="swipe-overlay like">Read</div>}
      {showPass && <div className="swipe-overlay pass">Skip</div>}

      {/* Header row: categories + source + score badge (always visible at top) */}
      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
        {paper.categories?.split(',').slice(0, 3).map((cat) => (
          <span key={cat} className="card-category" style={{ margin: 0 }}>{cat.trim()}</span>
        ))}
        <span className={`source-badge ${source}`}>{source}</span>
        {hasFavoriteAuthor && (
          <span className="favorite-author-badge" title="Paper by a favourite author">⭐ Fav</span>
        )}
        {pubDate && <span className="paper-date">{pubDate}</span>}

        {/* Single score badge — pushed to the right */}
        {displayScore != null && (
          <span
            className="card-score-badge"
            style={{ background: scoreColor + '22', color: scoreColor }}
            title={paper.relevance_reason || ''}
          >
            {(displayScore * 100).toFixed(0)}% {scoreLabel}
          </span>
        )}
      </div>

      <div className="card-title">{paper.title}</div>

      <div className="card-authors">
        {(paper.authors || []).slice(0, 5).map((author, i) => (
          <span key={i}>
            {i > 0 && ', '}
            <span className={`author-name${favSet.has(author.toLowerCase()) ? ' is-favorite' : ''}`}>
              {author}
            </span>
          </span>
        ))}
        {(paper.authors?.length || 0) > 5 && ` +${paper.authors.length - 5} more`}
      </div>

      <div className="card-abstract">{paper.abstract}</div>

      {/* Artifact links */}
      {artifactLinks.length > 0 && (
        <div className="artifact-tags">
          {artifactLinks.slice(0, 3).map((url, i) => {
            const host = (() => { try { return new URL(url).hostname.replace('www.', '') } catch { return url } })()
            return (
              <a
                key={i}
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="artifact-tag"
                onPointerDown={e => e.stopPropagation()}
                title={url}
              >
                <Link size={9} /> {host}
              </a>
            )
          })}
        </div>
      )}

      {paper.relevance_reason && (
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8, fontStyle: 'italic' }}>
          {paper.relevance_reason}
        </div>
      )}
    </div>
  )
}

