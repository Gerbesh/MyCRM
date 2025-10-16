'use strict';

// Общие UI-скрипты: лоадер, анимации, переходы, всплывающие уведомления
(function () {
  // Плавный глобальный loader
  function showPageLoader() {
    const loader = document.getElementById('pageLoader');
    if (!loader) return;

    const prefersReducedMotion = window.matchMedia(
      '(prefers-reduced-motion: reduce)'
    ).matches;

    loader.classList.remove('fade-out');
    loader.classList.add('visible');

    // Настраиваем z-index навбара
    const navbar = document.querySelector('.navbar');
    if (navbar) {
      navbar.style.zIndex = '1031';
      navbar.style.position = 'relative';
    }

    const existing = document.getElementById('global-progress-bar');
    if (existing) existing.remove();
    const progressBar = document.createElement('div');
    progressBar.id = 'global-progress-bar';
    progressBar.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 0%;
      height: 2px;
      background: linear-gradient(90deg, var(--color-primary), var(--color-accent));
      z-index: 10001;
      box-shadow: 0 0 10px rgba(var(--color-primary-light-rgb), 0.5);
    `;
    document.body.appendChild(progressBar);

    if (prefersReducedMotion) {
      progressBar.style.width = '100%';
      return;
    }

    const duration = 5000;
    let start;
    function step(timestamp) {
      if (!start) start = timestamp;
      const progress = Math.min(((timestamp - start) / duration) * 90, 90);
      progressBar.style.width = progress + '%';
      if (progress < 90) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);

    setTimeout(() => {
      progressBar.style.width = '100%';
      setTimeout(() => progressBar.remove(), 300);
    }, duration);
  }

  function showToast(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;
    toast.innerHTML = `
      <div class="toast-content">
        <i class="bi bi-${
          type === 'success'
            ? 'check-circle'
            : type === 'error'
              ? 'exclamation-triangle'
              : type === 'warning'
                ? 'exclamation-circle'
                : 'info-circle'
        }"></i>
        <span>${message}</span>
      </div>
      <button class="toast-close" onclick="this.parentElement.remove()">
        <i class="bi bi-x"></i>
      </button>
    `;
    toast.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      z-index: 1080;
      max-width: 350px;
      background: var(--bs-card-bg);
      color: var(--gray-800);
      border-radius: 12px;
      box-shadow: var(--shadow-lg);
      padding: 1rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      transform: translateX(100%);
      transition: transform var(--transition-normal);
      margin-bottom: 10px;
    `;
    document.body.appendChild(toast);
    setTimeout(() => (toast.style.transform = 'translateX(0)'), 100);
    setTimeout(() => {
      toast.style.transform = 'translateX(100%)';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  function setupFormLoadingStates() {
    const forms = document.querySelectorAll('form');
    forms.forEach((form) => {
      form.addEventListener('submit', function () {
        const submitBtn = form.querySelector(
          'button[type="submit"], input[type="submit"]'
        );
        if (submitBtn && !submitBtn.disabled) {
          const originalText = submitBtn.innerHTML;
          submitBtn.disabled = true;
          submitBtn.innerHTML =
            '<i class="bi bi-spinner bi-spin me-2"></i>Обработка...';
          setTimeout(() => {
            if (submitBtn.disabled) {
              submitBtn.disabled = false;
              submitBtn.innerHTML = originalText;
            }
          }, 30000);
        }
      });
    });
  }

  function setupPageTransitions() {
    const navLinks = document.querySelectorAll(
      'a[href]:not([href^="#"]):not([href^="javascript:"]):not([target="_blank"])'
    );
    navLinks.forEach((link) => {
      link.addEventListener('click', function (e) {
        if (link.href && link.href !== window.location.href) {
          if (
            !link.hasAttribute('data-bs-toggle') &&
            !link.hasAttribute('onclick') &&
            !link.hasAttribute('download')
          ) {
            e.preventDefault();
            showPageLoader();
            setTimeout(() => {
              window.location.href = link.href;
            }, 150);
          }
        }
      });
    });
  }

  function animateOnView() {
    const elements = document.querySelectorAll(
      '.fade-in, .slide-up, .slide-down, .slide-left, .slide-right, .zoom-in'
    );
    if (!elements.length) {
      return;
    }

    // На старых браузерах (или при сбое наблюдателя) сразу показываем элементы
    if (!('IntersectionObserver' in window)) {
      elements.forEach((el) => el.classList.add('animated'));
      return;
    }

    const observer = new IntersectionObserver(
      (entries, obs) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('animated');
            obs.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1 }
    );

    elements.forEach((el) => observer.observe(el));

    // Страховка для мобильных: если анимация не запустилась, делаем это вручную
    setTimeout(() => {
      elements.forEach((el) => {
        if (!el.classList.contains('animated')) {
          el.classList.add('animated');
        }
      });
    }, 1200);
  }

  function animateCounter(element, start, end, duration = 2000) {
    let current = start;
    const increment = (end - start) / (duration / 16);
    const timer = setInterval(() => {
      current += increment;
      element.textContent = Math.floor(current);
      if (current >= end) {
        element.textContent = end;
        clearInterval(timer);
      }
    }, 16);
  }

  function initCounters() {
    const counters = document.querySelectorAll('.stats-number');
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (
            entry.isIntersecting &&
            !entry.target.hasAttribute('data-animated')
          ) {
            const target = parseInt(entry.target.textContent, 10);
            entry.target.textContent = '0';
            animateCounter(entry.target, 0, isNaN(target) ? 0 : target);
            entry.target.setAttribute('data-animated', 'true');
          }
        });
      },
      { threshold: 0.5 }
    );
    counters.forEach((el) => observer.observe(el));
  }

  function smoothAnchorScroll() {
    document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
      anchor.addEventListener('click', function (e) {
        const href = this.getAttribute('href');
        if (!href || href.trim() === '#' || href.length < 2) {
          return;
        }

        const targetId = href.slice(1).split('?')[0].split('&')[0].trim();
        if (!targetId) {
          return;
        }

        const target = document.getElementById(targetId);
        if (!target) {
          return;
        }

        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
  }

  function initializeModalHandlers() {
    if (typeof window.enforceNavbarZIndex === 'function') {
      window.enforceNavbarZIndex();
    }
  }

  // Сбрасываем состояние лоадера при возврате по истории
  // и перед кешированием страницы браузером
  function resetPageLoader() {
    const loader = document.getElementById('pageLoader');
    loader?.classList.remove('visible', 'fade-out');
    document.getElementById('global-progress-bar')?.remove();
  }

  window.addEventListener('pageshow', resetPageLoader);
  window.addEventListener('pagehide', resetPageLoader);
  if ('serviceWorker' in navigator) {
    // Скрываем лоадер после активации сервис‑воркера
    navigator.serviceWorker.addEventListener(
      'controllerchange',
      resetPageLoader
    );
  }

  document.addEventListener('DOMContentLoaded', function () {
    // Убираем лоадер страницы
    const loader = document.getElementById('pageLoader');
    if (loader) {
      document.getElementById('global-progress-bar')?.remove();
      const prefersReducedMotion = window.matchMedia(
        '(prefers-reduced-motion: reduce)'
      ).matches;
      if (!prefersReducedMotion) {
        loader.classList.add('fade-out');
        setTimeout(() => loader.classList.remove('fade-out'), 400);
      }
      loader.classList.remove('visible');
      const navbar = document.querySelector('.navbar');
      if (navbar) navbar.style.zIndex = '1031';
    }

    // Авто‑закрытие alert'ов
    document.querySelectorAll('.alert').forEach((alert) => {
      setTimeout(() => {
        if (alert && alert.parentNode) {
          try {
            // eslint-disable-next-line no-undef
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
          } catch (e) {
            alert.remove();
          }
        }
      }, 5000);
    });

    setupFormLoadingStates();
    setupPageTransitions();
    initializeModalHandlers();
    animateOnView();
    setTimeout(initCounters, 500);
    smoothAnchorScroll();
  });

  // Expose helpers
  window.showPageLoader = showPageLoader;
  window.showToast = showToast;
})();
