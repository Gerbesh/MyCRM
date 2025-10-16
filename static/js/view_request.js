'use strict';

(function () {
  function getConfig() {
    const root =
      document.querySelector('.request-detail-container') || document.body;
    return {
      deleteCommentUrlTemplate:
        root.getAttribute('data-delete-comment-url-template') || '',
      addCommentUrl: root.getAttribute('data-add-comment-url') || '',
      updateDateUrl: root.getAttribute('data-update-date-url') || '',
      requestId: root.getAttribute('data-request-id') || '',
      createdAtFormValue: root.getAttribute('data-created-at-form-value') || '',
      timezoneTitle: root.getAttribute('data-timezone-title') || '',
      timezoneHint: root.getAttribute('data-timezone-hint') || '',
      timezoneAbbr: root.getAttribute('data-timezone-abbr') || '',
    };
  }

  async function copyToClipboard(text) {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
      await navigator.clipboard.writeText(text);
      return true;
    }

    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.top = '-1000px';
    textarea.style.left = '-1000px';
    document.body.appendChild(textarea);
    textarea.select();
    textarea.setSelectionRange(0, textarea.value.length);

    let success = false;
    try {
      success = document.execCommand('copy');
    } catch (err) {
      success = false;
    }
    textarea.remove();
    return success;
  }

  function startTimer(btn, seconds, timersMap) {
    const commentId = btn.dataset.commentId;
    let timeLeft = seconds;
    const timerElement = btn.querySelector('.timer');
    const timer = setInterval(() => {
      timeLeft--;
      if (timerElement) timerElement.textContent = String(timeLeft);
      if (timeLeft <= 0) {
        clearInterval(timer);
        btn.remove();
        timersMap.delete(commentId);
      }
    }, 1000);
    timersMap.set(commentId, timer);
  }

  document.addEventListener('DOMContentLoaded', () => {
    const timers = new Map();
    const config = getConfig();
    const { deleteCommentUrlTemplate, addCommentUrl } = config;
    const container = document.querySelector('.request-detail-container');

    const copyBtn = container?.querySelector('[data-copy-request-id]') || null;
    if (copyBtn) {
      copyBtn.addEventListener('click', async () => {
        const requestId =
          container?.dataset.requestId || config.requestId || copyBtn.dataset.requestId || '';
        if (!requestId) return;

        const icon = copyBtn.querySelector('i');
        try {
          const success = await copyToClipboard(requestId);
          if (!success) {
            throw new Error('COPY_FAILED');
          }
          if (typeof window.showToast === 'function') {
            window.showToast('Номер заявки скопирован', 'success');
          }
          if (icon) {
            icon.classList.remove('bi-clipboard');
            icon.classList.add('bi-clipboard-check');
            setTimeout(() => {
              icon.classList.remove('bi-clipboard-check');
              icon.classList.add('bi-clipboard');
            }, 2000);
          }
        } catch (err) {
          if (typeof window.showToast === 'function') {
            window.showToast('Не удалось скопировать номер заявки', 'danger');
          } else {
            alert('Не удалось скопировать номер заявки');
          }
        }
      });
    }

    const editDateModalEl = document.getElementById('editDateModal');
    const editDateForm = document.getElementById('editDateForm');
    const dateInput = document.getElementById('requestCreatedAtInput');
    const dateErrorBox = editDateModalEl?.querySelector('[data-edit-date-error]') || null;
    const dateHintEl = editDateModalEl?.querySelector('[data-edit-date-hint]') || null;
    let editDateModal = null;

    if (container && config.timezoneHint && dateHintEl) {
      dateHintEl.textContent = config.timezoneHint;
    }

    function showDateError(message, highlight) {
      if (dateErrorBox) {
        if (message) {
          dateErrorBox.textContent = message;
          dateErrorBox.classList.remove('d-none');
        } else {
          dateErrorBox.textContent = '';
          dateErrorBox.classList.add('d-none');
        }
      }
      if (dateInput) {
        if (highlight) {
          dateInput.classList.add('is-invalid');
        } else {
          dateInput.classList.remove('is-invalid');
        }
      }
    }

    const editDateBtn = container?.querySelector('[data-action="edit-date"]') || null;
    if (editDateBtn && editDateModalEl && editDateForm && dateInput) {
      if (window.bootstrap && window.bootstrap.Modal) {
        editDateModal =
          typeof window.bootstrap.Modal.getOrCreateInstance === 'function'
            ? window.bootstrap.Modal.getOrCreateInstance(editDateModalEl)
            : new window.bootstrap.Modal(editDateModalEl);
      }

      editDateBtn.addEventListener('click', () => {
        const storedValue =
          container.dataset.createdAtFormValue || config.createdAtFormValue || '';
        dateInput.value = storedValue;
        showDateError('', false);
        if (dateHintEl) {
          const hint = container.dataset.timezoneHint || config.timezoneHint;
          if (hint) dateHintEl.textContent = hint;
        }
        if (editDateModal) {
          editDateModal.show();
          setTimeout(() => {
            dateInput.focus();
          }, 150);
        }
      });

      editDateModalEl.addEventListener('hidden.bs.modal', () => {
        showDateError('', false);
        const submitBtn = editDateForm.querySelector('button[type="submit"]');
        if (submitBtn) submitBtn.disabled = false;
      });

      editDateForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        showDateError('', false);
        const submitBtn = editDateForm.querySelector('button[type="submit"]');
        const newValue = dateInput.value.trim();
        if (!newValue) {
          showDateError('Укажите дату и время размещения', true);
          return;
        }

        if (submitBtn) submitBtn.disabled = true;

        const formData = new FormData(editDateForm);
        formData.set('created_at', newValue);

        const fetchFn = window.fetchRetry
          ? (input, init) => window.fetchRetry(input, init)
          : window.fetch.bind(window);

        let response;
        let data;
        try {
          response = await fetchFn(config.updateDateUrl || editDateForm.action, {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
          });
          data = await response.json().catch(() => null);
          const ok = response.ok && data && data.success;
          if (!ok) {
            const errorMessage =
              (data && (data.error || data.message)) || 'Не удалось обновить дату';
            const highlight = response && response.status === 400;
            showDateError(errorMessage, highlight);
            if (typeof window.showToast === 'function') {
              window.showToast(errorMessage, 'danger');
            }
            return;
          }

          const displayEl = container?.querySelector('[data-created-at-display]');
          if (displayEl && data.created_at_display) {
            displayEl.textContent = data.created_at_display;
          }

          const abbrEl = container?.querySelector('[data-timezone-abbr]');
          if (abbrEl) {
            if (data.timezone_abbr) {
              abbrEl.textContent = data.timezone_abbr;
              container.dataset.timezoneAbbr = data.timezone_abbr;
            }
            if (data.timezone_title) {
              abbrEl.setAttribute('title', data.timezone_title);
              container.dataset.timezoneTitle = data.timezone_title;
            }
          }

          if (dateHintEl && data.timezone_hint) {
            dateHintEl.textContent = data.timezone_hint;
            container.dataset.timezoneHint = data.timezone_hint;
          }

          if (typeof data.created_at_form_value === 'string') {
            container.dataset.createdAtFormValue = data.created_at_form_value;
            config.createdAtFormValue = data.created_at_form_value;
            dateInput.value = data.created_at_form_value;
          }

          if (typeof window.showToast === 'function') {
            window.showToast(data.message || 'Дата обновлена', 'success');
          }
          showDateError('', false);
          if (editDateModal) editDateModal.hide();
        } catch (err) {
          const message =
            (data && (data.error || data.message)) ||
            (err && err.message) ||
            'Не удалось обновить дату';
          const highlight = response && response.status === 400;
          showDateError(message, highlight);
          if (typeof window.showToast === 'function') {
            window.showToast(message, 'danger');
          }
        } finally {
          if (submitBtn) submitBtn.disabled = false;
        }
      });
    }

    const deleteModalEl = document.getElementById('deleteModal');
    const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
    const manufacturerNameEl = document.getElementById('deleteManufacturerName');
    let currentAttachmentId = null;
    let currentScreenshotCard = null;

    let screenshotModal = null;
    if (deleteModalEl && window.bootstrap && window.bootstrap.Modal) {
      if (typeof window.bootstrap.Modal.getOrCreateInstance === 'function') {
        screenshotModal = window.bootstrap.Modal.getOrCreateInstance(deleteModalEl);
      } else {
        screenshotModal = new window.bootstrap.Modal(deleteModalEl);
      }
    }

    function getCommentsCard() {
      return Array.from(document.querySelectorAll('.detail-card')).find(
        (card) => {
          const header = card.querySelector('.header-title');
          return header && header.textContent.trim() === 'Комментарии';
        }
      );
    }

    function updateCommentsSection() {
      const card = getCommentsCard();
      if (!card) return;

      const commentsCount = card.querySelectorAll('[data-comment-id]').length;
      const header = card.querySelector('.card-header-modern');
      if (header) {
        let badge = header.querySelector('.header-badge');
        if (commentsCount > 0) {
          if (!badge) {
            badge = document.createElement('div');
            badge.className = 'header-badge';
            header.appendChild(badge);
          }
          badge.textContent = String(commentsCount);
        } else if (badge) {
          badge.remove();
        }
      }

      const cardBody = card.querySelector('.card-content-modern');
      if (!cardBody) return;

      const commentsSection = cardBody.querySelector('.comments-section');
      const formSection = cardBody.querySelector('.add-comment-section');
      const existingEmpty = cardBody.querySelector('.empty-comments');

      if (commentsCount === 0) {
        let emptyMessage = existingEmpty;
        if (!emptyMessage) {
          emptyMessage = document.createElement('div');
          emptyMessage.className = 'empty-comments';
          emptyMessage.innerHTML = `
              <div class="empty-icon"><i class="bi bi-chat"></i></div>
              <p>Комментариев пока нет</p>`;
        }
        if (commentsSection) {
          if (formSection) {
            commentsSection.insertBefore(emptyMessage, formSection);
          } else if (!emptyMessage.parentNode) {
            commentsSection.appendChild(emptyMessage);
          }
        }
      } else if (existingEmpty) {
        existingEmpty.remove();
      }
    }

    function getScreenshotsCard() {
      return Array.from(document.querySelectorAll('.detail-card')).find((card) => {
        const header = card.querySelector('.header-title');
        return header && header.textContent.trim() === 'Скриншоты производителей';
      });
    }

    function updateScreenshotsSection() {
      const card = getScreenshotsCard();
      if (!card) return;

      const remainingScreenshots = card.querySelectorAll('.screenshot-card').length;
      const badge = card.querySelector('.header-badge');
      if (badge) {
        if (remainingScreenshots > 0) {
          badge.textContent = String(remainingScreenshots);
        } else {
          badge.remove();
        }
      } else if (remainingScreenshots > 0) {
        const header = card.querySelector('.card-header-modern');
        if (header) {
          const newBadge = document.createElement('div');
          newBadge.className = 'header-badge';
          newBadge.textContent = String(remainingScreenshots);
          header.appendChild(newBadge);
        }
      }

      const grid = card.querySelector('.screenshots-grid');
      if (!grid) return;

      const placeholder = grid.querySelector('.screenshots-empty-placeholder');
      if (remainingScreenshots === 0) {
        if (!placeholder) {
          const empty = document.createElement('div');
          empty.className =
            'screenshots-empty-placeholder text-muted text-center py-4';
          empty.textContent = 'Скриншоты отсутствуют';
          grid.appendChild(empty);
        }
      } else if (placeholder) {
        placeholder.remove();
      }
    }

    const screenshotButtons = document.querySelectorAll('.delete-screenshot-btn');
    if (screenshotButtons.length && deleteModalEl && confirmDeleteBtn) {
      screenshotButtons.forEach((btn) => {
        btn.addEventListener('click', () => {
          currentAttachmentId = btn.dataset.attachmentId || null;
          currentScreenshotCard = btn.closest('.screenshot-card');
          if (manufacturerNameEl) {
            manufacturerNameEl.textContent = btn.dataset.manufacturer || '';
          }
          confirmDeleteBtn.dataset.attachmentId = currentAttachmentId || '';
          confirmDeleteBtn.dataset.requestId = btn.dataset.requestId || '';
          confirmDeleteBtn.dataset.manufacturer = btn.dataset.manufacturer || '';
          if (screenshotModal) {
            screenshotModal.show();
          }
        });
      });

      deleteModalEl.addEventListener('hidden.bs.modal', () => {
        confirmDeleteBtn.disabled = false;
        delete confirmDeleteBtn.dataset.attachmentId;
        delete confirmDeleteBtn.dataset.requestId;
        delete confirmDeleteBtn.dataset.manufacturer;
        currentAttachmentId = null;
        currentScreenshotCard = null;
      });

      confirmDeleteBtn.addEventListener('click', async function () {
        if (!currentAttachmentId) return;

        this.disabled = true;
        const url = `/files/delete_screenshot/${currentAttachmentId}`;
        const headers = {
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': window.getCSRFToken ? window.getCSRFToken() : '',
        };
        const fetchFn = window.fetchRetry
          ? (input, init) => window.fetchRetry(input, init)
          : window.fetch.bind(window);

        try {
          const response = await fetchFn(url, { method: 'POST', headers });
          let data = null;
          try {
            data = await response.json();
          } catch (err) {
            data = null;
          }

          if (!response.ok || !data || !data.success) {
            const message =
              (data && data.error) || response.statusText || 'Ошибка удаления';
            throw new Error(message);
          }

          if (screenshotModal) screenshotModal.hide();
          if (currentScreenshotCard) currentScreenshotCard.remove();
          updateScreenshotsSection();

          if (typeof window.showToast === 'function') {
            window.showToast('Скриншот удалён', 'success');
          }

          currentAttachmentId = null;
          currentScreenshotCard = null;
        } catch (err) {
          console.error('Ошибка удаления скриншота:', err);
          if (typeof window.showToast === 'function') {
            window.showToast(
              `Не удалось удалить скриншот: ${err.message}`,
              'error',
              5000
            );
          } else {
            alert(`Ошибка: ${err.message}`);
          }
        } finally {
          this.disabled = false;
        }
      });
    }

    document.addEventListener('click', async function (e) {
      const btn = e.target.closest('.delete-comment-btn');
      if (!btn) return;
      const commentId = btn.dataset.commentId;
      if (typeof window.customConfirm === 'function') {
        if (
          !(await window.customConfirm(
            'Вы действительно хотите удалить комментарий?'
          ))
        )
          return;
      } else if (!window.confirm('Удалить комментарий?')) {
        return;
      }

      const originalText = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = '<i class="bi bi-spinner bi-spin"></i> Удаление...';

      if (timers.has(commentId)) {
        clearInterval(timers.get(commentId));
        timers.delete(commentId);
      }

      const deleteUrl = deleteCommentUrlTemplate.replace(
        '0',
        String(commentId)
      );
      try {
        const headers = {
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': window.getCSRFToken ? window.getCSRFToken() : '',
        };
        const response = await (window.fetchRetry
          ? window.fetchRetry(deleteUrl, { method: 'POST', headers })
          : fetch(deleteUrl, { method: 'POST', headers }));
        const data = await response.json();
        if (!response.ok || !data.success)
          throw new Error(data.error || 'Ошибка сервера');
        const commentElement = document.querySelector(
          `[data-comment-id="${commentId}"]`
        );
        if (commentElement) commentElement.remove();
        updateCommentsSection();
      } catch (err) {
        console.error('Error:', err);
        alert('Ошибка: ' + err.message);
        btn.disabled = false;
        btn.innerHTML = originalText;
      }
    });

    // Запуск таймеров на существующих кнопках
    document
      .querySelectorAll('.delete-comment-btn[data-remaining-time]')
      .forEach((btn) => {
        const secs = parseInt(btn.dataset.remainingTime, 10);
        if (secs > 0) startTimer(btn, secs, timers);
      });

    // Обработка формы добавления комментария
    const commentForm = document.getElementById('add-comment-form');
    if (commentForm) {
      commentForm.addEventListener('submit', function (e) {
        e.preventDefault();
        const content = (document.getElementById('content') || {}).value || '';
        const text = content.trim();
        if (!text) {
          alert('Комментарий не может быть пустым');
          return;
        }
        const submitBtn = this.querySelector('button[type="submit"]');
        const originalHtml = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML =
          '<i class="bi bi-spinner bi-spin me-2"></i>Обработка...';

        const headers = {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': window.getCSRFToken ? window.getCSRFToken() : '',
        };
        (window.fetchRetry
          ? window.fetchRetry(
              addCommentUrl,
              {
                method: 'POST',
                headers,
                body: `content=${encodeURIComponent(text)}`,
              },
              2,
              10000,
              window.__originalFetch
            )
          : fetch(addCommentUrl, {
              method: 'POST',
              headers,
              body: `content=${encodeURIComponent(text)}`,
            })
        )
          .then((response) =>
            response.json().then((data) => ({ ok: response.ok, data }))
          )
          .then(({ ok, data }) => {
            if (!ok || !data.success)
              throw new Error((data && data.error) || 'Неизвестная ошибка');
            const commentsList =
              document.querySelector('.comments-section .comments-list') ||
              document.querySelector('.comments-section');
            if (commentsList && data.rendered_html) {
              commentsList.insertAdjacentHTML('afterbegin', data.rendered_html);
              const newComment = commentsList.querySelector('.comment-card');
              const newBtn = newComment
                ? newComment.querySelector(
                    '.delete-comment-btn[data-remaining-time]'
                  )
                : null;
              if (newBtn)
                startTimer(
                  newBtn,
                  parseInt(newBtn.dataset.remainingTime, 10),
                  timers
                );
            }
            (document.getElementById('content') || {}).value = '';
            updateCommentsSection();
            const submitBtn2 = commentForm.querySelector('.comment-submit-btn');
            if (submitBtn2) {
              submitBtn2.disabled = false;
              submitBtn2.innerHTML =
                '<i class="bi bi-check2 me-2"></i>Отправлено!';
              submitBtn2.classList.remove('btn-primary');
              submitBtn2.classList.add('btn-success');
              setTimeout(() => {
                submitBtn2.innerHTML =
                  '<i class="bi bi-send me-2"></i>Отправить';
                submitBtn2.classList.remove('btn-success');
                submitBtn2.classList.add('btn-primary');
              }, 2000);
            }
          })
          .catch((err) => {
            console.error('Error:', err);
            const errorMsg =
              err.message || 'Произошла ошибка при добавлении комментария';
            const errorToast = document.createElement('div');
            errorToast.className =
              'alert alert-danger alert-dismissible fade show';
            errorToast.style.cssText =
              'position: fixed; top: 20px; right: 20px; z-index: 1080; max-width: 350px; margin: 0;';
            errorToast.innerHTML = `<i class="bi bi-exclamation-triangle me-2"></i>${errorMsg}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
            document.body.appendChild(errorToast);
            setTimeout(() => {
              if (errorToast.parentNode) errorToast.remove();
            }, 5000);
          })
          .finally(() => {
            const submitBtn3 = commentForm.querySelector('.comment-submit-btn');
            if (submitBtn3 && submitBtn3.innerHTML.includes('spinner')) {
              submitBtn3.disabled = false;
              submitBtn3.innerHTML = '<i class="bi bi-send me-2"></i>Отправить';
            }
          });
      });
    }

    // Просмотр изображений на весь экран
    document.querySelectorAll('.clickable-image').forEach(function (image) {
      image.addEventListener('click', function () {
        const img = this;
        const overlay = document.createElement('div');
        overlay.className = 'image-fullscreen';
        const fullImg = document.createElement('img');
        fullImg.src = img.dataset.fullsize;
        overlay.appendChild(fullImg);
        document.body.appendChild(overlay);
        function closeOverlay() {
          overlay.remove();
          document.removeEventListener('keydown', onKeyDown);
        }
        function onKeyDown(e) {
          if (e.key === 'Escape') closeOverlay();
        }
        overlay.addEventListener('click', closeOverlay);
        document.addEventListener('keydown', onKeyDown);
      });
    });
  });
})();
