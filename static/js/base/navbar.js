'use strict';

// Немедленное исправление z-index для navbar и отладочные функции
(function () {
  // Immediate fix to avoid overlap issues during early load
  const navbar = document.querySelector('.navbar');
  if (navbar) {
    try {
      navbar.style.setProperty('z-index', '1031', 'important');
      navbar.style.setProperty('position', 'relative', 'important');

      function keepNavbarZIndex() {
        if (!navbar) return;
        const currentZ = window.getComputedStyle(navbar).zIndex;
        if (currentZ !== '1031' && currentZ !== 'auto') {
          navbar.style.setProperty('z-index', '1031', 'important');
          navbar.style.setProperty('position', 'relative', 'important');
        }
      }
      setInterval(keepNavbarZIndex, 100);

      document.addEventListener('show.bs.modal', function () {
        keepNavbarZIndex();
      });
    } catch (e) {
      // noop
    }
  }

  // Debug helpers
  window.debugZIndex = function () {
    console.log('=== Отладка Z-Index иерархии ===');
    const navbar = document.querySelector('.navbar');
    const modals = document.querySelectorAll('.modal');
    const backdrops = document.querySelectorAll('.modal-backdrop');
    if (navbar) {
      const navbarZ = window.getComputedStyle(navbar).zIndex;
      const navbarPos = window.getComputedStyle(navbar).position;
      console.log(`Navbar: z-index=${navbarZ}, position=${navbarPos}`);
    }
    modals.forEach((modal, i) => {
      const modalZ = window.getComputedStyle(modal).zIndex;
      const modalPos = window.getComputedStyle(modal).position;
      const isVisible = modal.classList.contains('show');
      console.log(
        `Modal ${i} (${modal.id}): z-index=${modalZ}, position=${modalPos}, visible=${isVisible}`
      );
      const dialog = modal.querySelector('.modal-dialog');
      const content = modal.querySelector('.modal-content');
      if (dialog)
        console.log(
          `  - Dialog: z-index=${window.getComputedStyle(dialog).zIndex}`
        );
      if (content)
        console.log(
          `  - Content: z-index=${window.getComputedStyle(content).zIndex}`
        );
    });
    backdrops.forEach((backdrop, i) => {
      console.log(
        `Backdrop ${i}: z-index=${window.getComputedStyle(backdrop).zIndex}`
      );
    });
    console.log('=== Конец отладки ===');
  };

  window.fixZIndex = function () {
    const navbar = document.querySelector('.navbar');
    if (navbar) {
      navbar.style.setProperty('z-index', '1031', 'important');
      navbar.style.setProperty('position', 'relative', 'important');
    }
    const modals = document.querySelectorAll('.modal');
    modals.forEach((modal) => {
      modal.style.setProperty('z-index', '1055', 'important');
      const dialog = modal.querySelector('.modal-dialog');
      const content = modal.querySelector('.modal-content');
      if (dialog) dialog.style.setProperty('z-index', '1056', 'important');
      if (content) content.style.setProperty('z-index', '1057', 'important');
    });
    const backdrops = document.querySelectorAll('.modal-backdrop');
    backdrops.forEach((backdrop) => {
      backdrop.style.setProperty('z-index', '1050', 'important');
    });
    console.log('справление завершено!');
  };

  window.visualDebug = function () {
    const navbar = document.querySelector('.navbar');
    const modals = document.querySelectorAll('.modal');
    if (navbar) navbar.setAttribute('data-debug', 'true');
    modals.forEach((modal) => modal.setAttribute('data-debug', 'true'));
    console.log(
      'Визуальная отладка включена (синяя рамка = navbar, красная = modal)'
    );
  };

  // Enforce correct z-index and monitor changes
  window.enforceNavbarZIndex = function () {
    const navbar = document.querySelector('.navbar');
    if (!navbar) return;
    navbar.style.setProperty('z-index', '1031', 'important');
    navbar.style.setProperty('position', 'relative', 'important');
    const observer = new MutationObserver(function (mutations) {
      mutations.forEach(function (mutation) {
        if (
          mutation.type === 'attributes' &&
          (mutation.attributeName === 'style' ||
            mutation.attributeName === 'class')
        ) {
          const currentZIndex = window.getComputedStyle(navbar).zIndex;
          if (currentZIndex !== '1031' && currentZIndex !== 'auto') {
            navbar.style.setProperty('z-index', '1031', 'important');
            navbar.style.setProperty('position', 'relative', 'important');
          }
        }
      });
    });
    observer.observe(navbar, {
      attributes: true,
      attributeFilter: ['style', 'class'],
    });
    setInterval(() => {
      const currentZIndex = window.getComputedStyle(navbar).zIndex;
      if (currentZIndex !== '1031' && currentZIndex !== 'auto') {
        navbar.style.setProperty('z-index', '1031', 'important');
        navbar.style.setProperty('position', 'relative', 'important');
      }
    }, 1000);
  };

  document.addEventListener('DOMContentLoaded', function () {
    if (typeof window.enforceNavbarZIndex === 'function')
      window.enforceNavbarZIndex();
  });
})();
