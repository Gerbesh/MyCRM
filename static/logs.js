document.addEventListener('DOMContentLoaded', () => {
  const logEl = document.getElementById('log-content');
  if (!logEl) return;
  const url = logEl.dataset.url;

  async function loadLogs() {
    try {
      const response = await fetch(url);
      if (response.ok) {
        const text = await response.text();
        logEl.textContent = text;
      }
    } catch (e) {
      console.error('РћС€РёР±РєР° РїСЂРё Р·Р°РіСЂСѓР·РєРµ Р»РѕРіРѕРІ:', e);
    }
  }

  loadLogs();
  setInterval(loadLogs, 10000);
});
