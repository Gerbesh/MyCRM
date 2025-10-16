// Кастомные модальные окна для alert и confirm
(function () {
  function ensureModal() {
    let overlay = document.getElementById('customModalOverlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'customModalOverlay';
      overlay.className = 'custom-modal-overlay';
      overlay.innerHTML = `
        <div class="custom-modal">
          <i class="bi bi-exclamation-triangle-fill icon"></i>
          <div id="customModalMessage"></div>
          <div class="custom-modal-buttons" id="customModalButtons"></div>
        </div>`;
      document.body.appendChild(overlay);
    }
    return overlay;
  }

  function showModal(message, withCancel) {
    return new Promise((resolve) => {
      const overlay = ensureModal();
      const msg = document.getElementById('customModalMessage');
      const btns = document.getElementById('customModalButtons');
      msg.textContent = message;
      btns.innerHTML = '';

      const okBtn = document.createElement('button');
      okBtn.className = 'btn btn-primary';
      okBtn.textContent = withCancel ? 'Да' : 'Ок';
      okBtn.addEventListener('click', () => {
        overlay.classList.remove('show');
        resolve(true);
      });
      btns.appendChild(okBtn);

      if (withCancel) {
        const cancelBtn = document.createElement('button');
        cancelBtn.className = 'btn btn-secondary';
        cancelBtn.textContent = 'Нет';
        cancelBtn.addEventListener('click', () => {
          overlay.classList.remove('show');
          resolve(false);
        });
        btns.appendChild(cancelBtn);
      }

      overlay.classList.add('show');
    });
  }

  window.customAlert = function (message) {
    return showModal(message, false);
  };

  window.customConfirm = function (message) {
    return showModal(message, true);
  };

  // Переопределяем стандартный alert
  window.alert = window.customAlert;

  // Делегирование для элементов с data-confirm
  document.addEventListener('DOMContentLoaded', function () {
    document.body.addEventListener('click', async function (e) {
      const target = e.target.closest('[data-confirm]');
      if (target && target.tagName !== 'FORM') {
        // Предотвращаем немедленное выполнение действия до ответа пользователя
        e.preventDefault();
        e.stopImmediatePropagation();

        const msg = target.getAttribute('data-confirm');
        const ok = await window.customConfirm(msg);
        if (ok) {
          // Убираем атрибут, чтобы повторный клик не вызывал модалку
          target.removeAttribute('data-confirm');
          target.click();
          target.setAttribute('data-confirm', msg);
        }
      }
    });

    document.body.addEventListener('submit', async function (e) {
      const form = e.target;
      if (form.matches('[data-confirm]')) {
        e.preventDefault();
        const msg = form.getAttribute('data-confirm');
        const ok = await window.customConfirm(msg);
        if (ok) {
          form.submit();
        }
      }
    });
  });
})();
