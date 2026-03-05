/**
 * Offline-first localStorage cache.
 *
 * Stores:
 *   rt:feed         — array of Paper objects fetched from the server
 *   rt:favs         — array of favourite author name strings
 *   rt:swipe_queue  — array of { id, action, ts } pending swipes
 *
 * Swipes committed while offline are held in the queue and flushed
 * automatically once the network comes back (via the 'online' event
 * in SwipePage).
 */

const KEYS = {
  feed: 'rt:feed',
  favs: 'rt:favs',
  queue: 'rt:swipe_queue',
}

// ─── helpers ────────────────────────────────────────────────────────────────

function set(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)) } catch {}
}
function get(key) {
  try { const r = localStorage.getItem(key); return r ? JSON.parse(r) : null }
  catch { return null }
}

// ─── feed ────────────────────────────────────────────────────────────────────

/** Persist a fresh feed to localStorage. */
export function cacheFeed(papers) {
  set(KEYS.feed, { papers, ts: Date.now() })
}

/**
 * Return cached feed papers, or null if nothing is cached yet.
 * Intentionally ignores TTL so the cache is available even after 24h offline.
 */
export function getCachedFeed() {
  const stored = get(KEYS.feed)
  return stored ? stored.papers : null
}

/** Remove papers that the user already swiped (keep cache tidy). */
export function removePaperFromCache(id) {
  const stored = get(KEYS.feed)
  if (!stored) return
  stored.papers = stored.papers.filter(p => p.id !== id)
  set(KEYS.feed, stored)
}

// ─── favourites ──────────────────────────────────────────────────────────────

export function cacheFavs(authors) {
  set(KEYS.favs, { authors, ts: Date.now() })
}

export function getCachedFavs() {
  const stored = get(KEYS.favs)
  return stored ? (stored.authors ?? []) : []
}

// ─── swipe queue (offline pending commits) ───────────────────────────────────

/**
 * Add a swipe action to the local queue so it can be replayed when the
 * network returns.  If the same paper is already queued, overwrite it.
 */
export function enqueueSwipe(id, action) {
  const queue = get(KEYS.queue) || []
  const filtered = queue.filter(item => item.id !== id)
  filtered.push({ id, action, ts: Date.now() })
  set(KEYS.queue, filtered)
}

export function getSwipeQueue() {
  return get(KEYS.queue) || []
}

export function removeFromQueue(id) {
  const queue = get(KEYS.queue) || []
  set(KEYS.queue, queue.filter(item => item.id !== id))
}

export function clearSwipeQueue() {
  set(KEYS.queue, [])
}

// ─── network status ──────────────────────────────────────────────────────────

export function isOnline() {
  return typeof navigator !== 'undefined' ? navigator.onLine : true
}
