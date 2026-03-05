const API_BASE = '/api';

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

export const api = {
  // Papers
  getFeed: (limit = 25, minScore = 0) =>
    request(`/papers/feed?limit=${limit}&min_score=${minScore}`),
  
  getStash: (page = 1, perPage = 25) =>
    request(`/papers/stash?page=${page}&per_page=${perPage}`),

  swipePaper: (id, action) =>
    request(`/papers/${id}/swipe?action=${action}`, { method: 'POST' }),
  
  getReadingList: (page = 1, perPage = 20) =>
    request(`/papers/reading-list?page=${page}&per_page=${perPage}`),
  
  unlikePaper: (id) =>
    request(`/papers/${id}/unlike`, { method: 'POST' }),
  
  getStats: () => request('/papers/stats'),

  shareToRaindrop: (id) =>
    request(`/papers/${id}/raindrop`, { method: 'POST' }),

  // Settings
  getSettings: () => request('/settings/'),
  updateSettings: (data) =>
    request('/settings/', { method: 'PUT', body: JSON.stringify(data) }),
  
  triggerScrape: () => request('/settings/scrape', { method: 'POST' }),
  triggerScore: () => request('/settings/score', { method: 'POST' }),
  triggerScrapeAndScore: () => request('/settings/scrape-and-score', { method: 'POST' }),
  healthCheck: () => request('/settings/health'),

  // Background task status
  getTaskStatus: () => request('/settings/task-status'),

  // Scholar
  triggerScholarScrape: () => request('/settings/scholar-scrape', { method: 'POST' }),

  // ACM
  triggerAcmScrape: () => request('/settings/acm-scrape', { method: 'POST' }),

  // Raindrop
  getRaindropCollections: () => request('/settings/raindrop/collections'),
  testRaindropToken: () => request('/settings/raindrop/test', { method: 'POST' }),
  
  ping: () => request('/ping'),

  // Favorite authors
  getFavoriteAuthors: () => request('/papers/favorite-authors'),
  addFavoriteAuthor: (name) =>
    request('/papers/favorite-authors', { method: 'POST', body: JSON.stringify({ name }) }),
  removeFavoriteAuthor: (name) =>
    request(`/papers/favorite-authors/${encodeURIComponent(name)}`, { method: 'DELETE' }),
};
