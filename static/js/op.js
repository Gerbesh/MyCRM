'use strict';

(function () {
  function qs(sel, ctx = document) {
    return ctx.querySelector(sel);
  }
  function qsa(sel, ctx = document) {
    return Array.from(ctx.querySelectorAll(sel));
  }

  function debounce(fn, delay) {
    let timer;
    return function (...args) {
      const ctx = this;
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(ctx, args), delay);
    };
  }

  let selected = { id: null, name: '', address: '' };
  let currentStatuses = [];
  let currentSide = '';
  let currentObjectId = null;
  let viewRequestUrlTemplate = '';
  let requestsModalEl = null;
  let requestsListEl = null;

  // Р СџР С•Р Т‘Р С–Р С•Р Р… РЎР‚Р В°Р В·Р СР ВµРЎР‚Р В° РЎв‚¬РЎР‚Р С‘РЎвЂћРЎвЂљР В° Р С—Р С•Р Т‘ РЎв‚¬Р С‘РЎР‚Р С‘Р Р…РЎС“ Р С‘Р Р…Р С—РЎС“РЎвЂљР В°, РЎвЂЎРЎвЂљР С•Р В±РЎвЂ№ РЎвЂљР ВµР С”РЎРѓРЎвЂљ Р Р†Р В»Р ВµР В·Р В°Р В»
  function fitTextToInput(input, { min = 10, max = 14 } = {}) {
    if (!input) return;
    // Р РЋР В±РЎР‚Р С•РЎРѓ Р С” Р Т‘Р ВµРЎвЂћР С•Р В»РЎвЂљР Р…Р С•Р СРЎС“ Р С‘ Р С‘Р В·Р СР ВµРЎР‚Р ВµР Р…Р С‘Р Вµ
    input.style.fontSize = '';
    const computed = parseFloat(getComputedStyle(input).fontSize) || max;
    let size = Math.min(max, Math.max(min, computed));
    input.style.fontSize = size + 'px';
    let guard = 0;
    while (input.scrollWidth > input.clientWidth && size > min && guard < 40) {
      size -= 0.5;
      input.style.fontSize = size + 'px';
      guard++;
    }
  }

  function hideSearchWithAnimation(onHidden) {
    const container = qs('#op-search-container');
    if (!container) return onHidden && onHidden();
    container.classList.add('fade-out', 'slide-up');
    const done = () => {
      container.classList.add('d-none');
      container.classList.remove('fade-out', 'slide-up');
      container.removeEventListener('transitionend', done);
      if (onHidden) onHidden();
    };
    container.addEventListener('transitionend', done);
    setTimeout(done, 450);
  }

  function showSearchWithAnimation() {
    const container = qs('#op-search-container');
    if (!container) return;
    const content = qs('#op-content');
    if (content) content.classList.add('d-none');
    container.classList.remove('d-none');
    container.classList.add('fade-in', 'slide-down');
    const done = () => {
      container.classList.remove('fade-in', 'slide-down');
      container.removeEventListener('transitionend', done);
    };
    container.addEventListener('transitionend', done);
  }

  function showContent() {
    const content = qs('#op-content');
    if (content) content.classList.remove('d-none');
  }

  function resetRequestsList() {
    if (requestsListEl) {
      requestsListEl.innerHTML =
        '<li class="list-group-item text-center text-muted">Загрузка...</li>';
    }
  }

  function ensureRequestsModal() {
    if (!requestsModalEl) {
      requestsModalEl = qs('#requestsModal');
      if (requestsModalEl) {
        requestsListEl = qs('#requests-list', requestsModalEl);
        resetRequestsList();
        if (window.ModalSystem) {
          window.ModalSystem.init(requestsModalEl);
        }
        requestsModalEl.addEventListener('hidden.bs.modal', () => {
          resetRequestsList();
          qsa('.modal-backdrop').forEach((b) => b.remove());
          document.body.classList.remove('modal-open');
          document.body.style.overflow = '';
          document.body.style.paddingRight = '';
        });
        const closeBtn = qs('[data-bs-dismiss="modal"]', requestsModalEl);
        if (closeBtn) {
          closeBtn.addEventListener('click', () => {
            window.ModalSystem && window.ModalSystem.hide('requestsModal');
            setTimeout(
              () =>
                window.cleanupModalBackdrop && window.cleanupModalBackdrop(),
              200
            );
          });
        }
        requestsModalEl.addEventListener('click', (event) => {
          if (event.target === requestsModalEl) {
            window.ModalSystem && window.ModalSystem.hide('requestsModal');
          }
        });
      }
    }
    return requestsModalEl;
  }

  function renderRequestsList(items) {
    if (!requestsListEl) return;
    requestsListEl.innerHTML = '';
    if (!items || items.length === 0) {
      requestsListEl.innerHTML =
        '<li class="list-group-item text-center text-muted">Нет заявок</li>';
      return;
    }
    items.forEach((req) => {
      const code = String(req.status || '').toUpperCase();
      const statusClass = code === 'DONE' ? 'bg-success' : 'bg-warning';
      const createdAt = req.created_at ? new Date(req.created_at) : null;
      const dateLabel = createdAt ? createdAt.toLocaleDateString('ru-RU') : '';
      const dateHtml = dateLabel ? `от ${dateLabel}` : '—';
      const contractorsHtml =
        (req.contractors || [])
          .map((c) => `<span class="badge bg-primary me-1">${c.name}</span>`)
          .join('') || '<span class="text-muted">—</span>';
      const manufacturersHtml =
        (req.manufacturers || [])
          .map((m) => `<span class="badge bg-info me-1">${m}</span>`)
          .join('') || '<span class="text-muted">—</span>';
      const viewUrl =
        viewRequestUrlTemplate && viewRequestUrlTemplate.includes('0')
          ? viewRequestUrlTemplate.replace('0', String(req.id))
          : '';
      const item = document.createElement('li');
      item.className = 'list-group-item';
      item.innerHTML = `
        <div class="d-flex justify-content-between mb-2">
          <strong>Заявка #${req.id}</strong>
          <span class="badge ${statusClass}">${
            window.STATUS_LABELS_RU?.[code] || req.status || '—'
          }</span>
        </div>
        <div class="mb-1"><small><strong>Подрядчики:</strong></small><br>${contractorsHtml}</div>
        <div class="mb-1"><small><strong>Производители:</strong></small><br>${manufacturersHtml}</div>
        <div class="text-muted small">${dateHtml}</div>
        ${
          viewUrl
            ? `<div class="text-end mt-2">
                <a href="${viewUrl}" class="btn btn-sm btn-outline-primary">Открыть</a>
              </div>`
            : ''
        }
      `;
      requestsListEl.appendChild(item);
    });
  }

  function renderObjectCard(name, address = '') {
    const card = qs('#op-object-card');
    if (!card) return;
    card.innerHTML = `
      <div class="card-body d-flex align-items-start justify-content-between">
        <div>
          <h5 class="card-title mb-1">${name}</h5>
          ${address ? `<div class="text-muted">${address}</div>` : ''}
        </div>
        <button class="btn btn-sm btn-outline-secondary" id=\"op-change-btn\">Сменить объект</button>
      </div>`;
    const changeBtn = qs('#op-change-btn', card);
    if (changeBtn) {
      changeBtn.addEventListener('click', () => {
        selected = { id: null, name: '', address: '' };
        currentObjectId = null;
        const input = qs('#op-search');
        if (input) input.value = '';
        showSearchWithAnimation();
      });
    }
  }

  function loadGroupTags(objectId) {
    const params = new URLSearchParams();
    currentStatuses.forEach((s) => params.append('status', s));
    if (currentSide) params.append('side', currentSide);
    fetch(`/api/op/${objectId}/groups?${params.toString()}`)
      .then((r) => r.json())
      .then((data) => {
        const wrap = qs('#op-groups');
        if (!wrap) return;
        wrap.innerHTML = '';
        (data || []).forEach((g) => {
          const chip = document.createElement('span');
          chip.className = 'op-chip';
          chip.textContent = `${g.name} (${g.count})`;
          chip.dataset.groupId = g.id;
          chip.setAttribute('data-bs-toggle', 'tooltip');
          chip.setAttribute(
            'title',
            `Заявок: ${g.count}${
              currentStatuses.length === 1
                ? ', статус: ' +
                  (window.STATUS_LABELS_RU?.[
                    String(currentStatuses[0] || '').toUpperCase()
                  ] || currentStatuses[0])
                : ''
            }`
          );
          if (Number(g.count) >= 1) {
            chip.classList.add('op-chip-positive');
          } else {
            chip.classList.add('op-chip-zero');
          }
          chip.addEventListener('click', () => onGroupFilter(g));
          wrap.appendChild(chip);
        });
        qsa('[data-bs-toggle="tooltip"]', wrap).forEach(
          (el) => new bootstrap.Tooltip(el)
        );
      })
      .catch((e) => console.error('groups', e));
  }

  function onGroupFilter(group) {
    if (!currentObjectId) return;
    const modal = ensureRequestsModal();
    if (!modal) return;
    const title = qs('.modal-title', modal);
    if (title) title.textContent = `Заявки: ${group.name}`;
    resetRequestsList();
    window.ModalSystem && window.ModalSystem.show('requestsModal');
    const params = new URLSearchParams();
    params.set('manufacturer', group.id);
    params.set('limit', '200');
    currentStatuses.forEach((s) => params.append('status', s));
    if (currentSide) params.append('side', currentSide);
    const query = params.toString();
    const url = query
      ? `/api/op/${currentObjectId}/requests?${query}`
      : `/api/op/${currentObjectId}/requests`;
    fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        const items = Array.isArray(data)
          ? data
          : Array.isArray(data?.data)
            ? data.data
            : [];
        renderRequestsList(items);
      })
      .catch((err) => {
        if (!requestsListEl) return;
        requestsListEl.innerHTML = `<li class="list-group-item text-center text-danger">
          <i class="bi bi-exclamation-triangle me-1"></i>
          Ошибка загрузки заявок: ${err.message}
        </li>`;
      });
  }

  function initComments(objectId) {
    const form = qs('#op-comment-form');
    const list = qs('#op-comments');
    if (!form || !list) return;

    fetch(`/api/op/${objectId}/comments`)
      .then((r) => r.json())
      .then((data) => {
        list.innerHTML = '';
        (data || []).forEach((c) => {
          list.insertAdjacentHTML('beforeend', c.rendered_html);
        });
      });

    if (form.dataset.initialized === '1') return;
    form.dataset.initialized = '1';

    // Р вЂќР ВµР В»Р ВµР С–Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘Р Вµ РЎС“Р Т‘Р В°Р В»Р ВµР Р…Р С‘РЎРЏ Р С”Р С•Р СР СР ВµР Р…РЎвЂљР В°РЎР‚Р С‘Р ВµР Р†
    list.addEventListener('click', async (e) => {
      const btn = e.target.closest('.delete-comment-btn');
      if (!btn) return;
      const cid = btn.getAttribute('data-comment-id');
      if (!cid) return;
      if (typeof window.customConfirm === 'function') {
        const ok = await window.customConfirm('Удалить комментарий?');
        if (!ok) return;
      } else if (!window.confirm('Удалить комментарий?')) {
        return;
      }
      btn.disabled = true;
      try {
        const resp = await fetch(`/api/op/comments/${cid}`, {
          method: 'DELETE',
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || data.success !== true)
          throw new Error(data.error || 'Ошибка удаления');
        const card = btn.closest('.comment-card');
        if (card) card.remove();
      } catch (err) {
        console.error('comment-delete', err);
        btn.disabled = false;
      }
    });

    form.addEventListener('submit', (e) => {
      e.preventDefault();
      if (form.dataset.submitting === '1') return;
      form.dataset.submitting = '1';
      const ta = qs('#op-comment-text');
      const text = ((ta && ta.value) || '').trim();
      if (!text) return;
      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="bi bi-check2 me-1"></i>Сохранено!';
      }
      fetch(`/api/op/${objectId}/comments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: text }),
      })
        .then((r) => r.json())
        .then((data) => {
          if (data.rendered_html) {
            list.insertAdjacentHTML('afterbegin', data.rendered_html);
            if (ta) ta.value = '';
          }
        })
        .catch((e) => console.error('comment', e))
        .finally(() => {
          form.dataset.submitting = '0';
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="bi bi-check2 me-1"></i>Сохранено!';
            setTimeout(() => {
              submitBtn.textContent = 'Добавить комментарий';
            }, 1200);
          }
        });
    });
  }

  function initFiles(objectId) {
    const zone = qs('#op-files-dropzone');
    const list = qs('#op-files');
    const fileInput = qs('#op-file-input');
    if (!zone || !list) return;

    function uploadFiles(files) {
      Array.from(files || []).forEach((file) => {
        const fd = new FormData();
        fd.append('file', file);
        fetch(`/api/op/${objectId}/files`, { method: 'POST', body: fd })
          .then(refresh)
          .catch((err) => console.error('upload', err));
      });
    }

    function refresh() {
      fetch(`/api/op/${objectId}/files`)
        .then((r) => r.json())
        .then((data) => {
          list.innerHTML = '';
          (data || []).forEach((f) => {
            const row = document.createElement('div');
            row.className = 'mb-2';
            row.innerHTML = `<a href="/op/files/${f.id}/download" target="_blank">${f.original_name}</a>`;
            const del = document.createElement('button');
            del.className = 'btn btn-sm btn-danger ms-2';
            del.textContent = 'Удалить';
            del.addEventListener('click', () => {
              fetch(`/api/op/files/${f.id}`, { method: 'DELETE' }).then(
                refresh
              );
            });
            row.appendChild(del);
            list.appendChild(row);
          });
        });
    }

    zone.addEventListener('dragover', (e) => {
      e.preventDefault();
      zone.classList.add('drag');
    });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag'));
    zone.addEventListener('drop', (e) => {
      e.preventDefault();
      zone.classList.remove('drag');
      uploadFiles(e.dataTransfer.files);
    });
    zone.addEventListener('click', () => fileInput && fileInput.click());
    if (fileInput) {
      fileInput.addEventListener('change', () => {
        if (fileInput.files && fileInput.files.length) {
          uploadFiles(fileInput.files);
          fileInput.value = '';
        }
      });
    }

    refresh();
  }

  function validateCategoryName(input) {
    const val = (input.value || '').trim();
    const sideEl = input.closest('.kp-side');
    const others = qsa('input.kp-name', sideEl).filter((i) => i !== input);
    let error = '';
    if (!val) {
      error = 'Название категории обязательно';
    } else if (
      others.some(
        (i) => (i.value || '').trim().toLowerCase() === val.toLowerCase()
      )
    ) {
      error = 'Категория с таким названием уже есть';
    }
    if (error) {
      input.classList.add('is-invalid');
      if (typeof window.showToast === 'function') {
        window.showToast(error, 'error');
      }
      return false;
    }
    input.classList.remove('is-invalid');
    return true;
  }

  function initSortable(container) {
    if (!window.Sortable || !container) return;
    window.Sortable.create(container, {
      handle: '.kp-drag-handle',
      animation: 150,
      onEnd: () => {
        qsa('tr', container).forEach((tr, idx) => {
          const id = tr.dataset.catId;
          if (!id) return;
          fetch(`/api/op/kp/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ position: idx + 1 }),
          }).catch((e) => console.error('kp-order', e));
        });
      },
    });
  }

  function initKPCollapse() {
    ['OV', 'VK'].forEach((side) => {
      const el = qs(`#kp-collapse-${side}`);
      if (!el) return;
      const key = `kp-collapse-${side}`;
      const state = localStorage.getItem(key);
      if (state === '0') {
        new bootstrap.Collapse(el, { toggle: false }).hide();
      }
      el.addEventListener('shown.bs.collapse', () =>
        localStorage.setItem(key, '1')
      );
      el.addEventListener('hidden.bs.collapse', () =>
        localStorage.setItem(key, '0')
      );
    });
  }

  function initKP(objectId) {
    // Р С™Р Р…Р С•Р С—Р С”Р С‘ Р Т‘Р С•Р В±Р В°Р Р†Р В»Р ВµР Р…Р С‘РЎРЏ Р Т‘Р С•Р С—. Р С”Р В°РЎвЂљР ВµР С–Р С•РЎР‚Р С‘Р в„–
    qsa('.kp-add').forEach((btn) => {
      btn.onclick = () => {
        const side = btn.dataset.side;
        fetch(`/api/op/${objectId}/kp`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ side, name: 'Категория', is_extra: true }),
        }).then(() => initKP(objectId));
      };
    });

    // Р вЂ”Р В°Р С–РЎР‚РЎС“Р В·Р С”Р В° Р С”Р В°РЎвЂљР ВµР С–Р С•РЎР‚Р С‘Р в„– Р С‘ РЎР‚Р ВµР Р…Р Т‘Р ВµРЎР‚ Р Р† РЎРѓРЎвЂљРЎР‚Р С•Р С–Р С•Р в„– РЎвЂљР В°Р В±Р В»Р С‘РЎвЂ Р Вµ
    fetch(`/api/op/${objectId}/kp`)
      .then((r) => r.json())
      .then((cats) => {
        ['OV', 'VK'].forEach((side) => {
          const sideEl = qs(`.kp-side[data-side="${side}"]`);
          if (!sideEl) return;
          const rowsEl = sideEl.querySelector('.kp-rows');
          if (!rowsEl) return;
          rowsEl.innerHTML = '';

          cats
            .filter((c) => c.side === side)
            .forEach((cat) => {
              const tr = document.createElement('tr');
              tr.dataset.catId = cat.id;

              const tdName = document.createElement('td');
              tdName.classList.add('p-0');
              const name = document.createElement('input');
              name.className = 'form-control form-control-sm kp-name';
              name.value = cat.name;
              name.required = true;
              name.addEventListener('blur', () => validateCategoryName(name));
              tdName.appendChild(name);

              const tdInvoice = document.createElement('td');
              tdInvoice.classList.add('p-0');
              const invoice = document.createElement('input');
              invoice.className = 'form-control form-control-sm';
              invoice.placeholder = 'Счёт';
              invoice.value = cat.invoice_number || '';
              tdInvoice.appendChild(invoice);

              const tdActions = document.createElement('td');
              tdActions.className = 'text-center align-middle';
              const drag = document.createElement('span');
              drag.className = 'kp-drag-handle bi bi-grip-vertical me-2';
              tdActions.appendChild(drag);

              let timer;
              function save() {
                if (!validateCategoryName(name)) return;
                fetch(`/api/op/kp/${cat.id}`, {
                  method: 'PUT',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                    name: name.value,
                    invoice_number: invoice.value,
                  }),
                }).catch((e) => console.error('kp', e));
                updateDeleteVisibility();
              }

              [name, invoice].forEach((inp) => {
                inp.addEventListener('input', () => {
                  clearTimeout(timer);
                  timer = setTimeout(save, 500);
                  fitTextToInput(inp);
                });
                // Р СџР С•Р Т‘Р С–Р С•Р Р…РЎРЏР ВµР С РЎР‚Р В°Р В·Р СР ВµРЎР‚ Р С—РЎР‚Р С‘ Р С—Р С•РЎвЂљР ВµРЎР‚Р Вµ РЎвЂћР С•Р С”РЎС“РЎРѓР В° Р С‘ Р Р…Р В° РЎРѓРЎвЂљР В°РЎР‚РЎвЂљР Вµ
                inp.addEventListener('change', () => fitTextToInput(inp));
              });

              // Р С™Р Р…Р С•Р С—Р С”Р В° РЎС“Р Т‘Р В°Р В»Р ВµР Р…Р С‘РЎРЏ РЎвЂљР С•Р В»РЎРЉР С”Р С• Р Т‘Р В»РЎРЏ Р Т‘Р С•Р С—. Р С”Р В°РЎвЂљР ВµР С–Р С•РЎР‚Р С‘Р в„– Р С‘ РЎвЂљР С•Р В»РЎРЉР С”Р С• Р ВµРЎРѓР В»Р С‘ Р С—РЎС“РЎРѓРЎвЂљР С•
              let delBtn = null;
              function isEmpty() {
                const nm = (name.value || '').trim();
                const inv = (invoice.value || '').trim();
                const emptyName = nm === '' || nm.toLowerCase() === 'категория';
                return emptyName && inv === '';
              }
              function updateDeleteVisibility() {
                if (!delBtn) return;
                if (isEmpty()) {
                  delBtn.classList.remove('d-none');
                } else {
                  delBtn.classList.add('d-none');
                }
              }

              if (cat.is_extra) {
                delBtn = document.createElement('button');
                delBtn.type = 'button';
                delBtn.className = 'btn-close kp-del d-none';
                delBtn.title = 'Удалить пустую строку';
                delBtn.addEventListener('click', () => {
                  if (!isEmpty()) return; // Safety
                  fetch(`/api/op/kp/${cat.id}`, { method: 'DELETE' })
                    .then(() => initKP(objectId))
                    .catch((e) => console.error('kp-del', e));
                });
                tdActions.appendChild(delBtn);
                // Р ВР В·Р Р…Р В°РЎвЂЎР В°Р В»РЎРЉР Р…Р С•Р Вµ РЎРѓР С•РЎРѓРЎвЂљР С•РЎРЏР Р…Р С‘Р Вµ
                updateDeleteVisibility();
              }

              tr.appendChild(tdName);
              tr.appendChild(tdInvoice);
              tr.appendChild(tdActions);
              rowsEl.appendChild(tr);

              // Р СџР С•РЎРѓР В»Р Вµ Р Р†РЎРѓРЎвЂљР В°Р Р†Р С”Р С‘ Р Р† DOM Р С—Р С•Р Т‘Р С–Р С•Р Р…РЎРЏР ВµР С РЎР‚Р В°Р В·Р СР ВµРЎР‚РЎвЂ№
              requestAnimationFrame(() => {
                fitTextToInput(name);
                fitTextToInput(invoice);
              });
            });
          initSortable(rowsEl);
        });
      })
      .catch((e) => console.error('kp', e));
  }

  // Р В Р ВµРЎРѓР В°Р в„–Р В· РІР‚вЂќ Р С—Р ВµРЎР‚Р ВµРЎРѓРЎвЂЎР С‘РЎвЂљР В°РЎвЂљРЎРЉ Р Р†РЎРѓР Вµ Р Р†Р С‘Р Т‘Р С‘Р СРЎвЂ№Р Вµ Р С‘Р Р…Р С—РЎС“РЎвЂљРЎвЂ№ Р Р† Р С™Р Сџ
  window.addEventListener('resize', () => {
    qsa('.kp-table input.form-control.form-control-sm').forEach((inp) =>
      fitTextToInput(inp)
    );
  });

  document.addEventListener('DOMContentLoaded', () => {
    const root = qs('#op-root');
    if (!root) return;
    viewRequestUrlTemplate = root.dataset.viewRequestUrlTemplate || '';
    ensureRequestsModal();
    initKPCollapse();
    const searchInput = qs('#op-search');
    let suggestBox = qs('#op-suggest-list') || qs('#suggestions');
    const selectBtn = qs('#op-select-btn');
    const searchUrl = root.dataset.searchUrl;
    let currentPage = 1;
    let currentQuery = '';

    function getSuggestBox() {
      if (suggestBox && suggestBox instanceof HTMLElement) return suggestBox;
      // Р СџР С•Р Т‘Р Т‘Р ВµРЎР‚Р В¶Р С”Р В° legacy-Р С‘Р Т‘Р ВµР Р…РЎвЂљР С‘РЎвЂћР С‘Р С”Р В°РЎвЂљР С•РЎР‚Р В° Р С‘ Р В°Р Р†РЎвЂљР С•РЎРѓР С•Р В·Р Т‘Р В°Р Р…Р С‘Р Вµ Р С”Р С•Р Р…РЎвЂљР ВµР в„–Р Р…Р ВµРЎР‚Р В°
      suggestBox = qs('#op-suggest-list') || qs('#suggestions');
      if (suggestBox && suggestBox instanceof HTMLElement) return suggestBox;
      const host =
        qs('#op-search-container .card-body') || qs('#op-search-container');
      if (!host) return null;
      const box = document.createElement('div');
      box.id = 'op-suggest-list';
      box.className = 'op-suggest-list';
      host.appendChild(box);
      suggestBox = box;
      return suggestBox;
    }

    function startForObject(id, name, address) {
      currentObjectId = id;
      hideSearchWithAnimation(() => {
        showContent();
        renderObjectCard(name, address);
        loadGroupTags(id);
        initComments(id);
        initFiles(id);
        initKP(id);
      });
    }

    function renderSuggestions(items, append = false, hasMore = false) {
      const box = getSuggestBox();
      if (!box) return;
      if (!append) box.innerHTML = '';
      box.classList.toggle('visible', (items && items.length > 0) || hasMore);
      (items || []).forEach((it) => {
        const el = document.createElement('div');
        el.className = 'op-suggest-item';
        el.dataset.id = it.id;
        el.innerHTML = `
          <div class="title">${it.name}</div>
          ${
            it.address
              ? `<div class="subtitle text-muted">${it.address}</div>`
              : ''
          }
        `;
        el.addEventListener('click', () => {
          selected = {
            id: String(it.id),
            name: it.name,
            address: it.address || '',
          };
          if (searchInput) searchInput.value = it.name;
          const b = getSuggestBox();
          if (b) {
            b.innerHTML = '';
            b.classList.remove('visible');
          }
        });
        box.appendChild(el);
      });
      if (hasMore) {
        const more = document.createElement('div');
        more.className = 'op-suggest-more';
        more.textContent = 'Показать ещё';
        more.addEventListener('click', () => {
          currentPage += 1;
          fetchSuggestions(true);
        });
        box.appendChild(more);
      }
    }

    function fetchSuggestions(append = false) {
      fetch(
        `${searchUrl}?query=${encodeURIComponent(
          currentQuery
        )}&page=${currentPage}`
      )
        .then((r) => r.json())
        .then((data) => {
          const items = Array.isArray(data) ? data : data.items;
          const hasMore = Array.isArray(data) ? false : data.has_next;
          renderSuggestions(items, append, hasMore);
        })
        .catch(() => renderSuggestions([], false, false));
    }

    if (searchInput) {
      const debounced = debounce(() => {
        selected = { id: null, name: '', address: '' };
        const q = searchInput.value.trim();
        if (q.length < 2) {
          renderSuggestions([], false, false);
          return;
        }
        currentQuery = q;
        currentPage = 1;
        fetchSuggestions(false);
      }, 300);
      searchInput.addEventListener('input', debounced);

      searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          if (selected.id)
            startForObject(selected.id, selected.name, selected.address);
        }
      });
    }

    if (selectBtn) {
      selectBtn.addEventListener('click', () => {
        if (selected.id)
          startForObject(selected.id, selected.name, selected.address);
      });
    }

    document.addEventListener('click', (e) => {
      const box = getSuggestBox();
      if (!box) return;
      if (!box.contains(e.target) && e.target !== searchInput) {
        box.classList.remove('visible');
      }
    });

    const preloadId = root.dataset.objectId;
    if (preloadId) {
      const preloadName = root.dataset.objectName || '';
      startForObject(preloadId, preloadName, '');
    }
  });
})();
