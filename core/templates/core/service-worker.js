self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

// Never store responses: authenticated pages and uploads must not survive logout.
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET" || event.request.mode !== "navigate") return;

  // Bypass the HTTP cache too, so navigation cannot reuse a stored private page.
  event.respondWith(fetch(event.request, {cache: "no-store"}).catch(() => new Response(`<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#153f42"><title>Offline · Campus Radar</title>
<style>body{font:1rem/1.5 system-ui,sans-serif;background:#f5f7f5;color:#172e35;margin:0}header{background:#153f42;color:white;padding:1rem 1.5rem;font-weight:700}main{max-width:36rem;margin:3rem auto;padding:0 1.5rem}a{display:inline-block;background:#153f42;color:white;border-radius:.4rem;padding:.75rem 1.25rem;text-decoration:none;font-weight:600}a:focus-visible{outline:3px solid #176a65;outline-offset:3px}</style></head>
<body><header>Campus Radar</header><main><h1>You are offline</h1><p>Connect to the internet to view your information or make changes. Reminders may not be delivered while offline.</p><p><a href="">Try again</a></p></main></body></html>`, {
    status: 503,
    headers: {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"},
  })));
});
