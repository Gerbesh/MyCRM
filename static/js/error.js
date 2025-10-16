'use strict';

// Скрипты страницы ошибок: авто‑скрытие флешей, копирование и отправка отчёта
(function () {
  function getErrorData() {
    try {
      const el = document.getElementById('error-data');
      if (!el) return null;
      return JSON.parse(el.textContent || '{}');
    } catch (e) {
      return null;
    }
  }

  function autoHideAlerts() {
    setTimeout(function () {
      var alerts = document.querySelectorAll('.alert:not(.alert-danger)');
      alerts.forEach(function (alert) {
        alert.style.transition = 'opacity 0.5s';
        alert.style.opacity = '0';
        setTimeout(function () {
          if (alert && alert.parentNode) alert.remove();
        }, 500);
      });
    }, 5000);
  }

  window.copyErrorDetails = function copyErrorDetails() {
    const data = getErrorData();
    const text = JSON.stringify(data || {}, null, 2);
    navigator.clipboard
      .writeText(text)
      .then(function () {
        alert('Детали ошибки скопированы');
      })
      .catch(function () {
        console.log('Error details:', text);
        alert('Не удалось скопировать. Детали показаны в консоли.');
      });
  };

  window.reportError = function reportError() {
    const payload = getErrorData() || {};
    const body = {
      name: 'error_report',
      data: payload,
      csrf_token:
        window.CSRF_TOKEN ||
        document
          .querySelector('meta[name="csrf-token"]')
          .getAttribute('content') ||
        '',
    };
    fetch('/api/v1/audit/event', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
      credentials: 'same-origin',
      body: JSON.stringify(body),
    })
      .then(function () {
        alert('Отчёт об ошибке отправлен');
      })
      .catch(function () {
        alert('Не удалось отправить отчёт');
      });
  };

  document.addEventListener('DOMContentLoaded', autoHideAlerts);
})();
