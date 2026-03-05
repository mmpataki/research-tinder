import { useState, useEffect, useCallback } from 'react'
import { ExternalLink, FileText, Trash2, CloudUpload, Copy, Check, ChevronDown, ChevronUp, Link } from 'lucide-react'
import { api } from '../api'

function formatDate(iso) {
  if (!iso) return null
  return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

function buildCitation(paper) {
  const authors = (paper.authors || []).slice(0, 6).join(', ')
  const date = paper.published_date ? new Date(paper.published_date).getFullYear() : ''
  const source = paper.source === 'acm' ? 'ACM DL' : paper.source === 'scholar' ? 'Google Scholar' : 'arXiv'
  return `${authors} (${date}). "${paper.title}." ${source}. ${paper.arxiv_url || paper.pdf_url}`
}

export default function ReadingListPage() {
  const [papers, setPapers] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState(null)
  const [sharing, setSharing] = useState(null)
  const [expanded, setExpanded] = useState(new Set())
  const [copiedId, setCopiedId] = useState(null)
  const [favoriteAuthors, setFavoriteAuthors] = useState([])

  const loadPapers = useCallback(async () => {
    setLoading(true)
    try {
      const [listData, favData] = await Promise.all([
        api.getReadingList(page),
        api.getFavoriteAuthors().catch(() => ({ authors: [] })),
      ])
      setPapers(listData.papers)
      setTotal(listData.total)
      setFavoriteAuthors(favData.authors || [])
    } catch (err) {
      setToast(err.message)
    } finally {
      setLoading(false)
    }
  }, [page])

  useEffect(() => { loadPapers() }, [loadPapers])

  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(null), 3000)
      return () => clearTimeout(t)
    }
  }, [toast])

  const handleRemove = async (id) => {
    try {
      await api.unlikePaper(id)
      setPapers(prev => prev.filter(p => p.id !== id))
      setTotal(prev => prev - 1)
    } catch (err) {
      setToast(err.message)
    }
  }

  const handleShareRaindrop = async (id) => {
    setSharing(id)
    try {
      const result = await api.shareToRaindrop(id)
      setToast(result.message || 'Saved to Raindrop!')
    } catch (err) {
      setToast(err.message)
    } finally {
      setSharing(null)
    }
  }

  const handleCopy = async (paper) => {
    const text = buildCitation(paper)
    try {
      await navigator.clipboard.writeText(text)
      setCopiedId(paper.id)
      setTimeout(() => setCopiedId(null), 1800)
    } catch {
      setToast('Copy failed')
    }
  }

  const toggleExpand = (id) => {
    setExpanded(prev => {
      const s = new Set(prev)
      s.has(id) ? s.delete(id) : s.add(id)
      return s
    })
  }

  const toggleFavoriteAuthor = async (name) => {
    const favSet = new Set(favoriteAuthors)
    try {
      if (favSet.has(name)) {
        await api.removeFavoriteAuthor(name)
        setFavoriteAuthors(prev => prev.filter(a => a !== name))
        setToast(`Removed ${name} from favorites`)
      } else {
        await api.addFavoriteAuthor(name)
        setFavoriteAuthors(prev => [...prev, name])
        setToast(`Added ${name} to favorites`)
      }
    } catch (err) {
      setToast(err.message)
    }
  }

  const totalPages = Math.ceil(total / 20)
  const favSet = new Set(favoriteAuthors.map(a => a.toLowerCase()))

  return (
    <div className="page">
      <div className="header">
        <h1>Reading List</h1>
        <div className="subtitle">{total} paper{total !== 1 ? 's' : ''} saved</div>
      </div>

      {toast && <div className="toast">{toast}</div>}

      {loading ? (
        <div className="loading"><div className="spinner" /></div>
      ) : papers.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📚</div>
          <h3>No saved papers yet</h3>
          <p>Right-swipe papers you want to read and they'll appear here.</p>
        </div>
      ) : (
        <div className="reading-list">
          {papers.map(paper => {
            const isExpanded = expanded.has(paper.id)
            const isCopied = copiedId === paper.id
            const source = paper.source || 'arxiv'
            const pubDate = formatDate(paper.published_date)
            const hasFavAuthor = (paper.authors || []).some(a => favSet.has(a.toLowerCase()))
            const artifactLinks = paper.artifact_links || []

            return (
              <div key={paper.id} className="paper-item">
                {/* Title row */}
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                  <div className="paper-title" style={{ flex: 1 }}>{paper.title}</div>
                  <button
                    onClick={() => toggleExpand(paper.id)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '2px 0', flexShrink: 0 }}
                    title={isExpanded ? 'Collapse' : 'Expand'}
                  >
                    {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </button>
                </div>

                {/* Meta row */}
                <div className="paper-meta" style={{ flexWrap: 'wrap' }}>
                  <span className={`source-badge ${source}`}>{source}</span>
                  {pubDate && <span className="paper-date">{pubDate}</span>}
                  <span>·</span>
                  <span>{paper.categories?.split(',')[0]}</span>
                  {paper.relevance_score != null && (
                    <>
                      <span>·</span>
                      <span style={{
                        color: paper.relevance_score >= 0.7 ? 'var(--green)' : paper.relevance_score >= 0.4 ? 'var(--yellow)' : 'var(--red)',
                        fontWeight: 600,
                      }}>
                        {(paper.relevance_score * 100).toFixed(0)}%
                      </span>
                    </>
                  )}
                  {hasFavAuthor && <span className="favorite-author-badge">⭐ Fav</span>}
                </div>

                {/* Authors with favorite toggle */}
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4, lineHeight: 1.5 }}>
                  {(paper.authors || []).slice(0, 6).map((author, i) => {
                    const isFav = favSet.has(author.toLowerCase())
                    return (
                      <span key={i} style={{ marginRight: 4 }}>
                        {i > 0 && ''}
                        <button
                          onClick={() => toggleFavoriteAuthor(author)}
                          title={isFav ? `Remove ${author} from favorites` : `Add ${author} to favorites`}
                          style={{
                            background: 'none',
                            border: 'none',
                            cursor: 'pointer',
                            padding: 0,
                            fontSize: 12,
                            color: isFav ? 'var(--yellow)' : 'var(--text-muted)',
                            fontWeight: isFav ? 600 : 400,
                          }}
                        >
                          {isFav ? '⭐' : '☆'} {author}
                          {i < Math.min((paper.authors?.length || 0) - 1, 5) ? ',' : ''}
                        </button>
                      </span>
                    )
                  })}
                  {(paper.authors?.length || 0) > 6 && ` +${paper.authors.length - 6} more`}
                </div>

                {/* Artifact links */}
                {artifactLinks.length > 0 && (
                  <div className="artifact-tags">
                    {artifactLinks.slice(0, 3).map((url, i) => {
                      const host = (() => { try { return new URL(url).hostname.replace('www.', '') } catch { return url } })()
                      return (
                        <a key={i} href={url} target="_blank" rel="noopener noreferrer" className="artifact-tag" title={url}>
                          <Link size={9} /> {host}
                        </a>
                      )
                    })}
                  </div>
                )}

                {/* Expanded detail */}
                {isExpanded && (
                  <div className="paper-detail">
                    <div className="paper-abstract">{paper.abstract}</div>
                    {paper.relevance_reason && (
                      <div className="paper-reason">💡 {paper.relevance_reason}</div>
                    )}
                  </div>
                )}

                {/* Action buttons */}
                <div className="paper-actions">
                  <a href={paper.arxiv_url} target="_blank" rel="noopener noreferrer">
                    <FileText size={12} style={{ marginRight: 3, verticalAlign: -1 }} />
                    {source === 'acm' ? 'ACM DL' : source === 'scholar' ? 'Scholar' : 'arXiv'}
                  </a>
                  <a href={paper.pdf_url} target="_blank" rel="noopener noreferrer">
                    <ExternalLink size={12} style={{ marginRight: 3, verticalAlign: -1 }} />
                    PDF
                  </a>
                  <button
                    onClick={() => handleCopy(paper)}
                    className={isCopied ? 'copy-success' : ''}
                    title="Copy citation"
                  >
                    {isCopied
                      ? <><Check size={12} style={{ marginRight: 3, verticalAlign: -1 }} /> Copied</>
                      : <><Copy size={12} style={{ marginRight: 3, verticalAlign: -1 }} /> Cite</>
                    }
                  </button>
                  <button
                    className="raindrop-btn"
                    onClick={() => handleShareRaindrop(paper.id)}
                    disabled={sharing === paper.id}
                    title="Save to Raindrop.io"
                  >
                    <CloudUpload size={12} style={{ marginRight: 3, verticalAlign: -1 }} />
                    {sharing === paper.id ? '...' : 'Raindrop'}
                  </button>
                  <button className="remove-btn" onClick={() => handleRemove(paper.id)}>
                    <Trash2 size={12} style={{ marginRight: 3, verticalAlign: -1 }} />
                    Remove
                  </button>
                </div>
              </div>
            )
          })}

          {totalPages > 1 && (
            <div style={{ display: 'flex', justifyContent: 'center', gap: 10, marginTop: 16 }}>
              <button className="btn btn-secondary" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Prev</button>
              <span style={{ padding: '10px 0', fontSize: 13, color: 'var(--text-muted)' }}>{page} / {totalPages}</span>
              <button className="btn btn-secondary" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next</button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}