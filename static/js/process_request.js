'use strict';

(function () {
  // URL для получения всех объектов берём из data-атрибута модалки смены объекта
  function getConfig() {
    const el = document.getElementById('changeObjectModal') || document.body;
    return {
      GET_ALL_OBJECTS_URL:
        el.getAttribute('data-get-all-objects-url') || '/api/v1/objects',
      CHANGE_OBJECT_URL: el.getAttribute('data-change-object-url') || '',
    };
  }

  let objectsCache = [];
  let isObjectCacheLoaded = false;
  let isLoadingObjects = false;

  async function loadObjectsCache() {
    const { GET_ALL_OBJECTS_URL } = getConfig();
    if (isObjectCacheLoaded || isLoadingObjects)
      return Promise.resolve(objectsCache);
    isLoadingObjects = true;
    try {
      const response = await fetch(GET_ALL_OBJECTS_URL);
      if (response.ok) {
        const payload = await response.json();
        objectsCache = Array.isArray(payload)
          ? payload
          : Array.isArray(payload?.data)
            ? payload.data
            : [];
        isObjectCacheLoaded = true;
        const objectsCountSpan = document.getElementById('objects-count');
        if (objectsCountSpan)
          objectsCountSpan.textContent = String(objectsCache.length);
        return objectsCache;
      }
      // fallback
      objectsCache = [];
      isObjectCacheLoaded = true;
      const objectsCountSpan = document.getElementById('objects-count');
      if (objectsCountSpan) objectsCountSpan.textContent = 'поиск работает';
      return objectsCache;
    } catch (err) {
      console.warn('Ошибка загрузки объектов:', err);
      objectsCache = [];
      isObjectCacheLoaded = true;
      const objectsCountSpan = document.getElementById('objects-count');
      if (objectsCountSpan) objectsCountSpan.textContent = 'поиск работает';
      return objectsCache;
    } finally {
      isLoadingObjects = false;
    }
  }

  function calculateFuzzyScore(query, obj) {
    const name = (obj.name || '').toLowerCase();
    const address = (obj.address || '').toLowerCase();
    const customer = (obj.customer || '').toLowerCase();
    let maxScore = 0;
    if (name.startsWith(query)) maxScore = Math.max(maxScore, 100);
    if (address.startsWith(query)) maxScore = Math.max(maxScore, 95);
    if (customer.startsWith(query)) maxScore = Math.max(maxScore, 90);
    if (name.includes(query)) maxScore = Math.max(maxScore, 80);
    if (address.includes(query)) maxScore = Math.max(maxScore, 75);
    if (customer.includes(query)) maxScore = Math.max(maxScore, 70);
    const queryWords = query.split(/\s+/).filter((w) => w.length > 0);
    if (queryWords.length > 1) {
      const allWordsInName = queryWords.every((word) => name.includes(word));
      const allWordsInAddress = queryWords.every((word) =>
        address.includes(word)
      );
      const allWordsInCustomer = queryWords.every((word) =>
        customer.includes(word)
      );
      if (allWordsInName) maxScore = Math.max(maxScore, 65);
      if (allWordsInAddress) maxScore = Math.max(maxScore, 60);
      if (allWordsInCustomer) maxScore = Math.max(maxScore, 55);
    }
    queryWords.forEach((word) => {
      if (word.length >= 2) {
        if (name.includes(word)) maxScore = Math.max(maxScore, 45);
        if (address.includes(word)) maxScore = Math.max(maxScore, 40);
        if (customer.includes(word)) maxScore = Math.max(maxScore, 35);
      }
    });
    if (query.length >= 2) {
      name.split(/\s+/).forEach((word) => {
        if (word.startsWith(query)) maxScore = Math.max(maxScore, 30);
        if (word.includes(query) && word.length >= query.length)
          maxScore = Math.max(maxScore, 20);
      });
      address.split(/\s+/).forEach((word) => {
        if (word.startsWith(query)) maxScore = Math.max(maxScore, 25);
        if (word.includes(query) && word.length >= query.length)
          maxScore = Math.max(maxScore, 15);
      });
    }
    return maxScore;
  }

  function findFuzzyMatches(query, objects) {
    const normalizedQuery = query.toLowerCase().trim();
    const results = [];
    objects.forEach((obj) => {
      const score = calculateFuzzyScore(normalizedQuery, obj);
      if (score > 0) results.push({ ...obj, score });
    });
    return results.sort((a, b) => b.score - a.score);
  }

  function displayObjectSuggestions(objects, query = '') {
    const objectSuggestions = document.getElementById('object-suggestions');
    const objectInput = document.getElementById('new-object-input');
    const objectIdInput = document.getElementById('new-object-id');
    const confirmChangeBtn = document.getElementById(
      'confirm-change-object-btn'
    );
    if (!objectSuggestions) return;
    if (!objects.length) {
      objectSuggestions.innerHTML =
        '<div class="suggestion-item text-muted">Ничего не найдено</div>';
      objectSuggestions.style.display = 'block';
      return;
    }
    objectSuggestions.innerHTML = '';
    objects.slice(0, 10).forEach((obj) => {
      const div = document.createElement('div');
      div.className = 'suggestion-item';
      div.textContent = `${obj.name}${obj.address ? ' — ' + obj.address : ''}`;
      div.addEventListener('click', function () {
        if (objectInput) objectInput.value = obj.name;
        if (objectIdInput) objectIdInput.value = obj.id;
        if (confirmChangeBtn) confirmChangeBtn.disabled = false;
        objectSuggestions.style.display = 'none';
      });
      objectSuggestions.appendChild(div);
    });
    objectSuggestions.style.display = 'block';
  }

  function performObjectSearch(query) {
    if (isObjectCacheLoaded && objectsCache.length > 0) {
      const results = findFuzzyMatches(query, objectsCache).slice(0, 10);
      displayObjectSuggestions(results, query);
    } else {
      if (query.length >= 1) {
        fetch(`/search/search_objects?query=${encodeURIComponent(query)}`)
          .then((r) =>
            r.ok ? r.json() : Promise.reject(new Error('Search failed'))
          )
          .then((data) => displayObjectSuggestions(data || [], query))
          .catch(() => {
            const objectSuggestions =
              document.getElementById('object-suggestions');
            if (objectSuggestions) {
              objectSuggestions.innerHTML =
                '<div class="suggestion-item text-muted">Ошибка поиска</div>';
              objectSuggestions.style.display = 'block';
            }
          });
      } else {
        const objectSuggestions = document.getElementById('object-suggestions');
        if (objectSuggestions) objectSuggestions.style.display = 'none';
      }
    }
  }

  window.changeRequestObject = function () {
    if (window.ModalSystem) window.ModalSystem.show('changeObjectModal');
    const objectsCountSpan = document.getElementById('objects-count');
    if (objectsCountSpan) objectsCountSpan.textContent = 'поиск работает';
  };

  document.addEventListener('DOMContentLoaded', () => {
    const statusSelect = document.getElementById('status-select');
    const applyStatusBtn = document.getElementById('apply-status-btn');
    if (statusSelect && applyStatusBtn) {
      const requestId = applyStatusBtn.dataset.requestId;
      applyStatusBtn.addEventListener('click', () => {
        const newStatus = statusSelect.value;
        applyStatusBtn.disabled = true;
        fetch(`/requests/process/change_status/${requestId}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': window.getCSRFToken ? window.getCSRFToken() : '',
          },
          body: JSON.stringify({ status: newStatus }),
        })
          .then(async (r) => {
            if (!r.ok) {
              if (r.status === 429) {
                throw new Error('Слишком часто, попробуй позже');
              }
              let msg = r.statusText;
              try {
                const j = await r.json();
                if (j?.error) msg = j.error;
              } catch (_) {}
              throw new Error(msg || `HTTP ${r.status}`);
            }
            return r.json();
          })
          .then((data) => {
            if (data && data.success) {
              updateStatusBadge(data.label, data.class);
              if (typeof window.showToast === 'function') {
                window.showToast('Статус обновлён', 'success');
              }
            } else {
              throw new Error((data && data.error) || 'Ошибка');
            }
          })
          .catch((err) => {
            console.error('Error:', err);
            alert('Ошибка: ' + err.message);
          })
          .finally(() => {
            applyStatusBtn.disabled = false;
          });
      });
    }
    // Переключение содержимого подрядчиков по радио
    const contractorRadios = document.querySelectorAll(
      'input[name="contractor_id"]'
    );
    const contractorContents = document.querySelectorAll('.contractor-content');

    function showContractorContent(radio) {
      contractorContents.forEach((c) => (c.style.display = 'none'));
      if (radio && radio.checked) {
        const target = document.querySelector(
          `[data-contractor-id="${radio.value}"]`
        );
        if (target) target.style.display = 'block';
      }
    }

    contractorRadios.forEach((radio) => {
      ['change', 'click'].forEach((evt) => {
        radio.addEventListener(evt, () => showContractorContent(radio));
      });
      if (radio.checked) showContractorContent(radio);
    });

    // Вставка скриншотов из буфера обмена
    const screenshotInputs = document.querySelectorAll(
      'input[type="file"][name="screenshots[]"]'
    );
    screenshotInputs.forEach((input) => {
      input.addEventListener('paste', (e) => {
        const items = e.clipboardData?.items;
        if (!items) return;
        for (const item of items) {
          if (item.kind === 'file' && item.type.startsWith('image/')) {
            const blob = item.getAsFile();
            if (!blob) continue;
            const ext = item.type.split('/')[1] || 'png';
            const file = new File([blob], `screenshot.${ext}`, {
              type: item.type,
            });
            const dt = new DataTransfer();
            dt.items.add(file);
            input.files = dt.files;
            const checkbox = input
              .closest('div')
              ?.querySelector('input[type="checkbox"][name="manufacturers[]"]');
            if (checkbox) checkbox.checked = true;
            break;
          }
        }
      });
    });

    // Удаление скриншота (через модалку подтверждения)
    const deleteButtons = document.querySelectorAll('.delete-screenshot-btn');
    let currentAttachmentId = null;
    deleteButtons.forEach((btn) => {
      btn.addEventListener('click', function () {
        currentAttachmentId = this.dataset.attachmentId;
        window.ModalSystem && window.ModalSystem.show('deleteModal');
      });
    });

    const confirmDeleteBtn = document.getElementById('confirm-delete-btn');
    if (confirmDeleteBtn) {
      confirmDeleteBtn.addEventListener('click', function () {
        const attachmentId = currentAttachmentId;
        if (!attachmentId) return;
        confirmDeleteBtn.disabled = true;
        fetch(`/files/delete_screenshot/${attachmentId}`, {
          method: 'POST',
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': window.getCSRFToken ? window.getCSRFToken() : '',
          },
        })
          .then(async (r) => {
            if (!r.ok) {
              if (r.status === 429) {
                throw new Error('Слишком часто, попробуй позже');
              }
              let msg = r.statusText;
              try {
                const j = await r.json();
                if (j?.error) msg = j.error;
              } catch (_) {}
              throw new Error(msg || `HTTP ${r.status}`);
            }
            return r.json();
          })
          .then((data) => {
            if (data && data.success) {
              window.ModalSystem && window.ModalSystem.hide('deleteModal');
              const row = document.getElementById(
                `attachment-row-${attachmentId}`
              );
              if (row) row.remove();
              if (typeof window.showToast === 'function')
                window.showToast('Скриншот удалён', 'success');
              updateStatusBadge(
                window.STATUS_LABELS_RU.OPEN,
                window.STATUS_CLASS.OPEN
              );
            } else {
              throw new Error((data && data.error) || 'Ошибка');
            }
          })
          .catch((err) => {
            console.error('Error:', err);
            alert('Ошибка: ' + err.message);
          })
          .finally(() => {
            confirmDeleteBtn.disabled = false;
          });
      });
    }

    // Автокомплит для объектов
    const objectInput = document.getElementById('new-object-input');
    const objectSuggestions = document.getElementById('object-suggestions');
    const objectIdInput = document.getElementById('new-object-id');
    const confirmChangeBtn = document.getElementById(
      'confirm-change-object-btn'
    );
    const changeObjectModal = document.getElementById('changeObjectModal');
    let searchTimeout;
    if (objectInput) {
      objectInput.addEventListener('input', function () {
        const query = this.value.trim();
        clearTimeout(searchTimeout);
        if (query.length < 1) {
          if (objectSuggestions) objectSuggestions.style.display = 'none';
          if (objectIdInput) objectIdInput.value = '';
          if (confirmChangeBtn) confirmChangeBtn.disabled = true;
          return;
        }
        searchTimeout = setTimeout(() => performObjectSearch(query), 100);
      });
      objectInput.addEventListener('focus', function () {
        if (this.value.length >= 1) performObjectSearch(this.value.trim());
      });
      document.addEventListener('click', function (e) {
        if (
          !objectInput.contains(e.target) &&
          !objectSuggestions.contains(e.target)
        ) {
          objectSuggestions.style.display = 'none';
        }
      });
    }

    if (confirmChangeBtn) {
      confirmChangeBtn.addEventListener('click', function () {
        const newObjectId = objectIdInput ? objectIdInput.value : '';
        if (!newObjectId) {
          alert('Выберите объект из списка');
          return;
        }
        confirmChangeBtn.disabled = true;
        confirmChangeBtn.innerHTML =
          '<span class="spinner-border spinner-border-sm me-2"></span>зменяем...';
        const { CHANGE_OBJECT_URL } = getConfig();
        fetch(CHANGE_OBJECT_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ new_object_id: newObjectId }),
        })
          .then(async (r) => {
            if (!r.ok) {
              if (r.status === 429) {
                throw new Error('Слишком часто, попробуй позже');
              }
              let msg = r.statusText;
              try {
                const j = await r.json();
                if (j?.error) msg = j.error;
              } catch (_) {}
              throw new Error(msg || `HTTP ${r.status}`);
            }
            return r.json();
          })
          .then((data) => {
            if (data && data.success) {
              if (typeof window.showToast === 'function') {
                window.showToast('Объект заявки успешно изменён', 'success');
              }
              setTimeout(() => window.location.reload(), 1000);
            } else {
              throw new Error(
                (data && data.error) || 'Ошибка при изменении объекта'
              );
            }
          })
          .catch((err) => {
            console.error('Error:', err);
            alert('Ошибка: ' + err.message);
            confirmChangeBtn.disabled = false;
            confirmChangeBtn.innerHTML =
              '<i class="bi bi-check-lg me-1"></i>зменить объект';
          });
      });
    }

    if (changeObjectModal) {
      changeObjectModal.addEventListener('hidden.bs.modal', () => {
        if (objectInput) objectInput.value = '';
        if (objectIdInput) objectIdInput.value = '';
        if (objectSuggestions) objectSuggestions.style.display = 'none';
        if (confirmChangeBtn) {
          confirmChangeBtn.disabled = true;
          confirmChangeBtn.innerHTML =
            '<i class="bi bi-check-lg me-1"></i>зменить объект';
        }
      });
    }

    // Прогружаем кэш объектов фоном
    loadObjectsCache();
  });
})();
