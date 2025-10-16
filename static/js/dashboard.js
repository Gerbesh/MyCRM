'use strict';

(function () {
  function isMobile() {
    return window.innerWidth <= 768;
  }

  function setDefaultView(tableView, cardsView, buttons, cardBtn, tableBtn) {
    if (isMobile()) {
      tableView.classList.add('d-none');
      cardsView.classList.remove('d-none');
      buttons.forEach((b) => b.classList.remove('active'));
      if (cardBtn) cardBtn.classList.add('active');
    } else {
      cardsView.classList.add('d-none');
      tableView.classList.remove('d-none');
      buttons.forEach((b) => b.classList.remove('active'));
      if (tableBtn) tableBtn.classList.add('active');
    }
  }

  function applyCurrentFilters() {
    const searchInput = document.getElementById('searchInput');
    const myRequestsCheckbox = document.getElementById('myRequestsOnly');
    const perPageSelect = document.getElementById('perPageSelect');
    const currentUrl = new URL(window.location);
    const searchValue = searchInput ? searchInput.value.trim() : '';
    const myRequestsValue = myRequestsCheckbox
      ? myRequestsCheckbox.checked
      : false;
    const perPageValue = perPageSelect ? perPageSelect.value : '';
    if (searchValue) currentUrl.searchParams.set('search', searchValue);
    else currentUrl.searchParams.delete('search');
    if (myRequestsValue) currentUrl.searchParams.set('my_requests', 'true');
    else currentUrl.searchParams.delete('my_requests');
    if (perPageValue) currentUrl.searchParams.set('per_page', perPageValue);
    else currentUrl.searchParams.delete('per_page');
    currentUrl.searchParams.delete('page');
    window.location.href = currentUrl.toString();
  }

  document.addEventListener('DOMContentLoaded', () => {
    const tableView = document.getElementById('requests-table');
    const cardsView = document.getElementById('requests-cards');
    const buttons = document.querySelectorAll('[data-view]');
    const cardBtn = document.querySelector('[data-view="cards"]');
    const tableBtn = document.querySelector('[data-view="table"]');

    if (tableView && cardsView && buttons.length) {
      setDefaultView(tableView, cardsView, buttons, cardBtn, tableBtn);
      buttons.forEach((btn) => {
        btn.addEventListener('click', () => {
          if (btn.getAttribute('data-view') === 'cards') {
            tableView.classList.add('d-none');
            cardsView.classList.remove('d-none');
          } else {
            cardsView.classList.add('d-none');
            tableView.classList.remove('d-none');
          }
          buttons.forEach((b) => b.classList.remove('active'));
          btn.classList.add('active');
        });
      });
      window.addEventListener('resize', () => {
        clearTimeout(window.__resizeTimer);
        window.__resizeTimer = setTimeout(
          () =>
            setDefaultView(tableView, cardsView, buttons, cardBtn, tableBtn),
          250
        );
      });
    }

    const searchInput = document.getElementById('searchInput');
    const clearSearchBtn = document.getElementById('clearSearch');
    const applyFiltersBtn = document.getElementById('applyFilters');
    const perPageSelect = document.getElementById('perPageSelect');
    if (clearSearchBtn && searchInput)
      clearSearchBtn.addEventListener('click', () => {
        searchInput.value = '';
        applyCurrentFilters();
      });
    if (searchInput)
      searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          applyCurrentFilters();
        }
      });
    if (applyFiltersBtn)
      applyFiltersBtn.addEventListener('click', applyCurrentFilters);
    if (perPageSelect)
      perPageSelect.addEventListener('change', applyCurrentFilters);
  });

  // Глобально доступная функция удаления
  window.confirmDelete = async function confirmDelete(requestId) {
    if (typeof window.customConfirm === 'function') {
      if (
        !(await window.customConfirm(
          'Вы уверены, что хотите удалить эту заявку?'
        ))
      )
        return;
    } else if (!window.confirm('Удалить заявку?')) {
      return;
    }
    const form = document.getElementById('deleteForm');
    if (!form) return;
    const base = form.getAttribute('data-delete-url-template');
    if (!base) return;
    form.action = base.replace('0', String(requestId));
    form.submit();
  };
})();
