'use strict';
(function () {
  function qs(sel, root = document) {
    return root.querySelector(sel);
  }
  document.addEventListener('DOMContentLoaded', () => {
    const table = qs('#requests-table');
    const cards = qs('#requests-cards');
    const tableSkeleton = qs('#requests-table-skeleton');
    const cardsSkeleton = qs('#requests-cards-skeleton');
    if (tableSkeleton && table) {
      setTimeout(() => {
        tableSkeleton.classList.add('d-none');
        table.classList.remove('d-none');
      }, 300);
    }
    if (cardsSkeleton && cards) {
      setTimeout(() => {
        cardsSkeleton.classList.add('d-none');
        cards.classList.remove('d-none');
      }, 300);
    }
  });
})();
