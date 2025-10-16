'use strict';

// Лёгкая система аудита UI-событий
(function () {
  function send(name, data) {
    try {
      const headers = {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-Request-Id':
          window.__rid ||
          (window.__rid = self.crypto?.randomUUID?.() || String(Date.now())),
      };
      const auditToken =
        document
          .querySelector('meta[name="audit-token"]')
          ?.getAttribute('content') || window.AUDIT_EVENT_TOKEN;
      if (auditToken) headers['X-Audit-Token'] = auditToken;

      fetch('/api/v1/audit/event', {
        method: 'POST',
        headers,
        body: JSON.stringify({ name, data }),
        keepalive: true,
      }).catch(() => {});
    } catch (e) {
      // ignore
    }
  }

  let lastAuditClickTs = 0;
  document.addEventListener(
    'click',
    (e) => {
      const now = Date.now();
      if (now - lastAuditClickTs < 250) return;
      lastAuditClickTs = now;

      const t = e.target.closest(
        '[data-audit], a, button, input, [role="button"]'
      );
      if (!t) return;

      const id = t.id || '';
      const href = t.getAttribute && t.getAttribute('href');
      if (id === 'userDropdown' || href === '#') return;

      const info = {
        tag: t.tagName,
        id: id || null,
        cls: t.className || null,
        href: href,
        name:
          t.getAttribute &&
          (t.getAttribute('data-audit') ||
            t.getAttribute('name') ||
            t.textContent?.trim()?.slice(0, 64)),
        path: location.pathname,
      };
      send('click', info);
    },
    { capture: true }
  );

  const pushState = history.pushState;
  history.pushState = function () {
    pushState.apply(this, arguments);
    send('nav', { path: location.pathname });
  };
  window.addEventListener('popstate', () =>
    send('nav', { path: location.pathname })
  );

  window.addEventListener('error', (e) => {
    send('js_error', {
      msg: e.message,
      src: e.filename,
      line: e.lineno,
      col: e.colno,
    });
  });
  window.addEventListener('unhandledrejection', (e) => {
    send('js_unhandledrejection', { reason: String(e.reason) });
  });
})();
