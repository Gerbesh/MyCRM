'use strict';

// Глобальная система управления модальными окнами (Bootstrap 5)
(function () {
  let modalInstances = new Map();
  let isInitialized = false;

  function cleanupOrphanedBackdrops() {
    const activeModals = document.querySelectorAll('.modal.show');
    const allBackdrops = document.querySelectorAll('.modal-backdrop');

    if (activeModals.length === 0) {
      allBackdrops.forEach(
        (backdrop) =>
          backdrop.parentNode && backdrop.parentNode.removeChild(backdrop)
      );
      document.body.classList.remove('modal-open');
      document.body.style.overflow = '';
      document.body.style.paddingRight = '';
    } else if (allBackdrops.length > 1) {
      for (let i = 1; i < allBackdrops.length; i++) {
        if (allBackdrops[i] && allBackdrops[i].parentNode) {
          allBackdrops[i].parentNode.removeChild(allBackdrops[i]);
        }
      }
    }
  }

  function setupGlobalHandlers() {
    document.addEventListener('hidden.bs.modal', function () {
      setTimeout(cleanupOrphanedBackdrops, 100);
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        const openModals = document.querySelectorAll('.modal.show');
        openModals.forEach((modal) => {
          const modalId = modal.id;
          if (modalId && modalInstances.has(modalId)) {
            modalInstances.get(modalId).hide();
          }
        });
      }
    });

    document.addEventListener('show.bs.modal', function () {
      setTimeout(cleanupOrphanedBackdrops, 50);
    });
  }

  function setupMutationObserver() {
    if (!window.MutationObserver) return;
    const observer = new MutationObserver(function (mutations) {
      let needsCleanup = false;
      mutations.forEach(function (mutation) {
        mutation.addedNodes.forEach(function (node) {
          if (
            node.nodeType === 1 &&
            node.className &&
            String(node.className).includes('modal-backdrop')
          ) {
            needsCleanup = true;
          }
        });
      });
      if (needsCleanup) setTimeout(cleanupOrphanedBackdrops, 100);
    });
    observer.observe(document.body, { childList: true, subtree: false });
  }

  function initModalSystem() {
    if (isInitialized) return;
    isInitialized = true;
    cleanupOrphanedBackdrops();
    setupGlobalHandlers();
    setupMutationObserver();
  }

  function getBootstrapModalInstance(modalEl, options = {}) {
    // eslint-disable-next-line no-undef
    return new bootstrap.Modal(modalEl, {
      backdrop: 'static',
      keyboard: true,
      focus: true,
      ...options,
    });
  }

  window.ModalSystem = {
    init: function (modalElement, options = {}) {
      if (!modalElement) return null;
      const modalId =
        modalElement.id || Math.random().toString(36).substr(2, 9);
      const modalInstance = getBootstrapModalInstance(modalElement, options);
      modalInstances.set(modalId, modalInstance);

      modalElement.addEventListener('shown.bs.modal', function () {
        setTimeout(cleanupOrphanedBackdrops, 50);
      });
      modalElement.addEventListener('hidden.bs.modal', function () {
        setTimeout(cleanupOrphanedBackdrops, 100);
      });
      return modalInstance;
    },
    show: function (modalId, options = {}) {
      const modalElement = document.getElementById(modalId);
      if (!modalElement) {
        console.error('Модальное окно не найдено:', modalId);
        return null;
      }
      const modalInstance = this.init(modalElement, options);
      if (modalInstance) modalInstance.show();
      return modalInstance;
    },
    hide: function (modalId) {
      const modalInstance = modalInstances.get(modalId);
      if (modalInstance) {
        modalInstance.hide();
      } else {
        const modalElement = document.getElementById(modalId);
        if (modalElement) {
          modalElement.classList.remove('show');
          modalElement.style.display = 'none';
          modalElement.setAttribute('aria-hidden', 'true');
          modalElement.removeAttribute('aria-modal');
          modalElement.removeAttribute('role');
          cleanupOrphanedBackdrops();
        }
      }
    },
    cleanup: cleanupOrphanedBackdrops,
  };

  window.showModal = window.ModalSystem.show;
  window.hideModal = window.ModalSystem.hide;
  window.initModal = window.ModalSystem.init;
  window.cleanupModalBackdrop = window.ModalSystem.cleanup;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initModalSystem);
  } else {
    initModalSystem();
  }
})();
