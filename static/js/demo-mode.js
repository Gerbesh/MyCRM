'use strict';

// Скрипт блокировки действий для демо-пользователя
if (document.body && document.body.dataset.demoUser === 'true') {
  const warningMessage =
    'Демо-доступ предназначен только для чтения. Изменение данных отключено.';

  const notify = () => {
    if (typeof window.showToast === 'function') {
      window.showToast(warningMessage, 'warning', 5000);
    } else {
      alert(warningMessage);
    }
  };

  document.addEventListener('DOMContentLoaded', () => {
    // Перебираем формы с методами POST/PUT/PATCH/DELETE и блокируем отправку
    const blockedMethods = ['post', 'put', 'patch', 'delete'];
    const forms = document.querySelectorAll('form');
    forms.forEach((form) => {
      const method = (form.getAttribute('method') || 'get').toLowerCase();
      if (!blockedMethods.includes(method)) {
        return;
      }
      form.addEventListener('submit', (event) => {
        event.preventDefault();
        const submitBtn = form.querySelector(
          'button[type="submit"], input[type="submit"]'
        );
        if (submitBtn) {
          submitBtn.blur();
          submitBtn.classList.add('disabled');
          setTimeout(() => submitBtn.classList.remove('disabled'), 150);
        }
        notify();
      });
    });

    // Отключаем элементы с атрибутом data-demo-locked
    const lockedElements = document.querySelectorAll('[data-demo-locked]');
    lockedElements.forEach((element) => {
      element.addEventListener('click', (event) => {
        event.preventDefault();
        notify();
      });
      element.addEventListener('keypress', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          notify();
        }
      });
      element.classList.add('disabled');
      element.setAttribute('aria-disabled', 'true');
      element.title = warningMessage;
    });
  });
}
