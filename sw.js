// sw.js (recommended)
const CACHE_NAME = "quiz-static-v1";

// 캐시할 파일 목록(네 앱에 맞게 수정)
const PRECACHE_URLS = [
  "/quiz/",
  "/quiz/index.html",
  "/quiz/manifest.webmanifest",
  // "/quiz/styles.css",
  // "/quiz/app.js",
  // "/quiz/bank_civil_1.js",
  // "/quiz/bank_civil_2.js",
];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS))
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys
          .filter((k) => k !== CACHE_NAME)
          .map((k) => caches.delete(k))
      );
      await self.clients.claim();
    })()
  );
});

// 네트워크 우선 + 실패 시 캐시
self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // 같은 origin만 처리 (CDN 등 외부는 건드리지 않음)
  if (url.origin !== self.location.origin) return;

  // API 호출은 캐시하지 않음 (너의 AI 서버 호출 등)
  if (url.pathname.startsWith("/api") || url.pathname.includes("onrender.com")) return;

  event.respondWith(
    (async () => {
      try {
        const fresh = await fetch(req);
        // GET만 캐시에 저장
        if (req.method === "GET") {
          const cache = await caches.open(CACHE_NAME);
          cache.put(req, fresh.clone());
        }
        return fresh;
      } catch (e) {
        const cached = await caches.match(req);
        if (cached) return cached;
        // 마지막 fallback: index.html (SPA 라우팅용)
        if (req.mode === "navigate") {
          const fallback = await caches.match("/quiz/index.html");
          if (fallback) return fallback;
        }
        throw e;
      }
    })()
  );
});
