document.addEventListener('DOMContentLoaded', () => {
  const wrap = document.getElementById('log-wrap');
  if (!wrap) return;
  const url = wrap.dataset.url;
  let delay = 10000;
  let pollId;

  async function load() {
    try {
      const r = await safeFetch(url, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        __isBackgroundPoll: true,
      });
      if (r.status === 200) {
        const j = await r.json();
        wrap.textContent = j.lines.join('\n');
        wrap.scrollTop = wrap.scrollHeight;
        delay = 10000;
      } else {
        delay = Math.min(delay * 2, 60000);
      }
    } catch (e) {
      delay = Math.min(delay * 2, 60000);
    } finally {
      pollId = setTimeout(load, delay);
    }
  }

  window.stopPolling = function () {
    if (pollId) {
      clearTimeout(pollId);
      pollId = null;
    }
  };

  load();
});
