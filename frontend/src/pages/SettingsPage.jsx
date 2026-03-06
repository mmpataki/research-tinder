import { useState, useEffect, useCallback, useRef, useContext } from 'react'
import { RefreshCw, Zap, Download, CheckCircle, XCircle, Save, BookOpen, Cloud, Sun, Moon } from 'lucide-react'
import { api } from '../api'
import { AppContext, ACCENT_PRESETS } from '../App'

const TABS = [
  { id: 'feed',       label: 'Feed' },
  { id: 'ai',         label: 'AI' },
  { id: 'sources',    label: 'Sources' },
  { id: 'export',     label: 'Export' },
  { id: 'look',       label: 'Look' },
]

export default function SettingsPage() {
  const { theme, setTheme, font, setFont, accent, setAccent } = useContext(AppContext)
  const [activeTab, setActiveTab] = useState('feed')
  const [settings, setSettings] = useState({
    arxiv_categories: '',
    user_interests: '',
    ollama_model: '',
    ollama_base_url: '',
    scrape_cron_hour: 8,
    scrape_cron_minute: 0,
    llm_provider: 'ollama',
    openai_api_key: '',
    openai_model: 'gpt-4o-mini',
    gemini_api_key: '',
    gemini_model: 'gemini-2.0-flash',
    scholar_profile_urls: '',
    raindrop_token: '',
    raindrop_collection_id: -1,
    acm_sig_names: '',
  })
  const [stats, setStats] = useState(null)
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState(null)
  const [taskStatus, setTaskStatus] = useState(null)
  const pollRef = useRef(null)

  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      const [s, st, h, ts] = await Promise.all([
        api.getSettings(),
        api.getStats(),
        api.healthCheck().catch(() => ({ status: 'disconnected', provider: 'ollama' })),
        api.getTaskStatus().catch(() => ({ status: 'idle' })),
      ])
      setSettings(s)
      setStats(st)
      setHealth(h)
      setTaskStatus(ts)
      // If a task is still running, start polling
      if (ts.status === 'running') {
        startPolling()
      }
    } catch (err) {
      setToast(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadAll() }, [loadAll])

  // Poll task status when a background task is running
  const startPolling = useCallback(() => {
    if (pollRef.current) return
    pollRef.current = setInterval(async () => {
      try {
        const ts = await api.getTaskStatus()
        setTaskStatus(ts)
        if (ts.status !== 'running') {
          clearInterval(pollRef.current)
          pollRef.current = null
          setToast(ts.message)
          // refresh stats
          const st = await api.getStats()
          setStats(st)
        }
      } catch { /* ignore */ }
    }, 2000)
  }, [])

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(null), 4000)
      return () => clearTimeout(t)
    }
  }, [toast])

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.updateSettings(settings)
      setToast('Settings saved!')
      // Re-check health with new provider
      const h = await api.healthCheck().catch(() => ({ status: 'disconnected' }))
      setHealth(h)
    } catch (err) {
      setToast(err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleScrapeAndScore = async () => {
    try {
      const result = await api.triggerScrapeAndScore()
      setToast(result.message)
      setTaskStatus(result.task || null)
      startPolling()
    } catch (err) {
      setToast(err.message)
    }
  }

  const handleScoreOnly = async () => {
    try {
      const result = await api.triggerScore()
      setToast(result.message)
      if (result.task) { setTaskStatus(result.task); startPolling() }
    } catch (err) {
      setToast(err.message)
    }
  }

  const handleScholarScrape = async () => {
    try {
      const result = await api.triggerScholarScrape()
      setToast(result.message)
      if (result.task) { setTaskStatus(result.task); startPolling() }
    } catch (err) {
      setToast(err.message)
    }
  }

  const handleAcmScrape = async () => {
    try {
      const result = await api.triggerAcmScrape()
      setToast(result.message)
      if (result.task) { setTaskStatus(result.task); startPolling() }
    } catch (err) {
      setToast(err.message)
    }
  }

  const handleTestRaindrop = async () => {
    try {
      const result = await api.testRaindropToken()
      setToast(result.valid ? 'Raindrop token is valid!' : 'Raindrop token is invalid.')
    } catch (err) {
      setToast(err.message)
    }
  }

  const isTaskRunning = taskStatus?.status === 'running'

  if (loading) {
    return <div className="page"><div className="loading"><div className="spinner" /></div></div>
  }

  return (
    <div className="page settings-layout">
      <div className="header">
        <h1>Settings</h1>
      </div>

      {toast && <div className="toast">{toast}</div>}

      {/* Tab strip */}
      <div className="settings-tabs">
        {TABS.map(t => (
          <button
            key={t.id}
            className={`settings-tab ${activeTab === t.id ? 'active' : ''}`}
            onClick={() => setActiveTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="settings-page">
        {isTaskRunning && (
          <div className="task-banner">
            <RefreshCw size={16} className="spin" />
            <span>{taskStatus.message || 'Working...'}</span>
          </div>
        )}

        {/* ── Feed tab ───────────────────────────────────────────────────── */}
        {activeTab === 'feed' && <>
          {stats && (
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-value">{stats.total}</div>
                <div className="stat-label">Total</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.feed_ready ?? stats.pending}</div>
                <div className="stat-label">Feed</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.stashed ?? 0}</div>
                <div className="stat-label">Stashed</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.liked}</div>
                <div className="stat-label">Saved</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.unscored}</div>
                <div className="stat-label">Unscored</div>
              </div>
            </div>
          )}

          <div className="setting-group">
            <label>LLM Status</label>
            {health && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span className={`status-badge ${health.status === 'connected' ? 'ok' : 'error'}`}>
                  {health.status === 'connected'
                    ? <><CheckCircle size={14} /> Connected</>
                    : <><XCircle size={14} /> Disconnected</>
                  }
                </span>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  {health.provider} / {health.model}
                </span>
              </div>
            )}
          </div>

          <div className="setting-group">
            <label>Actions</label>
            <div className="btn-row">
              <button className="btn btn-primary" onClick={handleScrapeAndScore} disabled={isTaskRunning}>
                {isTaskRunning ? <><RefreshCw size={16} className="spin" /> Running...</> : <><Download size={16} /> Fetch &amp; Score</>}
              </button>
              <button className="btn btn-secondary" onClick={handleScoreOnly} disabled={isTaskRunning}>
                <Zap size={16} /> Score Only
              </button>
            </div>
            <div className="btn-row" style={{ marginTop: 8 }}>
              <button className="btn btn-secondary" onClick={handleScholarScrape} disabled={isTaskRunning || !settings.scholar_profile_urls}>
                <BookOpen size={16} /> Scholar
              </button>
              <button className="btn btn-secondary" onClick={handleAcmScrape} disabled={isTaskRunning || !settings.acm_sig_names}>
                <BookOpen size={16} /> ACM
              </button>
            </div>
          </div>
        </>}

        {/* ── AI tab ─────────────────────────────────────────────────────── */}
        {activeTab === 'ai' && <>
          <div className="setting-group">
            <label>LLM Provider</label>
            <select
              value={settings.llm_provider}
              onChange={e => setSettings(s => ({ ...s, llm_provider: e.target.value }))}
            >
              <option value="ollama">Ollama (local)</option>
              <option value="openai">OpenAI</option>
              <option value="gemini">Google Gemini</option>
            </select>
          </div>

          {settings.llm_provider === 'ollama' && <>
            <div className="setting-group">
              <label>Ollama Model</label>
              <input
                type="text"
                value={settings.ollama_model}
                onChange={e => setSettings(s => ({ ...s, ollama_model: e.target.value }))}
                placeholder="gemma3"
              />
            </div>
            <div className="setting-group">
              <label>Ollama URL</label>
              <input
                type="text"
                value={settings.ollama_base_url}
                onChange={e => setSettings(s => ({ ...s, ollama_base_url: e.target.value }))}
                placeholder="http://localhost:11434"
              />
            </div>
          </>}

          {settings.llm_provider === 'openai' && <>
            <div className="setting-group">
              <label>OpenAI API Key</label>
              <input
                type="password"
                value={settings.openai_api_key}
                onChange={e => setSettings(s => ({ ...s, openai_api_key: e.target.value }))}
                placeholder="sk-..."
              />
            </div>
            <div className="setting-group">
              <label>OpenAI Model</label>
              <input
                type="text"
                value={settings.openai_model}
                onChange={e => setSettings(s => ({ ...s, openai_model: e.target.value }))}
                placeholder="gpt-4o-mini"
              />
            </div>
          </>}

          {settings.llm_provider === 'gemini' && <>
            <div className="setting-group">
              <label>Gemini API Key</label>
              <input
                type="password"
                value={settings.gemini_api_key}
                onChange={e => setSettings(s => ({ ...s, gemini_api_key: e.target.value }))}
                placeholder="AI..."
              />
            </div>
            <div className="setting-group">
              <label>Gemini Model</label>
              <input
                type="text"
                value={settings.gemini_model}
                onChange={e => setSettings(s => ({ ...s, gemini_model: e.target.value }))}
                placeholder="gemini-2.0-flash"
              />
            </div>
          </>}
        </>}

        {/* ── Sources tab ────────────────────────────────────────────────── */}
        {activeTab === 'sources' && <>
          <div className="setting-group">
            <label>ArXiv Categories</label>
            <input
              type="text"
              value={settings.arxiv_categories}
              onChange={e => setSettings(s => ({ ...s, arxiv_categories: e.target.value }))}
              placeholder="cs.AI, cs.LG, cs.CL"
            />
            <div className="setting-hint">Comma-separated — e.g. cs.AI, cs.LG, cs.CL, cs.CV, stat.ML</div>
          </div>

          <div className="setting-group">
            <label>Your Research Interests</label>
            <textarea
              value={settings.user_interests}
              onChange={e => setSettings(s => ({ ...s, user_interests: e.target.value }))}
              placeholder="Describe your research interests..."
              rows={5}
            />
            <div className="setting-hint">Be specific — the LLM uses this to score each paper's relevance.</div>
          </div>

          <div className="setting-group">
            <label>Google Scholar Profile URLs</label>
            <textarea
              value={settings.scholar_profile_urls}
              onChange={e => setSettings(s => ({ ...s, scholar_profile_urls: e.target.value }))}
              placeholder={"https://scholar.google.com/citations?user=XXXXX\nhttps://scholar.google.com/citations?user=YYYYY"}
              rows={3}
            />
            <div className="setting-hint">One URL per line. Papers from these profiles will be added to your feed.</div>
          </div>

          <div className="setting-group">
            <label>ACM SIG Names</label>
            <textarea
              value={settings.acm_sig_names}
              onChange={e => setSettings(s => ({ ...s, acm_sig_names: e.target.value }))}
              placeholder={"CHI\nSIGKDD\nCSCW\nSIGMOD"}
              rows={3}
            />
            <div className="setting-hint">One per line. Fetches recent papers via Semantic Scholar.</div>
          </div>

          <div className="setting-group">
            <label>Daily Scrape Time</label>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <input
                type="number"
                min={0} max={23}
                value={settings.scrape_cron_hour}
                onChange={e => setSettings(s => ({ ...s, scrape_cron_hour: parseInt(e.target.value) || 0 }))}
                style={{ width: 70 }}
              />
              <span style={{ color: 'var(--text-muted)' }}>:</span>
              <input
                type="number"
                min={0} max={59}
                value={settings.scrape_cron_minute}
                onChange={e => setSettings(s => ({ ...s, scrape_cron_minute: parseInt(e.target.value) || 0 }))}
                style={{ width: 70 }}
              />
            </div>
          </div>
        </>}

        {/* ── Export tab ─────────────────────────────────────────────────── */}
        {activeTab === 'export' && <>
          <div className="setting-group">
            <label>Raindrop.io Token</label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                type="password"
                value={settings.raindrop_token}
                onChange={e => setSettings(s => ({ ...s, raindrop_token: e.target.value }))}
                placeholder="Test token from raindrop.io/settings/integrations"
                style={{ flex: 1 }}
              />
              <button className="btn btn-secondary" onClick={handleTestRaindrop} style={{ whiteSpace: 'nowrap' }}>
                <Cloud size={14} /> Test
              </button>
            </div>
          </div>

          <div className="setting-group">
            <label>Raindrop Collection ID</label>
            <input
              type="number"
              value={settings.raindrop_collection_id}
              onChange={e => setSettings(s => ({ ...s, raindrop_collection_id: parseInt(e.target.value) || -1 }))}
            />
            <div className="setting-hint">-1 = Unsorted. Find IDs via the Raindrop Collections button after saving your token.</div>
          </div>
        </>}

        {/* ── Look tab ───────────────────────────────────────────────────── */}
        {activeTab === 'look' && <>
          <div className="setting-group">
            <label>Theme</label>
            <div className="appearance-row">
              <select value={theme} onChange={e => setTheme(e.target.value)}>
                <option value="dark">Dark</option>
                <option value="light">Catppuccin Latte (Light)</option>
              </select>
              {theme === 'dark'
                ? <Moon size={18} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                : <Sun size={18} style={{ color: 'var(--yellow)', flexShrink: 0 }} />
              }
            </div>
          </div>

          <div className="setting-group">
            <label>Font</label>
            <div className="appearance-row">
              <select value={font} onChange={e => setFont(e.target.value)}>
                <option value="system">System Default</option>
                <option value="inter">Inter</option>
                <option value="jetbrains">JetBrains Mono</option>
                <option value="fira-code">Fira Code</option>
                <option value="georgia">Georgia (Serif)</option>
                <option value="ibm-plex">IBM Plex Sans</option>
              </select>
            </div>
          </div>

          <div className="setting-group">
            <label>Accent Color</label>
            <div className="accent-swatches">
              {ACCENT_PRESETS.map(p => (
                <button
                  key={p.value}
                  className={`accent-swatch ${accent === p.value ? 'active' : ''}`}
                  style={{ background: p.value }}
                  title={p.label}
                  onClick={() => setAccent(p.value)}
                />
              ))}
              <input
                type="color"
                className="accent-custom-input"
                value={accent}
                onChange={e => setAccent(e.target.value)}
                title="Custom color"
              />
            </div>
          </div>
        </>}

        {/* Save — always visible */}
        <button
          className="btn btn-primary"
          onClick={handleSave}
          disabled={saving}
          style={{ width: '100%', justifyContent: 'center', marginTop: 8 }}
        >
          {saving ? 'Saving...' : <><Save size={16} /> Save Settings</>}
        </button>
      </div>
    </div>
  )
}

        {/* Stats */}
        {stats && (
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-value">{stats.total}</div>
              <div className="stat-label">Total Papers</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats.feed_ready ?? stats.pending}</div>
              <div className="stat-label">Feed (Top 25)</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats.stashed ?? 0}</div>
              <div className="stat-label">Stashed</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats.liked}</div>
              <div className="stat-label">Saved</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats.unscored}</div>
              <div className="stat-label">Unscored</div>
            </div>
          </div>
        )}

        {/* LLM Provider Health */}
        <div className="setting-group">
          <label>LLM Status</label>
          {health && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span className={`status-badge ${health.status === 'connected' ? 'ok' : 'error'}`}>
                {health.status === 'connected'
                  ? <><CheckCircle size={14} /> Connected</>
                  : <><XCircle size={14} /> Disconnected</>
                }
              </span>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                {health.provider} / {health.model}
              </span>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="setting-group">
          <label>Actions</label>
          <div className="btn-row">
            <button
              className="btn btn-primary"
              onClick={handleScrapeAndScore}
              disabled={isTaskRunning}
            >
              {isTaskRunning ? <><RefreshCw size={16} className="spin" /> Running...</> : <><Download size={16} /> Fetch &amp; Score</>}
            </button>
            <button
              className="btn btn-secondary"
              onClick={handleScoreOnly}
              disabled={isTaskRunning}
            >
              <Zap size={16} /> Score Only
            </button>
          </div>
          <div className="btn-row" style={{ marginTop: 8 }}>
            <button
              className="btn btn-secondary"
              onClick={handleScholarScrape}
              disabled={isTaskRunning || !settings.scholar_profile_urls}
            >
              <BookOpen size={16} /> Scholar Scrape
            </button>
            <button
              className="btn btn-secondary"
              onClick={handleAcmScrape}
              disabled={isTaskRunning || !settings.acm_sig_names}
            >
              <BookOpen size={16} /> ACM Scrape
            </button>
          </div>
        </div>

        {/* LLM Provider */}
        <div className="setting-group">
          <label>LLM Provider</label>
          <select
            value={settings.llm_provider}
            onChange={e => setSettings(s => ({ ...s, llm_provider: e.target.value }))}
          >
            <option value="ollama">Ollama (local)</option>
            <option value="openai">OpenAI</option>
            <option value="gemini">Google Gemini</option>
          </select>
        </div>

        {/* Ollama config */}
        {settings.llm_provider === 'ollama' && (
          <>
            <div className="setting-group">
              <label>Ollama Model</label>
              <input
                type="text"
                value={settings.ollama_model}
                onChange={e => setSettings(s => ({ ...s, ollama_model: e.target.value }))}
                placeholder="gemma3"
              />
            </div>
            <div className="setting-group">
              <label>Ollama URL</label>
              <input
                type="text"
                value={settings.ollama_base_url}
                onChange={e => setSettings(s => ({ ...s, ollama_base_url: e.target.value }))}
                placeholder="http://localhost:11434"
              />
            </div>
          </>
        )}

        {/* OpenAI config */}
        {settings.llm_provider === 'openai' && (
          <>
            <div className="setting-group">
              <label>OpenAI API Key</label>
              <input
                type="password"
                value={settings.openai_api_key}
                onChange={e => setSettings(s => ({ ...s, openai_api_key: e.target.value }))}
                placeholder="sk-..."
              />
            </div>
            <div className="setting-group">
              <label>OpenAI Model</label>
              <input
                type="text"
                value={settings.openai_model}
                onChange={e => setSettings(s => ({ ...s, openai_model: e.target.value }))}
                placeholder="gpt-4o-mini"
              />
            </div>
          </>
        )}

        {/* Gemini config */}
        {settings.llm_provider === 'gemini' && (
          <>
            <div className="setting-group">
              <label>Gemini API Key</label>
              <input
                type="password"
                value={settings.gemini_api_key}
                onChange={e => setSettings(s => ({ ...s, gemini_api_key: e.target.value }))}
                placeholder="AI..."
              />
            </div>
            <div className="setting-group">
              <label>Gemini Model</label>
              <input
                type="text"
                value={settings.gemini_model}
                onChange={e => setSettings(s => ({ ...s, gemini_model: e.target.value }))}
                placeholder="gemini-2.0-flash"
              />
            </div>
          </>
        )}

        {/* ArXiv Categories */}
        <div className="setting-group">
          <label>ArXiv Categories (comma-separated)</label>
          <input
            type="text"
            value={settings.arxiv_categories}
            onChange={e => setSettings(s => ({ ...s, arxiv_categories: e.target.value }))}
            placeholder="cs.AI, cs.LG, cs.CL"
          />
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
            Examples: cs.AI, cs.LG, cs.CL, cs.CV, stat.ML, cs.PL, cs.SE
          </div>
        </div>

        {/* User Interests */}
        <div className="setting-group">
          <label>Your Research Interests</label>
          <textarea
            value={settings.user_interests}
            onChange={e => setSettings(s => ({ ...s, user_interests: e.target.value }))}
            placeholder="Describe your research interests..."
            rows={4}
          />
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
            Be specific! The LLM uses this to score each paper's relevance to you.
          </div>
        </div>

        {/* Google Scholar */}
        <div className="setting-group">
          <label>Google Scholar Profile URLs (one per line)</label>
          <textarea
            value={settings.scholar_profile_urls}
            onChange={e => setSettings(s => ({ ...s, scholar_profile_urls: e.target.value }))}
            placeholder={"https://scholar.google.com/citations?user=XXXXX\nhttps://scholar.google.com/citations?user=YYYYY"}
            rows={3}
          />
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
            Papers from these profiles will be added to your feed.
          </div>
        </div>

        {/* ACM SIGs */}
        <div className="setting-group">
          <label>ACM SIG Names (one per line)</label>
          <textarea
            value={settings.acm_sig_names}
            onChange={e => setSettings(s => ({ ...s, acm_sig_names: e.target.value }))}
            placeholder={"CHI\nSIGKDD\nCSCW\nSIGMOD\nSIGCOMM"}
            rows={3}
          />
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
            Fetches recent papers from these ACM SIG venues via Semantic Scholar.
          </div>
        </div>

        {/* Raindrop.io */}
        <div className="setting-group">
          <label>Raindrop.io Token</label>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              type="password"
              value={settings.raindrop_token}
              onChange={e => setSettings(s => ({ ...s, raindrop_token: e.target.value }))}
              placeholder="Test token from raindrop.io/settings/integrations"
              style={{ flex: 1 }}
            />
            <button className="btn btn-secondary" onClick={handleTestRaindrop} style={{ whiteSpace: 'nowrap' }}>
              <Cloud size={14} /> Test
            </button>
          </div>
        </div>

        <div className="setting-group">
          <label>Raindrop Collection ID</label>
          <input
            type="number"
            value={settings.raindrop_collection_id}
            onChange={e => setSettings(s => ({ ...s, raindrop_collection_id: parseInt(e.target.value) || -1 }))}
          />
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
            -1 = Unsorted. Find IDs via the Raindrop Collections button after saving your token.
          </div>
        </div>

        {/* Schedule */}
        <div className="setting-group">
          <label>Daily Scrape Time</label>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <input
              type="number"
              min={0}
              max={23}
              value={settings.scrape_cron_hour}
              onChange={e => setSettings(s => ({ ...s, scrape_cron_hour: parseInt(e.target.value) || 0 }))}
              style={{ width: 70 }}
            />
            <span style={{ color: 'var(--text-muted)' }}>:</span>
            <input
              type="number"
              min={0}
              max={59}
              value={settings.scrape_cron_minute}
              onChange={e => setSettings(s => ({ ...s, scrape_cron_minute: parseInt(e.target.value) || 0 }))}
              style={{ width: 70 }}
            />
          </div>
        </div>

        {/* Appearance */}
        <div className="setting-group">
          <label>Theme</label>
          <div className="appearance-row">
            <select value={theme} onChange={e => setTheme(e.target.value)}>
              <option value="dark">Dark</option>
              <option value="light">Catppuccin Latte (Light)</option>
            </select>
            {theme === 'dark'
              ? <Moon size={18} style={{ color: 'var(--accent)', flexShrink: 0 }} />
              : <Sun size={18} style={{ color: 'var(--yellow)', flexShrink: 0 }} />
            }
          </div>
        </div>

        <div className="setting-group">
          <label>Font</label>
          <div className="appearance-row">
            <select value={font} onChange={e => setFont(e.target.value)}>
              <option value="system">System Default</option>
              <option value="inter">Inter</option>
              <option value="jetbrains">JetBrains Mono</option>
              <option value="fira-code">Fira Code</option>
              <option value="georgia">Georgia (Serif)</option>
              <option value="ibm-plex">IBM Plex Sans</option>
            </select>
          </div>
        </div>

        {/* Accent Color */}
        <div className="setting-group">
          <label>Accent Color</label>
          <div className="accent-swatches">
            {ACCENT_PRESETS.map(p => (
              <button
                key={p.value}
                className={`accent-swatch ${accent === p.value ? 'active' : ''}`}
                style={{ background: p.value }}
                title={p.label}
                onClick={() => setAccent(p.value)}
              />
            ))}
            <input
              type="color"
              className="accent-custom-input"
              value={accent}
              onChange={e => setAccent(e.target.value)}
              title="Custom color"
            />
          </div>
        </div>

        {/* Save */}
        <button
          className="btn btn-primary"
          onClick={handleSave}
          disabled={saving}
          style={{ width: '100%', justifyContent: 'center' }}
        >
          {saving ? 'Saving...' : <><Save size={16} /> Save Settings</>}
        </button>
      </div>
    </div>
  )
}
