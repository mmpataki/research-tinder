import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'icon-192.png', 'icon-512.png'],
      manifest: {
        name: 'Research Tinder',
        short_name: 'ResTinder',
        description: 'Swipe through arXiv papers matched to your interests',
        theme_color: '#6366f1',
        background_color: '#0f172a',
        display: 'standalone',
        orientation: 'portrait',
        start_url: '/',
        scope: '/',
        icons: [
          {
            src: '/favicon.svg',
            sizes: 'any',
            type: 'image/svg+xml',
            purpose: 'any',
          },
          {
            src: '/icon-192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: '/icon-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any maskable',
          },
        ],
      },
      // Enable service worker in dev mode for testing
      devOptions: {
        enabled: true,
        type: 'module',
      },
      workbox: {
        // Cache page navigations (SPA)
        navigateFallback: '/index.html',
        navigateFallbackAllowlist: [/^\/(?!api\/).*/],
        // Runtime caching for API calls
        // NOTE: urlPattern regexes are tested against the FULL URL (including origin),
        // so do NOT anchor with ^ at the start.
        runtimeCaching: [
          {
            urlPattern: /\/api\/papers\/feed/,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-feed',
              expiration: { maxEntries: 5, maxAgeSeconds: 86400 },
              networkTimeoutSeconds: 5,
            },
          },
          {
            urlPattern: /\/api\/papers\/reading-list/,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-reading-list',
              expiration: { maxEntries: 5, maxAgeSeconds: 86400 },
              networkTimeoutSeconds: 5,
            },
          },
          {
            urlPattern: /\/api\/papers\/stash/,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-stash',
              expiration: { maxEntries: 5, maxAgeSeconds: 86400 },
              networkTimeoutSeconds: 5,
            },
          },
          {
            urlPattern: /\/api\//,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-general',
              expiration: { maxEntries: 20, maxAgeSeconds: 86400 },
              networkTimeoutSeconds: 5,
            },
          },
        ],
      },
    }),
  ],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
