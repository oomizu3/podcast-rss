// 記事投稿アプリの殻（画面・アイコン）だけを控えておく。GitHub の API や原稿・結果ファイルは必ずネットワークへ。
const CACHE = "schoolpost-shell-v1";
const SHELL = ["./", "index.html", "manifest.webmanifest", "icon.svg", "icon-192.png", "icon-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  // 消すのはこのアプリの古い控えだけ（同じ置き場所の kpipe アプリの控えには触らない）
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("schoolpost-shell-") && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  // 自分の置き場所の外（api.github.com など）は一切触らない＝ネットワークのまま
  if (url.origin !== self.location.origin) return;
  const scope = new URL(self.registration.scope);
  if (!url.pathname.startsWith(scope.pathname)) return;
  // 殻は「まずネットワーク、だめなら控え」。更新がすぐ届き、電波がなくても開ける
  e.respondWith(
    fetch(req)
      .then((res) => {
        if (res && res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      })
      .catch(() => caches.match(req, {ignoreSearch: true}).then((m) => m || caches.match("index.html")))
  );
});
