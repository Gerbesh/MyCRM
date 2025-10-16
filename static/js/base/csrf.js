'use strict';

// CSRF helpers and fetch wrappers
(function () {
  function getCSRFToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : window.CSRF_TOKEN || '';
  }

  async function refreshCSRFToken() {
    try {
      const r = await safeFetch('/refresh_csrf', {
        credentials: 'same-origin',
        __isBackgroundPoll: true,
      });
      const data = await r.json().catch(() => null);
      if (data && data.csrf_token) {
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) meta.setAttribute('content', data.csrf_token);
        document.querySelectorAll('input[name="csrf_token"]').forEach((el) => {
          el.value = data.csrf_token;
        });
        window.CSRF_TOKEN = data.csrf_token;
        if (window.console) console.log('CSRF токен обновлён');
      }
    } catch (err) {
      if (window.console) console.error('Не удалось обновить CSRF токен', err);
    }
  }

  function handleCSRFError(response) {
    if (response && response.status === 400) {
      response
        .clone()
        .json()
        .then((data) => {
          if (data && data.csrf_error) {
            alert('Ошибка безопасности. Страница будет обновлена.');
            location.reload();
          }
        })
        .catch(() => {});
      return true;
    }
    return false;
  }

  async function fetchRetry(
    input,
    init = {},
    retries = 2,
    timeout = 10000,
    fetchImpl
  ) {
    const _fetch = fetchImpl || window.fetch.bind(window);
    for (let attempt = 0; attempt <= retries; attempt++) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeout);
      try {
        const resp = await _fetch(input, {
          ...init,
          signal: controller.signal,
        });
        clearTimeout(timer);
        if (!resp.ok && attempt < retries) {
          await new Promise((r) => setTimeout(r, 2 ** attempt * 1000));
          continue;
        }
        return resp;
      } catch (err) {
        clearTimeout(timer);
        if (attempt === retries) throw err;
        await new Promise((r) => setTimeout(r, 2 ** attempt * 1000));
      }
    }
  }

  async function safeFetch(input, init = {}) {
    try {
      const r = await fetchRetry(input, init, 2, 10000, window.__originalFetch);

      if ([502, 503, 504].includes(r.status)) {
        if (init.__isBackgroundPoll) {
          if (typeof window.stopPolling === 'function') window.stopPolling();
          if (typeof window.showToast === 'function') {
            window.showToast('Сервер перезапускается, подождите…');
          }
          return r;
        }
        throw new Error('SERVER_RESTART');
      }

      if (r.status === 401) {
        if (init.__isBackgroundPoll) {
          if (typeof window.stopPolling === 'function') window.stopPolling();
          if (typeof window.showToast === 'function') {
            window.showToast('Сессия истекла. Обновите страницу.');
          }
          return r;
        }
        if (typeof window.showReauthModal === 'function') {
          window.showReauthModal();
        } else if (typeof window.showToast === 'function') {
          window.showToast('Требуется повторный вход', 'warning', 5000);
        }
        throw new Error('AUTH_EXPIRED');
      }
      return r;
    } catch (err) {
      if (init.__isBackgroundPoll) {
        if (typeof window.stopPolling === 'function') window.stopPolling();
        if (typeof window.showToast === 'function') {
          window.showToast('Сеть недоступна, подождите…');
        }
        return new Response('', { status: 0, statusText: 'Network error' });
      }
      throw err;
    }
  }

  function showReauthModal() {
    if (typeof window.showToast === 'function') {
      window.showToast('Требуется повторный вход', 'warning', 5000);
    } else {
      alert('Требуется повторный вход');
    }
  }

  // Patch global fetch to automatically add CSRF for mutating requests
  const originalFetch = window.fetch.bind(window);
  window.__originalFetch = originalFetch;
  window.fetch = function (url, options = {}) {
    options.credentials = options.credentials || 'same-origin';

    if (
      options.method &&
      ['POST', 'PUT', 'DELETE', 'PATCH'].includes(options.method.toUpperCase())
    ) {
      options.headers = options.headers || {};
      const csrfToken = getCSRFToken();
      if (!options.headers['X-CSRFToken'])
        options.headers['X-CSRFToken'] = csrfToken;

      if (options.body instanceof FormData) {
        options.body.set('csrf_token', csrfToken);
      } else if (options.body instanceof URLSearchParams) {
        options.body.set('csrf_token', csrfToken);
      } else if (typeof options.body === 'string') {
        if (options.headers['Content-Type'] === 'application/json') {
          try {
            const data = JSON.parse(options.body);
            data.csrf_token = csrfToken;
            options.body = JSON.stringify(data);
          } catch (e) {
            const params = new URLSearchParams(options.body);
            params.set('csrf_token', csrfToken);
            options.body = params.toString();
            options.headers['Content-Type'] =
              'application/x-www-form-urlencoded';
          }
        } else {
          const params = new URLSearchParams(options.body);
          params.set('csrf_token', csrfToken);
          options.body = params.toString();
        }
      } else if (!options.body) {
        options.body = `csrf_token=${encodeURIComponent(csrfToken)}`;
        options.headers['Content-Type'] = 'application/x-www-form-urlencoded';
      }
    }

    return fetchRetry(url, options, 2, 10000, originalFetch).then(
      (response) => {
        if (!response.ok) {
          if (
            typeof url === 'string' &&
            url.startsWith('/api/v1/audit/event')
          ) {
            return response;
          }
          handleCSRFError(response);
        }
        return response;
      }
    );
  };

  // Expose helpers
  window.getCSRFToken = getCSRFToken;
  window.refreshCSRFToken = refreshCSRFToken;
  window.handleCSRFError = handleCSRFError;
  window.fetchRetry = fetchRetry;
  window.safeFetch = safeFetch;
  window.showReauthModal = showReauthModal;

  // Periodic CSRF refresh
  document.addEventListener('DOMContentLoaded', function () {
    setInterval(refreshCSRFToken, 10 * 60 * 1000);
  });
})();
