# Research Tinder 🔬❤️

Swipe through arXiv papers matched to your research interests by a local LLM. Like Tinder, but for academic papers.

## How it works

1. **Scrape** — Fetches new papers from your configured arXiv categories (e.g. `cs.AI`, `cs.LG`)
2. **Score** — Sends each paper's abstract to a local Ollama LLM which scores relevance (0–100%) based on your described interests
3. **Swipe** — Papers appear as cards sorted by relevance. Swipe right to save, left to skip
4. **Read** — Your saved papers live in the Reading List with direct arXiv/PDF links

## Architecture

```
backend/          Python FastAPI
  app/
    models/       SQLAlchemy models (Paper, UserPreference)
    routes/       REST API (papers feed/swipe, settings, scrape triggers)
    services/     ArXiv scraper, Ollama LLM scorer, APScheduler
    
frontend/         React + Vite PWA
  src/
    pages/        SwipePage, ReadingListPage, SettingsPage
    components/   SwipeCard (drag gesture)
```

## Prerequisites

- **Python 3.8+**
- **Node.js 18+**
- **Ollama** running locally with a model pulled (e.g. `ollama pull llama3`)

## Quick Start

### 1. Install dependencies

```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### 2. Configure

Edit `backend/.env`:

```env
ARXIV_CATEGORIES=cs.AI,cs.LG        # arXiv categories to follow
OLLAMA_MODEL=llama3                   # your Ollama model
USER_INTERESTS=I am interested in...  # describe your research interests
```

### 3. Run (development)

Two terminals:

```bash
# Terminal 1 — Backend
./start-backend.sh
# → http://localhost:8000

# Terminal 2 — Frontend
./start-frontend.sh
# → http://localhost:5173
```

### 4. Run (production — single server)

```bash
./start-prod.sh
# → http://localhost:8000 (serves both API and frontend)
```

### 5. First use

1. Open the app → go to **Settings**
2. Set your arXiv categories and research interests
3. Click **Fetch & Score** to pull today's papers
4. Go to **Swipe** and start swiping!

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/papers/feed` | Get papers to swipe on |
| POST | `/api/papers/{id}/swipe?action=like\|pass` | Swipe on a paper |
| GET | `/api/papers/reading-list` | Get saved papers |
| POST | `/api/papers/{id}/unlike` | Remove from reading list |
| GET | `/api/papers/stats` | Paper counts by status |
| GET | `/api/settings/` | Get app settings |
| PUT | `/api/settings/` | Update settings |
| POST | `/api/settings/scrape` | Trigger arXiv scrape |
| POST | `/api/settings/score` | Trigger LLM scoring |
| POST | `/api/settings/scrape-and-score` | Scrape + score in one call |
| GET | `/api/settings/health` | Check Ollama connectivity |

## Mobile Use

The frontend is a **PWA** (Progressive Web App). On your phone:
1. Open `http://<your-laptop-ip>:8000` in Chrome/Safari
2. Tap "Add to Home Screen"
3. It works like a native app with offline support

## Daily Auto-Scrape

By default, the backend runs a cron job at **8:00 AM** daily to fetch and score new papers. Configure this in Settings.
