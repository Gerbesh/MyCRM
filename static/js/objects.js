'use strict';

(function () {
  function qs(selector, root = document) {
    return root.querySelector(selector);
  }
  function qsa(selector, root = document) {
    return Array.from(root.querySelectorAll(selector));
  }

  document.addEventListener('DOMContentLoaded', () => {
    const root = qs('.container.mt-4') || document.body;
    const viewUrlTemplate =
      root.getAttribute('data-view-request-url-template') || '';
    const isAdmin = (root.getAttribute('data-is-admin') || 'false') === 'true';
    const addObjectUrl = root.getAttribute('data-add-object-url') || '';
    const editUrlTemplate =
      root.getAttribute('data-edit-object-url-template') || '';
    const deleteUrlTemplate =
      root.getAttribute('data-delete-object-url-template') || '';

    const tableView = qs('#objects-table');
    const cardsView = qs('#objects-cards');
    const tableSkeleton = qs('#objects-table-skeleton');
    const cardsSkeleton = qs('#objects-cards-skeleton');

    if (tableSkeleton && tableView) {
      setTimeout(() => {
        tableSkeleton.classList.add('d-none');
        tableView.classList.remove('d-none');
      }, 300);
    }
    const buttons = qsa('[data-view]');
    if (tableView && cardsView && buttons.length) {
      buttons.forEach((btn) => {
        btn.addEventListener('click', () => {
          const currentViewSpan = qs('#current-view');
          if (btn.getAttribute('data-view') === 'cards') {
            tableView.classList.add('d-none');
            cardsView.classList.add('d-none');
            if (currentViewSpan) currentViewSpan.textContent = 'Карточки';
            if (cardsSkeleton) {
              cardsSkeleton.classList.remove('d-none');
              setTimeout(() => {
                cardsSkeleton.classList.add('d-none');
                cardsView.classList.remove('d-none');
              }, 300);
            } else {
              cardsView.classList.remove('d-none');
            }
          } else {
            cardsView.classList.add('d-none');
            tableView.classList.add('d-none');
            if (currentViewSpan) currentViewSpan.textContent = 'Таблица';
            if (tableSkeleton) {
              tableSkeleton.classList.remove('d-none');
              setTimeout(() => {
                tableSkeleton.classList.add('d-none');
                tableView.classList.remove('d-none');
              }, 300);
            } else {
              tableView.classList.remove('d-none');
            }
          }
          buttons.forEach((b) => b.classList.remove('active'));
          btn.classList.add('active');
        });
      });
    }

    const modal = qs('#requestsModal');
    if (modal) {
      modal.addEventListener('show.bs.modal', function (event) {
        const button = event.relatedTarget;
        const objectId = button.getAttribute('data-object-id');
        const name = button.getAttribute('data-object-name');
        const list = qs('#requests-list');
        if (list)
          list.innerHTML =
            '<li class="list-group-item text-center text-muted">Загрузка...</li>';
        const title = modal.querySelector('.modal-title');
        if (title) title.textContent = `Заявки: ${name}`;

        fetch(`/api/v1/requests/by_object/${objectId}`)
          .then((response) => {
            if (!response.ok) {
              if (response.status === 404)
                throw new Error('API endpoint not found');
              if (response.status === 500) throw new Error('Server error');
              throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
          })
          .then((data) => {
            if (!list) return;
            list.innerHTML = '';
            data = Array.isArray(data)
              ? data
              : data && Array.isArray(data.data)
                ? data.data
                : [];
            if (!data || data.length === 0) {
              list.innerHTML =
                '<li class="list-group-item text-center text-muted">Нет заявок</li>';
              return;
            }
            data.forEach((req) => {
              const code = String(req.status || '').toUpperCase();
              const statusClass = code === 'DONE' ? 'bg-success' : 'bg-warning';
              const date = new Date(req.created_at).toLocaleDateString('ru-RU');
              const contractorsHtml = (req.contractors || [])
                .map(
                  (c) =>
                    `<span class=\"badge bg-primary me-1\">${c.name}</span>`
                )
                .join('');
              const manufacturersHtml = (req.manufacturers || [])
                .map((m) => `<span class=\"badge bg-info me-1\">${m}</span>`)
                .join('');
              const item = document.createElement('li');
              item.className = 'list-group-item';
              item.innerHTML = `
                <div class="d-flex justify-content-between mb-2">
                  <strong>Заявка #${req.id}</strong>
                  <span class="badge ${statusClass}">${
                    window.STATUS_LABELS_RU?.[code] || req.status
                  }</span>
                </div>
                <div class="mb-1"><small><strong>Подрядчики:</strong></small><br>${contractorsHtml}</div>
                <div class="mb-1"><small><strong>Производители:</strong></small><br>${manufacturersHtml}</div>
                <div class="text-muted small">от ${date}</div>
                <div class="text-end mt-2">
                  <a href="${viewUrlTemplate.replace(
                    '0',
                    String(req.id)
                  )}" class="btn btn-sm btn-outline-primary">Открыть</a>
                </div>`;
              list.appendChild(item);
            });
          })
          .catch((err) => {
            console.error('Error loading requests:', err);
            if (!list) return;
            list.innerHTML = `<li class="list-group-item text-center text-danger">
              <i class="bi bi-exclamation-triangle me-1"></i>
              Ошибка загрузки заявок: ${err.message}<br>
              <small class="text-muted">Попробуйте обновить страницу</small>
            </li>`;
          });
      });

      window.ModalSystem && window.ModalSystem.init(modal);

      modal.addEventListener('hidden.bs.modal', function () {
        const list = qs('#requests-list');
        if (list)
          list.innerHTML =
            '<li class="list-group-item text-center text-muted">Загрузка...</li>';
        qsa('.modal-backdrop').forEach((b) => b.remove());
        document.body.classList.remove('modal-open');
        document.body.style.overflow = '';
        document.body.style.paddingRight = '';
      });

      const closeBtn = modal.querySelector('[data-bs-dismiss="modal"]');
      if (closeBtn) {
        closeBtn.addEventListener('click', function () {
          window.ModalSystem && window.ModalSystem.hide('requestsModal');
          setTimeout(
            () => window.cleanupModalBackdrop && window.cleanupModalBackdrop(),
            200
          );
        });
      }

      modal.addEventListener('click', function (event) {
        if (event.target === modal)
          window.ModalSystem && window.ModalSystem.hide('requestsModal');
      });
    }

    // Добавление объекта (упрощённо — только имя)
    const addObjectBtn = qs('#add-object-btn');
    const addObjectModalEl = qs('#addObjectModal');
    const addObjectForm = qs('#add-object-form');
    const objectNameInput = qs('#object-name');
    const objectNameError = qs('#object-name-error');
    if (
      addObjectBtn &&
      addObjectModalEl &&
      addObjectForm &&
      objectNameInput &&
      objectNameError
    ) {
      // eslint-disable-next-line no-undef
      const addObjectModal = new bootstrap.Modal(addObjectModalEl);
      addObjectBtn.addEventListener('click', function (e) {
        e.preventDefault();
        addObjectForm.reset();
        objectNameInput.classList.remove('is-invalid');
        objectNameError.textContent = '';
        addObjectModal.show();
      });
      addObjectForm.addEventListener('submit', function (e) {
        e.preventDefault();
        const name = objectNameInput.value.trim();
        if (!name) {
          objectNameInput.classList.add('is-invalid');
          objectNameError.textContent = 'Название обязательно';
          return;
        }
        const formData = new FormData();
        formData.append('name', name);
        formData.append(
          'csrf_token',
          window.getCSRFToken ? window.getCSRFToken() : ''
        );
        fetch(addObjectUrl || '/object/add', { method: 'POST', body: formData })
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
            if (data.error) {
              objectNameInput.classList.add('is-invalid');
              objectNameError.textContent = data.error;
            } else {
              addObjectModal.hide();
              appendObjectRow(data, {
                isAdmin,
                editUrlTemplate,
                deleteUrlTemplate,
              });
            }
          })
          .catch((error) => {
            console.error('Ошибка:', error);
            objectNameInput.classList.add('is-invalid');
            objectNameError.textContent = 'Сервер недоступен';
          });
      });
    }

    // Кликабельные названия существующих объектов
    qsa('#objects-table tbody tr').forEach((row) => {
      const nameCell = row.cells[0];
      const linkCell = row.querySelector('[data-url]');
      if (nameCell && linkCell) {
        nameCell.style.cursor = 'pointer';
        nameCell.addEventListener('click', () => {
          const url = linkCell.getAttribute('data-url');
          if (url) window.location.href = url;
        });
      }
    });

    function appendObjectRow(data, ctx) {
      const { isAdmin, editUrlTemplate, deleteUrlTemplate } = ctx;
      const countEl = qs('#objects-count');
      if (countEl)
        countEl.textContent = String(parseInt(countEl.textContent, 10) + 1);

      const tableBody = qs('#objects-table tbody');
      if (tableBody) {
        const row = document.createElement('tr');
        let adminActions = '';
        if (isAdmin) {
          const editUrl = editUrlTemplate.replace('0', data.id);
          const deleteUrl = deleteUrlTemplate.replace('0', data.id);
          adminActions = `<a href="${editUrl}" class="btn btn-sm btn-primary">Редактировать</a>
            <form method="POST" action="${deleteUrl}" style="display:inline;">
              <input type="hidden" name="csrf_token" value="${
                window.getCSRFToken ? window.getCSRFToken() : ''
              }"/>
              <button type="submit" class="btn btn-sm btn-danger" data-confirm="Вы уверены, что хотите удалить объект? Это действие нельзя отменить.">Удалить</button>
            </form>`;
        }
        const viewUrl = viewUrlTemplate
          ? viewUrlTemplate.replace('0', data.id)
          : '';
        row.innerHTML =
          `<td>${data.name}</td><td data-url="${viewUrl}">—</td><td>—</td><td>—</td>
          <td><button class="btn btn-sm btn-info" data-bs-toggle="modal" data-bs-target="#requestsModal" data-object-id="${data.id}" data-object-name="${data.name}">Заявок: 0</button></td>` +
          (isAdmin ? `<td>${adminActions}</td>` : '');
        tableBody.prepend(row);
        const nameCell = row.querySelector('td');
        const linkCell = row.querySelector('[data-url]');
        if (nameCell && linkCell) {
          nameCell.style.cursor = 'pointer';
          nameCell.addEventListener('click', () => {
            const url = linkCell.getAttribute('data-url');
            if (url) window.location.href = url;
          });
        }
      }

      const cards = qs('#objects-cards');
      if (cards) {
        const card = document.createElement('div');
        card.className = 'card mb-3';
        let adminBlock = '';
        if (isAdmin) {
          const editUrl = editUrlTemplate.replace('0', data.id);
          const deleteUrl = deleteUrlTemplate.replace('0', data.id);
          adminBlock = `<div class="d-flex gap-2">
              <a href="${editUrl}" class="btn btn-sm btn-primary">Редактировать</a>
              <form method="POST" action="${deleteUrl}" style="display:inline;">
                <input type="hidden" name="csrf_token" value="${
                  window.getCSRFToken ? window.getCSRFToken() : ''
                }"/>
                <button type="submit" class="btn btn-sm btn-danger" data-confirm="Удалить?">Удалить</button>
              </form>
            </div>`;
        }
        card.innerHTML = `<div class="card-body">
            <h5 class="card-title">${data.name}</h5>
            <p><strong>Заявки:</strong> <button class="btn btn-sm btn-info" data-bs-toggle="modal" data-bs-target="#requestsModal" data-object-id="${
              data.id
            }" data-object-name="${data.name}">0</button></p>
            ${isAdmin ? adminBlock : ''}
          </div>`;
        cards.prepend(card);
      }
    }
  });
})();
