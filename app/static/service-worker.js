const CACHE_NAME = "motodb-v48";
const APP_SHELL = [
  "/static/css/app.css",
  "/static/js/app.js",
  "/static/js/help.js",
  "/static/js/indexeddb.js",
  "/static/js/sync.js",
  "/static/js/theme.js",
  "/static/fonts/IBMPlexSans-Regular-Latin1.woff2",
  "/static/fonts/IBMPlexSans-Medium-Latin1.woff2",
  "/static/fonts/IBMPlexSans-SemiBold-Latin1.woff2",
  "/static/fonts/IBMPlexSans-Bold-Latin1.woff2",
  "/static/fonts/IBMPlexMono-Regular-Latin1.woff2",
  "/static/fonts/IBMPlexMono-Medium-Latin1.woff2",
  "/static/fonts/IBMPlexMono-SemiBold-Latin1.woff2",
  "/manifest.webmanifest",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);

  if (url.origin !== self.location.origin || url.pathname.startsWith("/uploads/")) {
    event.respondWith(fetch(event.request));
    return;
  }

  if (!APP_SHELL.includes(url.pathname) && !url.pathname.startsWith("/static/")) {
    event.respondWith(fetch(event.request));
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        return response;
      })
      .catch(() => caches.match(event.request).then((cached) => cached || caches.match("/")))
  );
});
