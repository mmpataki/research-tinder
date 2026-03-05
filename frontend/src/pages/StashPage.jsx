import { useState, useEffect, useCallback } from 'react'
import { ExternalLink, FileText, Heart, RefreshCw } from 'lucide-react'
import { api } from '../api'

export default function StashPage() {
  const [papers, setPapers] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState(null)

  const loadPapers = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getStash(page)
      setPapers(data.papers)
      setTotal(data.total)
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

  const handleLike = async (id) => {
    try {
      await api.swipePaper(id, 'like')
      setPapers(prev => prev.filter(p => p.id !== id))
      setTotal(prev => prev - 1)
      setToast('Added to reading list!')
    } catch (err) {
      setToast(err.message)
    }
  }

  const handlePass = async (id) => {
    try {
      await api.swipePaper(id, 'pass')
      setPapers(prev => prev.filter(p => p.id !== id))
      setTotal(prev => prev - 1)
    } catch (err) {
      setToast(err.message)
    }
  }

  const totalPages = Math.ceil(total / 25)

  return (
    <div className="page">
      <div className="header">
        <h1>Stash</h1>
        <div className="subtitle">
          {total} lower-ranked paper{total !== 1 ? 's' : ''} beyond your daily top 25
        </div>
      </div>

      {toast && <div className="toast">{toast}</div>}

      {loading ? (
        <div className="loading"><div className="spinner" /></div>
      ) : papers.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📦</div>
          <h3>Stash is empty</h3>
          <p>When you have more than 25 scored papers, lower-ranked ones appear here.</p>
        </div>
      ) : (
        <div className="reading-list">
          {papers.map(paper => (
            <div key={paper.id} className="paper-item">
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <div className="paper-title" style={{ flex: 1 }}>{paper.title}</div>
                {paper.recommendation_score != null && (
                  <span className="rec-score">
                    {(paper.recommendation_score * 100).toFixed(0)}%
                  </span>
                )}
              </div>
              <div className="paper-meta">
                <span>{paper.authors?.slice(0, 3).join(', ')}{paper.authors?.length > 3 ? ' et al.' : ''}</span>
                <span>·</span>
                <span>{paper.categories?.split(',')[0]}</span>
                {paper.relevance_score != null && (
                  <>
                    <span>·</span>
                    <span style={{
                      color: paper.relevance_score >= 0.7 ? 'var(--green)' : paper.relevance_score >= 0.4 ? 'var(--yellow)' : 'var(--red)',
                      fontWeight: 600,
                      fontSize: 11,
                    }}>
                      LLM: {(paper.relevance_score * 100).toFixed(0)}%
                    </span>
                  </>
                )}
              </div>
              <div className="paper-actions">
                <a href={paper.arxiv_url} target="_blank" rel="noopener noreferrer">
                  <FileText size={12} style={{ marginRight: 3, verticalAlign: -1 }} />
                  arXiv
                </a>
                <a href={paper.pdf_url} target="_blank" rel="noopener noreferrer">
                  <ExternalLink size={12} style={{ marginRight: 3, verticalAlign: -1 }} />
                  PDF
                </a>
                <button onClick={() => handleLike(paper.id)} style={{ color: 'var(--green)', background: 'var(--green-dim)' }}>
                  <Heart size={12} style={{ marginRight: 3, verticalAlign: -1 }} />
                  Save
                </button>
                <button className="remove-btn" onClick={() => handlePass(paper.id)}>
                  Pass
                </button>
              </div>
            </div>
          ))}

          {totalPages > 1 && (
            <div style={{ display: 'flex', justifyContent: 'center', gap: 10, marginTop: 16 }}>
              <button
                className="btn btn-secondary"
                disabled={page <= 1}
                onClick={() => setPage(p => p - 1)}
              >
                Prev
              </button>
              <span style={{ padding: '10px 0', fontSize: 13, color: 'var(--text-muted)' }}>
                {page} / {totalPages}
              </span>
              <button
                className="btn btn-secondary"
                disabled={page >= totalPages}
                onClick={() => setPage(p => p + 1)}
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
