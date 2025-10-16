'use strict';

// РҐРµР»РїРµСЂ РґР»СЏ РѕР±РЅРѕРІР»РµРЅРёСЏ Р±РµР№РґР¶Р° СЃС‚Р°С‚СѓСЃР° Р·Р°СЏРІРєРё
(function () {
  window.updateStatusBadge = function (label, cssClass) {
    const badge =
      document.querySelector('[data-status-badge]') ||
      document.querySelector('.status-badge') ||
      document.querySelector('.status-badge-large') ||
      document.querySelector('.table-status') ||
      document.getElementById('request-status-badge') ||
      document.querySelector('.badge');

    if (badge) {
      const isLarge = badge.classList.contains('status-badge-large');
      badge.textContent = label;
      badge.className = `${
        isLarge ? 'status-badge-large' : 'status-badge'
      } status-${cssClass}`;
    }
  };
})();
