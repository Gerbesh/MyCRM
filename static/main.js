// Функция для получения CSRF токена
function getCSRFToken() {
  return document
    .querySelector('meta[name="csrf-token"]')
    .getAttribute('content');
}

// Функция для выполнения AJAX запросов с CSRF
async function fetchWithCSRF(url, options = {}) {
  const token = getCSRFToken();
  options.credentials = options.credentials || 'same-origin';

  // Добавляем токен в тело запроса
  if (options.body instanceof FormData) {
    options.body.set('csrf_token', token);
  } else if (options.body instanceof URLSearchParams) {
    options.body.set('csrf_token', token);
    options.headers = {
      ...options.headers,
      'Content-Type': 'application/x-www-form-urlencoded',
    };
  } else if (typeof options.body === 'string') {
    if (
      options.headers &&
      options.headers['Content-Type'] === 'application/json'
    ) {
      try {
        const data = JSON.parse(options.body);
        data.csrf_token = token;
        options.body = JSON.stringify(data);
      } catch (e) {
        const params = new URLSearchParams(options.body);
        params.set('csrf_token', token);
        options.body = params.toString();
        options.headers = {
          ...options.headers,
          'Content-Type': 'application/x-www-form-urlencoded',
        };
      }
    } else {
      const params = new URLSearchParams(options.body);
      params.set('csrf_token', token);
      options.body = params.toString();
      options.headers = {
        ...options.headers,
        'Content-Type': 'application/x-www-form-urlencoded',
      };
    }
  } else if (!options.body) {
    options.body = new URLSearchParams({ csrf_token: token }).toString();
    options.headers = {
      ...options.headers,
      'Content-Type': 'application/x-www-form-urlencoded',
    };
  }

  // Добавляем токен в заголовок
  options.headers = {
    ...options.headers,
    'X-CSRFToken': token,
  };

  try {
    const response = await fetch(url, options);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response;
  } catch (error) {
    console.error('Fetch error:', error);
    throw error;
  }
}

// Функция для настройки автодополнения
function setupAutocomplete(
  inputSelector,
  hiddenSelector,
  searchUrl,
  createUrl
) {
  const input = document.querySelector(inputSelector);
  const hiddenInput = document.querySelector(hiddenSelector);

  if (!input || !hiddenInput) {
    console.error('Elements not found:', inputSelector, hiddenSelector);
    return;
  }

  const suggestionsContainer = document.createElement('ul');
  suggestionsContainer.className = 'suggestions';
  suggestionsContainer.setAttribute('role', 'listbox');
  input.parentNode.appendChild(suggestionsContainer);

  let debounceTimer;
  let activeIndex = -1;

  function updateActive(items) {
    items.forEach((item, index) => {
      if (index === activeIndex) {
        item.classList.add('active');
        item.setAttribute('aria-selected', 'true');
        item.focus();
      } else {
        item.classList.remove('active');
        item.setAttribute('aria-selected', 'false');
      }
    });
  }

  input.addEventListener('input', async function () {
    const query = this.value.trim();
    clearTimeout(debounceTimer);

    if (query.length < 2) {
      suggestionsContainer.classList.remove('open');
      return;
    }

    debounceTimer = setTimeout(async () => {
      try {
        const response = await fetch(
          `${searchUrl}?query=${encodeURIComponent(query)}`
        );
        const items = await response.json();

        suggestionsContainer.innerHTML = '';
        activeIndex = -1;

        items.forEach((item) => {
          const li = document.createElement('li');
          li.className = 'suggestion-item';
          li.setAttribute('role', 'option');
          li.setAttribute('tabindex', '-1');
          li.textContent = item.name;
          li.addEventListener('click', () => {
            input.value = item.name;
            hiddenInput.value = item.id;
            suggestionsContainer.classList.remove('open');
          });
          suggestionsContainer.appendChild(li);
        });

        // Опция создания нового
        const createLi = document.createElement('li');
        createLi.className = 'suggestion-item create-new';
        createLi.setAttribute('role', 'option');
        createLi.setAttribute('tabindex', '-1');
        createLi.textContent = `Создать новый "${query}"`;
        createLi.addEventListener('click', async () => {
          try {
            // спользуем FormData вместо JSON
            const formData = new FormData();
            formData.append('name', query);

            const response = await fetchWithCSRF(createUrl, {
              method: 'POST',
              body: formData,
            });
            const newItem = await response.json();
            input.value = newItem.name;
            hiddenInput.value = newItem.id;
            suggestionsContainer.classList.remove('open');
            activeIndex = -1;
          } catch (error) {
            console.error('Error creating item:', error);
            alert('Ошибка при создании. Попробуйте еще раз.');
          }
        });
        suggestionsContainer.appendChild(createLi);
        suggestionsContainer.classList.add('open');
      } catch (error) {
        console.error('Error fetching suggestions:', error);
      }
    }, 300);
  });

  // Закрытие подсказок при клике вне
  document.addEventListener('click', (e) => {
    if (!input.contains(e.target) && !suggestionsContainer.contains(e.target)) {
      suggestionsContainer.classList.remove('open');
      activeIndex = -1;
    }
  });

  input.addEventListener('keydown', (e) => {
    const items = suggestionsContainer.querySelectorAll('[role="option"]');
    if (!items.length) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      activeIndex = (activeIndex + 1) % items.length;
      updateActive(items);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      activeIndex = (activeIndex - 1 + items.length) % items.length;
      updateActive(items);
    } else if (e.key === 'Enter' && activeIndex >= 0) {
      e.preventDefault();
      items[activeIndex].click();
    } else if (e.key === 'Escape') {
      suggestionsContainer.classList.remove('open');
      activeIndex = -1;
    }
  });
}
