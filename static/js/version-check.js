// Проверка версии приложения и очистка кэша
// Возвращает Promise, который завершается только при смене версии
function getCurrentVersion() {
  const meta = document.querySelector('meta[name="app-version"]');
  if (meta) {
    return Promise.resolve(meta.getAttribute('content'));
  }
  return fetch('/VERSION', { cache: 'no-store' })
    .then((r) => r.text())
    .then((v) => v.trim());
}

function checkVersion() {
  const stored = localStorage.getItem('appVersion');

  return new Promise((resolve) => {
    getCurrentVersion().then((current) => {
      if (stored === current) {
        // Ничего не делаем, страница продолжит загрузку
        return;
      }

      const auth = localStorage.getItem('authToken');
      localStorage.clear();
      if (auth) {
        localStorage.setItem('authToken', auth);
      }

      let cachePromise = Promise.resolve();
      if (typeof caches !== 'undefined') {
        cachePromise = caches
          .keys()
          .then((names) => Promise.all(names.map((n) => caches.delete(n))));
      }

      cachePromise.then(() => {
        localStorage.setItem('appVersion', current);
        resolve();
      });
    });
  });
}

// Экспортируем функцию в глобальную область видимости
window.checkVersion = checkVersion;
