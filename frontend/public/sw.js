// Service Worker pour Foot Predict PWA
// Gère le cache des ressources statiques et la mise en cache des requêtes API

const CACHE_NAME = 'foot-predict-v1';
const STATIC_ASSETS = [
  '/',
  '/manifest.json',
  '/icons/icon-192x192.png',
  '/icons/icon-512x512.png'
];

// Installer le service worker et mettre en cache les ressources statiques
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// Activer le service worker et nettoyer les anciens caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames.filter((cacheName) => cacheName !== CACHE_NAME)
            .map((cacheName) => caches.delete(cacheName))
        );
      })
      .then(() => self.clients.claim())
  );
});

// Intercepter les requêtes réseau
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Pour les requêtes API, essayer le réseau d'abord, puis le cache
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          // Cloner la réponse pour la mettre en cache
          const responseClone = response.clone();
          caches.open(CACHE_NAME)
            .then((cache) => cache.put(event.request, responseClone));
          return response;
        })
        .catch(() => {
          // En cas d'échec réseau, essayer le cache
          return caches.match(event.request);
        })
    );
    return;
  }

  // Pour les ressources statiques, utiliser le cache d'abord
  event.respondWith(
    caches.match(event.request)
      .then((cachedResponse) => {
        if (cachedResponse) {
          return cachedResponse;
        }
        return fetch(event.request);
      })
  );
});

// Écouter les messages du client (par exemple pour sauter la file d'attente)
self.addEventListener('message', (event) => {
  if (event.data === 'skipWaiting') {
    self.skipWaiting();
  }
});
