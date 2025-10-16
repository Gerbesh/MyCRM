'use strict';

// Небольшие улучшения доступности
document.addEventListener('DOMContentLoaded', () => {
  const userDropdown = document.getElementById('userDropdown');
  if (userDropdown) {
    userDropdown.addEventListener('shown.bs.dropdown', () =>
      userDropdown.setAttribute('aria-expanded', 'true')
    );
    userDropdown.addEventListener('hidden.bs.dropdown', () =>
      userDropdown.setAttribute('aria-expanded', 'false')
    );
  }
});
