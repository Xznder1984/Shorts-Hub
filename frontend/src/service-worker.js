const CACHE = 'shorts-hub-v1';
const CORE_ASSETS = [
	'/',
	'/manifest.webmanifest',
	'/offline.html'
];

self.addEventListener('install', (event) => {
	event.waitUntil(
		caches.open(CACHE).then((cache) => cache.addAll(CORE_ASSETS)).then(() => self.skipWaiting())
	);
});

self.addEventListener('activate', (event) => {
	event.waitUntil(
		caches.keys()
			.then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
			.then(() => self.clients.claim())
	);
});

self.addEventListener('fetch', (event) => {
	const url = new URL(event.request.url);

	// Pure network-for-navigation with offline fallback
	if (event.request.mode === 'navigate') {
		event.respondWith(
			fetch(event.request).catch(() => caches.match(event.request).then((r) => r || caches.match('/')))
		);
		return;
	}

	// NEVER cache or intercept API calls — search results must be live.
	if (url.pathname.startsWith('/api/')) {
		return; // default network behavior
	}

	// Cache-first for same-origin static assets
	if (url.origin === self.location.origin && event.request.method === 'GET') {
		event.respondWith(
			caches.match(event.request).then(
				(cached) =>
					cached ||
					fetch(event.request).then((resp) => {
						if (resp.ok) {
							const clone = resp.clone();
							caches.open(CACHE).then((cache) => cache.put(event.request, clone));
						}
						return resp;
					})
			)
		);
	}
});