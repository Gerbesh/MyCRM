// ===== REQUEST CREATION WIZARD =====
// Пошаговый мастер создания заявок с анимациями

// Ключ хранения черновика
const DRAFT_KEY = 'requestWizardDraft:v1';
const IS_DEMO_USER =
  typeof document !== 'undefined' &&
  document.body &&
  document.body.dataset.demoUser === 'true';
const DEMO_SUBMIT_MESSAGE = 'В демо-режиме отправка заявок недоступна.';

// Fallback for customConfirm: ensure it exists even if alert-modal.js failed to load
if (
  typeof window !== 'undefined' &&
  typeof window.customConfirm !== 'function'
) {
  window.customConfirm = function (message) {
    try {
      return Promise.resolve(window.confirm(message));
    } catch (e) {
      return Promise.resolve(true);
    }
  };
}

// Флаг, блокирующий автосохранение до выбора действия пользователем
let autosaveEnabled = !IS_DEMO_USER;

if (IS_DEMO_USER) {
  try {
    localStorage.removeItem(DRAFT_KEY);
  } catch (e) {
    console.warn('Не удалось очистить локальный черновик в демо-режиме', e);
  }
}

// Утилиты работы с черновиком
function readDraft() {
  if (IS_DEMO_USER) {
    return null;
  }
  try {
    return JSON.parse(localStorage.getItem(DRAFT_KEY) || 'null');
  } catch {
    return null;
  }
}

class WizardLoadingTracker {
  constructor() {
    this.overlay = document.getElementById('wizard-loading-overlay');
    this.progressBar = document.getElementById('wizard-loading-bar');
    this.label = document.getElementById('wizard-loading-label');
    this.detail = document.getElementById('wizard-loading-detail');
    this.datasets = new Map();
    this.totalKnownPages = 0;
    this.completedPages = 0;
    this.finished = false;
    this.lastPercent = 0;
  }

  start() {
    if (!this.overlay) {
      return;
    }
    this.finished = false;
    this.datasets.clear();
    this.totalKnownPages = 0;
    this.completedPages = 0;
    this.lastPercent = 0;
    this.overlay.style.display = 'flex';
    this.overlay.classList.remove('is-visible');
    requestAnimationFrame(() => {
      if (this.overlay) {
        this.overlay.classList.add('is-visible');
      }
    });
    this.updateProgress(0);
    this.setDetail('Проверяем количество страниц с данными…');
  }

  startDataset(name) {
    if (!this.overlay || this.finished) {
      return;
    }
    const displayName = this.formatName(name);
    this.datasets.set(displayName, {
      displayName,
      known: false,
      totalPages: 0,
      completed: 0,
    });
    this.setDetail(`Загружаем ${displayName}: готовим список страниц…`);
  }

  setDatasetTotalPages(name, totalPages) {
    if (!this.overlay || this.finished) {
      return;
    }
    const dataset = this.datasets.get(this.formatName(name));
    if (!dataset) {
      return;
    }
    const parsed = Number.isFinite(totalPages) && totalPages > 0
      ? Math.ceil(totalPages)
      : null;
    if (!parsed) {
      return;
    }
    if (dataset.known) {
      this.totalKnownPages -= dataset.totalPages;
    }
    dataset.known = true;
    dataset.totalPages = parsed;
    this.totalKnownPages += parsed;
    const shown = Math.min(dataset.completed + 1, dataset.totalPages);
    this.setDetail(
      `Загружаем ${dataset.displayName}: страница ${shown} из ${dataset.totalPages}`
    );
  }

  completePage(name, pageNumber) {
    if (!this.overlay || this.finished) {
      return;
    }
    const dataset = this.datasets.get(this.formatName(name));
    if (dataset) {
      dataset.completed = Math.max(dataset.completed + 1, pageNumber || 1);
      const { displayName } = dataset;
      if (dataset.known && dataset.totalPages) {
        const current = Math.min(dataset.completed, dataset.totalPages);
        this.setDetail(
          `Загружаем ${displayName}: страница ${current} из ${dataset.totalPages}`
        );
      } else {
        this.setDetail(`Загружаем ${displayName}: страница ${dataset.completed}`);
      }
    }
    this.completedPages += 1;
    this.updateProgress(this.calculatePercent());
  }

  completeDataset(name) {
    if (!this.overlay || this.finished) {
      return;
    }
    const dataset = this.datasets.get(this.formatName(name));
    if (dataset) {
      this.setDetail(`Загрузка списка «${dataset.displayName}» завершена`);
    }
  }

  showFinalizing() {
    if (!this.overlay || this.finished) {
      return;
    }
    const percent = this.calculatePercent();
    const boosted = percent >= 96 ? percent : Math.min(96, Math.max(percent, 75));
    this.updateProgress(boosted);
    this.setDetail('Готовим интерфейс мастера…');
  }

  finish() {
    if (!this.overlay || this.finished) {
      return;
    }
    this.finished = true;
    this.updateProgress(100);
    this.setDetail('Загрузка завершена. Открываем мастер…');
    this.overlay.classList.remove('is-visible');
    setTimeout(() => {
      if (this.overlay) {
        this.overlay.style.display = 'none';
      }
    }, 350);
  }

  updateProgress(value) {
    const clamped = Math.max(0, Math.min(100, Math.round(value)));
    this.lastPercent = clamped;
    if (this.progressBar) {
      this.progressBar.style.width = `${clamped}%`;
      this.progressBar.setAttribute('aria-valuenow', `${clamped}`);
    }
    if (this.label) {
      this.label.textContent = `${clamped}%`;
    }
  }

  setDetail(text) {
    if (this.detail) {
      this.detail.textContent = text;
    }
  }

  calculatePercent() {
    let percent;
    if (this.totalKnownPages > 0) {
      percent = (this.completedPages / this.totalKnownPages) * 100;
      percent = Math.min(99, Math.max(5, percent));
    }
    if (percent === undefined) {
      if (this.completedPages === 0) {
        percent = 0;
      } else {
        percent = Math.min(90, Math.max(12, this.completedPages * 12));
      }
    }
    if (percent < this.lastPercent) {
      return this.lastPercent;
    }
    return percent;
  }

  formatName(name) {
    const source = typeof name === 'string' ? name.trim() : '';
    if (!source) {
      return 'Данные';
    }
    return source.charAt(0).toUpperCase() + source.slice(1);
  }
}

function writeDraft(draft) {
  if (IS_DEMO_USER) {
    return;
  }
  const data = { ...draft, savedAt: Date.now() };
  localStorage.setItem(DRAFT_KEY, JSON.stringify(data));
  fetchRetry(window.CRM_URLS.DRAFT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ draft: data }),
  }).catch(() => {});
}
async function loadSessionDraft() {
  if (IS_DEMO_USER) {
    return;
  }
  try {
    const resp = await fetchRetry(window.CRM_URLS.DRAFT);
    if (resp.ok) {
      const data = await resp.json();
      if (data && data.draft) {
        localStorage.setItem(DRAFT_KEY, JSON.stringify(data.draft));
      }
    }
  } catch (e) {
    console.error('Не удалось загрузить черновик из сессии', e);
  }
}
async function clearDraft() {
  if (IS_DEMO_USER) {
    try {
      localStorage.removeItem(DRAFT_KEY);
    } catch (e) {
      console.warn('Не удалось очистить локальный черновик', e);
    }
    return;
  }
  localStorage.removeItem(DRAFT_KEY);
  await fetch(window.CRM_URLS.DRAFT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ draft: null }),
    keepalive: true,
  }).catch(() => {});
}

/**
 * Основной класс мастера создания заявок
 */
class RequestWizard {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.loadingTracker = new WizardLoadingTracker();
    this.currentStepIndex = 0;
    this.steps = [];
    this.stepChangeCallbacks = [];
    this.data = {
      object: null,
      contractors: [],
      manufacturers: [],
      comment: '',
      files: [],
    };

    // Кэш для данных
    this.cache = {
      objects: [],
      contractors: [],
      manufacturers: [],
    };

    // Mobile-specific properties
    this.isMobile = this.detectMobile();
    this.touchStartX = 0;
    this.touchStartY = 0;
    this.isSwipeEnabled = true;

    // Performance optimization for mobile
    this.animationFrame = null;
    this.isAnimating = false;

    // дентификатор таймера запуска
    this.startTimer = null;

    this.hasShownFirstStep = false;

    this.init();
  }

  get currentStep() {
    return this.currentStepIndex;
  }

  onStepChange(cb) {
    this.stepChangeCallbacks.push(cb);
  }

  goToStep(step) {
    if (step >= 0 && step < this.steps.length) {
      this.showStep(step);
      this.updateProgress();
    }
  }

  /**
   * нициализация мастера
   */
  async init() {
    console.log('нициализация мастера создания заявок');

    // Mobile-specific initialization
    if (this.isMobile) {
      this.initMobileFeatures();
    }

    // Загружаем черновик из сессии и localStorage
    await loadSessionDraft();
    this.loadFromLocalStorage();

    // Загружаем данные
    this.loadingTracker?.start();
    await this.loadData();
    this.loadingTracker?.showFinalizing();

    // Заполнение мастера при копировании заявки
    if (window.COPY_REQUEST_DATA) {
      // При копировании очищаем локальный черновик, чтобы не подставлялись старые данные
      try {
        localStorage.removeItem(DRAFT_KEY);
      } catch {}
      const copy = window.COPY_REQUEST_DATA || {};
      // Объект: кэш -> данные сервера -> placeholder
      let obj = null;
      try {
        obj =
          (this.cache.objects || []).find(
            (o) => o && o.id === copy.object_id
          ) || null;
      } catch {}
      if (!obj && copy.object && copy.object.id === copy.object_id) {
        obj = copy.object;
      }
      if (!obj && copy.object_id) {
        obj = { id: copy.object_id, name: `Объект #${copy.object_id}` };
      }
      this.data.object = obj;
      // Подрядчики: кэш -> данные сервера -> placeholder
      let contractors = [];
      try {
        contractors = (copy.contractor_ids || [])
          .map((cid) =>
            (this.cache.contractors || []).find((c) => c && c.id === cid)
          )
          .filter(Boolean);
      } catch {}
      if (
        (!contractors || contractors.length === 0) &&
        Array.isArray(copy.contractors) &&
        copy.contractors.length > 0
      ) {
        contractors = copy.contractors
          .map((c) => (c && c.id ? c : null))
          .filter(Boolean);
      }
      if (
        (!contractors || contractors.length === 0) &&
        Array.isArray(copy.contractor_ids) &&
        copy.contractor_ids.length > 0
      ) {
        contractors = copy.contractor_ids.map((cid) => ({
          id: cid,
          name: `Подрядчик #${cid}`,
        }));
      }
      this.data.contractors = contractors || [];
      this.data.manufacturers = copy.manufacturers || [];
      this.data.comment = copy.comment || '';
      this.currentStepIndex = 3;
      autosaveEnabled = false;

      // Очищаем черновик на сервере
      fetch(window.CRM_URLS.DRAFT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ draft: null }),
      }).catch(() => {});
    }

    // Создаем шаги
    this.createSteps();

    // нициализируем drag & drop
    this.initDragDrop();

    // нициализируем touch gestures для мобильных устройств
    if (this.isMobile) {
      this.initTouchGestures();
    }

    // Запускаем первый шаг сразу
    this.startWizard();
    if (window.COPY_REQUEST_DATA) {
      this.goToStep(3);
    }
  }

  /**
   * Загрузка данных с сервера
   */
  async loadData() {
    const tracker = this.loadingTracker;
    try {
      // Загружаем объекты
      const objectsData = await this.fetchAllEntities(
        window.CRM_URLS?.GET_ALL_OBJECTS || '/api/v1/get_all_objects',
        { datasetName: 'объекты', tracker }
      );
      this.cache.objects = Array.isArray(objectsData) ? objectsData : [];

      // Загружаем подрядчиков
      const contractorsData = await this.fetchAllEntities(
        window.CRM_URLS?.GET_ALL_CONTRACTORS || '/api/v1/get_all_contractors',
        { datasetName: 'подрядчики', tracker }
      );
      this.cache.contractors = Array.isArray(contractorsData)
        ? contractorsData
        : [];

      // Загружаем производителей из скрипта
      const manufacturersScript = document.getElementById('manufacturers-data');
      if (manufacturersScript) {
        this.cache.manufacturers = JSON.parse(manufacturersScript.textContent);
      }

      console.log('Данные загружены:', {
        objects: this.cache.objects.length,
        contractors: this.cache.contractors.length,
        manufacturers: this.cache.manufacturers.length,
      });
    } catch (error) {
      console.error('Ошибка загрузки данных:', error);
    }
  }

  /**
   * Последовательно загружает все элементы постраничного API.
   * Поддерживаются как новые, так и устаревшие форматы ответов (массивы без пагинации).
   */
  async fetchAllEntities(initialUrl, options = {}) {
    if (!initialUrl) {
      return [];
    }

    const { datasetName = 'данные', tracker = null } = options;
    const datasetLabel =
      tracker && typeof tracker.formatName === 'function'
        ? tracker.formatName(datasetName)
        : 'Данные';
    const result = [];
    const visited = new Set();
    let nextUrl = this.normalizePaginatedUrl(initialUrl);
    let pageIndex = 0;
    let totalPages = null;

    tracker?.startDataset(datasetName);

    while (nextUrl && !visited.has(nextUrl)) {
      visited.add(nextUrl);
      try {
        const response = await fetchRetry(nextUrl);
        if (!response.ok) {
          console.error(
            `Не удалось загрузить данные по адресу ${nextUrl}: ${response.status}`
          );
          tracker?.setDetail(
            `Ошибка ${response.status} при загрузке списка «${datasetLabel}»`
          );
          break;
        }

        pageIndex += 1;
        const payload = await response.json();
        if (totalPages === null) {
          const detectedPages = this.getTotalPagesFromPayload(payload);
          if (detectedPages) {
            totalPages = detectedPages;
            tracker?.setDatasetTotalPages(datasetName, totalPages);
          }
        }
        const portion = this.extractEntitiesFromPayload(payload);
        if (portion.length > 0) {
          result.push(...portion);
        }

        const currentPage = this.getCurrentPageFromPayload(payload, pageIndex);
        tracker?.completePage(datasetName, currentPage);

        const nextLink = this.getNextLink(payload);
        if (nextLink) {
          nextUrl = this.normalizePaginatedUrl(nextLink);
        } else {
          break;
        }
      } catch (err) {
        console.error('Ошибка при загрузке данных постранично:', err);
        tracker?.setDetail(
          `Не удалось загрузить данные для списка «${datasetLabel}». Проверьте подключение.`
        );
        break;
      }
    }

    tracker?.completeDataset(datasetName);
    return result;
  }

  /**
   * Приводит URL к единому виду и гарантирует максимально возможный лимит (100 записей).
   */
  normalizePaginatedUrl(rawUrl) {
    try {
      const urlObject = new URL(rawUrl, window.location.origin);
      const currentLimit = Number.parseInt(
        urlObject.searchParams.get('limit') || '0',
        10
      );
      if (!currentLimit || Number.isNaN(currentLimit) || currentLimit < 100) {
        urlObject.searchParams.set('limit', '100');
      }
      return urlObject.toString();
    } catch (e) {
      console.error('Не удалось нормализовать URL пагинации:', rawUrl, e);
      return rawUrl;
    }
  }

  /**
   * Достаёт массив сущностей из ответа API, сохраняя обратную совместимость.
   */
  extractEntitiesFromPayload(payload) {
    if (Array.isArray(payload)) {
      return payload;
    }
    if (Array.isArray(payload?.data)) {
      return payload.data;
    }
    if (Array.isArray(payload?.objects)) {
      return payload.objects;
    }
    if (Array.isArray(payload?.contractors)) {
      return payload.contractors;
    }
    return [];
  }

  /**
   * Возвращает ссылку на следующую страницу, если она присутствует в ответе.
   */
  getNextLink(payload) {
    if (payload?.links?.next) {
      return payload.links.next;
    }
    if (typeof payload?.next === 'string' && payload.next.length > 0) {
      return payload.next;
    }
    if (typeof payload?.meta?.next === 'string' && payload.meta.next.length > 0) {
      return payload.meta.next;
    }
    return null;
  }

  getTotalPagesFromPayload(payload) {
    if (!payload || typeof payload !== 'object') {
      return null;
    }
    const meta = payload.meta || payload.metadata || null;
    const candidates = [
      'total_pages',
      'totalPages',
      'pages',
      'page_count',
      'pageCount',
      'last_page',
      'lastPage',
    ];
    if (meta && typeof meta === 'object') {
      for (const key of candidates) {
        const parsed = this.parsePositiveInt(meta[key]);
        if (parsed) {
          return parsed;
        }
      }
      const total = this.parsePositiveInt(meta.total);
      const perPage = this.parsePositiveInt(meta.per_page || meta.perPage || meta.limit);
      if (total && perPage) {
        return Math.ceil(total / perPage);
      }
      if (Array.isArray(meta.pages)) {
        return meta.pages.length;
      }
    }
    const rootCandidates = ['total_pages', 'pages', 'page_count'];
    for (const key of rootCandidates) {
      const parsed = this.parsePositiveInt(payload[key]);
      if (parsed) {
        return parsed;
      }
    }
    return null;
  }

  getCurrentPageFromPayload(payload, fallback) {
    if (!payload || typeof payload !== 'object') {
      return fallback;
    }
    const meta = payload.meta || payload.metadata || null;
    const keys = ['current_page', 'currentPage', 'page', 'page_number', 'pageNumber'];
    if (meta && typeof meta === 'object') {
      for (const key of keys) {
        const parsed = this.parsePositiveInt(meta[key]);
        if (parsed) {
          return parsed;
        }
      }
    }
    for (const key of ['page', 'current_page', 'currentPage']) {
      const parsed = this.parsePositiveInt(payload[key]);
      if (parsed) {
        return parsed;
      }
    }
    return fallback;
  }

  parsePositiveInt(value) {
    if (value === null || value === undefined) {
      return null;
    }
    const num = Number.parseInt(value, 10);
    if (Number.isFinite(num) && num > 0) {
      return num;
    }
    return null;
  }

  /**
   * Создание шагов мастера
   */
  createSteps() {
    this.steps = [
      new ObjectStep(this),
      new ContractorStep(this),
      new ManufacturerStep(this),
      new FinalStep(this),
    ];
  }

  /**
   * Сохранение данных мастера в localStorage
   */
  saveToLocalStorage() {
    autosave();
  }

  /**
   * Загрузка данных мастера из localStorage
   */
  loadFromLocalStorage() {
    try {
      const draft = readDraft();
      if (draft?.data) {
        this.data.object = draft.data.object || null;
        this.data.contractors = draft.data.contractors || [];
        this.data.manufacturers = draft.data.manufacturers || [];
        this.data.comment = draft.data.comment || '';
        this.currentStepIndex = draft.data._step || 0;
      }
    } catch (error) {
      console.error('Ошибка загрузки из localStorage:', error);
    }
  }

  /**
   * Запуск мастера
   */
  startWizard() {
    this.updateProgress();
    this.showStep(this.currentStepIndex);
  }

  /**
   * Показать определенный шаг
   */
  async showStep(stepIndex) {
    if (stepIndex < 0 || stepIndex >= this.steps.length) {
      return;
    }

    // Prevent multiple animations on mobile
    if (this.isMobile && this.isAnimating) {
      return;
    }

    this.isAnimating = true;

    // Скрываем текущий шаг
    if (this.currentStepIndex >= 0 && this.steps[this.currentStepIndex]) {
      await this.steps[this.currentStepIndex].hide();
    }

    // Показываем новый шаг
    this.currentStepIndex = stepIndex;
    this.stepChangeCallbacks.forEach((cb) => cb(stepIndex));
    await this.steps[this.currentStepIndex].show();

    if (!this.hasShownFirstStep) {
      this.hasShownFirstStep = true;
      this.loadingTracker?.finish();
    }

    this.isAnimating = false;
  }

  /**
   * Переход к следующему шагу
   */
  async nextStep() {
    const currentStep = this.steps[this.currentStepIndex];

    // Валидируем текущий шаг
    if (!(await currentStep.validate())) {
      return false;
    }

    // Сохраняем данные текущего шага
    await currentStep.saveData();

    // Переходим к следующему шагу
    if (this.currentStepIndex < this.steps.length - 1) {
      await this.showStep(this.currentStepIndex + 1);
      this.updateProgress();
      return true;
    } else {
      // Последний шаг - отправляем форму
      return await this.submitForm();
    }
  }

  /**
   * Переход к предыдущему шагу
   */
  async prevStep() {
    const currentStep = this.steps[this.currentStepIndex];

    // Сохраняем данные текущего шага перед возвратом
    if (currentStep && typeof currentStep.saveData === 'function') {
      await currentStep.saveData();
    }

    if (this.currentStepIndex > 0) {
      await this.showStep(this.currentStepIndex - 1);
      this.updateProgress();
      return true;
    }
    return false;
  }

  /**
   * Обновление прогресс-бара
   */
  updateProgress() {
    const progressBar = document.querySelector(
      '#wizard-progress .progress-bar'
    );
    if (progressBar) {
      const progress = ((this.currentStepIndex + 1) / this.steps.length) * 100;
      progressBar.style.width = progress + '%';
      progressBar.setAttribute('aria-valuenow', progress);
    }

    // Update mobile step indicator
    if (this.isMobile) {
      const currentStepSpan = document.getElementById('current-step');
      if (currentStepSpan) {
        currentStepSpan.textContent = this.currentStepIndex + 1;
      }
    }
  }

  /**
   * Отправка формы
   */
  async submitForm() {
    const btn = document.getElementById('submit-request-btn');
    if (btn && !btn.dataset.originalText) {
      btn.dataset.originalText = btn.innerHTML;
    }

    const restoreButton = () => {
      if (!btn) {
        return;
      }
      btn.disabled = false;
      const original = btn.dataset?.originalText;
      btn.innerHTML = original || 'Создать заявку';
    };

    if (IS_DEMO_USER) {
      restoreButton();
      if (typeof window.showToast === 'function') {
        window.showToast(DEMO_SUBMIT_MESSAGE, 'info', 5000);
      } else {
        alert(DEMO_SUBMIT_MESSAGE);
      }
      return false;
    }

    if (btn) {
      btn.disabled = true;
      btn.innerHTML = 'Отправка...';
    }

    try {
      const formData = new FormData();
      formData.append('object_id', this.data.object.id);

      // Отправляем ID подрядчиков
      this.data.contractors.forEach((contractor) => {
        formData.append('contractor_ids[]', contractor.id);
      });

      // Отправляем производителей
      this.data.manufacturers.forEach((manufacturer) => {
        formData.append('manufacturers[]', manufacturer);
      });

      if (this.data.comment) {
        formData.append('request_comment', this.data.comment);
      }

      // Добавляем файлы
      this.data.files.forEach((file) => {
        formData.append('files[]', file);
      });

      const token =
        document.querySelector('meta[name="csrf-token"]')?.content ||
        window.CSRF_TOKEN;
      if (token && !formData.get('csrf_token')) {
        formData.append('csrf_token', token);
      }

      const headers = {
        'X-Requested-With': 'XMLHttpRequest',
        Accept: 'application/json',
      };
      if (token) {
        headers['X-CSRFToken'] = token;
      }

      const resp = await fetchRetry(
        window.CRM_URLS?.CREATE_REQUEST || '/requests/crud/create_request',
        {
          method: 'POST',
          headers,
          body: formData,
          credentials: 'same-origin',
        }
      );

      const ctype = resp.headers.get('Content-Type') || '';
      if (!resp.ok) {
        if ([0, 502, 503, 504].includes(resp.status)) {
          throw new Error(
            'Сервер перезапускается, попробуйте ещё раз через пару секунд.'
          );
        }
        const text = await resp.text();
        throw new Error(`HTTP ${resp.status} ${text.slice(0, 200)}`);
      }

      if (ctype.includes('application/json')) {
        const data = await resp.json();
        if (data.success) {
          await clearDraft();
          window.location.href = data.redirect_url;
          return true;
        }
        throw new Error(data.error || 'Неизвестная ошибка сервера');
      } else {
        await resp.text();
        throw new Error(
          'Неожиданный ответ сервера (HTML). Пожалуйста, повторите.'
        );
      }
    } catch (err) {
      console.error(err);
      const msg =
        err.message && err.message.includes('Failed to fetch')
          ? 'Сервер перезапускается, попробуйте ещё раз через пару секунд.'
          : err.message;
      alert(`Ошибка отправки: ${msg}`);
      return false;
    } finally {
      restoreButton();
    }
  }

  /**
   * нициализация drag & drop для файлов
   */
  initDragDrop() {
    // Use mobile-optimized drag drop if on mobile
    if (this.isMobile) {
      this.initMobileDragDrop();
      return;
    }

    const overlay = document.getElementById('drag-drop-overlay');
    let dragCounter = 0;
    let lastFocusedElement = null;

    // Обработчики для всего документа
    document.addEventListener('dragenter', (e) => {
      e.preventDefault();
      dragCounter++;
      if (dragCounter === 1) {
        lastFocusedElement = document.activeElement;
        overlay.classList.add('active');
        overlay.focus();
      }
    });

    document.addEventListener('dragleave', (e) => {
      e.preventDefault();
      dragCounter--;
      if (dragCounter === 0) {
        overlay.classList.remove('active');
        lastFocusedElement && lastFocusedElement.focus();
      }
    });

    document.addEventListener('dragover', (e) => {
      e.preventDefault();
    });

    document.addEventListener('drop', (e) => {
      e.preventDefault();
      dragCounter = 0;
      overlay.classList.remove('active');
      lastFocusedElement && lastFocusedElement.focus();

      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) {
        this.addFiles(files);
      }
    });

    // Клик по overlay для отмены
    overlay.addEventListener('click', () => {
      dragCounter = 0;
      overlay.classList.remove('active');
      lastFocusedElement && lastFocusedElement.focus();
    });

    // Закрытие по Esc
    overlay.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        dragCounter = 0;
        overlay.classList.remove('active');
        lastFocusedElement && lastFocusedElement.focus();
      }
    });
  }

  /**
   * Добавление файлов
   */
  addFiles(files) {
    files.forEach((file) => {
      // Проверяем размер файла (50MB)
      if (file.size > 50 * 1024 * 1024) {
        alert(`Файл "${file.name}" слишком большой. Максимальный размер: 50MB`);
        return;
      }

      // Проверяем, не добавлен ли уже такой файл
      const exists = this.data.files.some(
        (f) => f.name === file.name && f.size === file.size
      );
      if (!exists) {
        this.data.files.push(file);
      }
    });

    this.saveToLocalStorage();

    // Обновляем отображение файлов в финальном шаге
    const finalStep = this.steps[this.steps.length - 1];
    if (finalStep && typeof finalStep.updateFilesList === 'function') {
      finalStep.updateFilesList();
    }
  }

  /**
   * Удаление файла
   */
  removeFile(fileIndex) {
    if (fileIndex >= 0 && fileIndex < this.data.files.length) {
      this.data.files.splice(fileIndex, 1);
      this.saveToLocalStorage();

      // Обновляем отображение файлов
      const finalStep = this.steps[this.steps.length - 1];
      if (finalStep && typeof finalStep.updateFilesList === 'function') {
        finalStep.updateFilesList();
      }
    }
  }

  /**
   * Detect if device is mobile
   */
  detectMobile() {
    return (
      /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
        navigator.userAgent
      ) ||
      window.innerWidth <= 768 ||
      'ontouchstart' in window
    );
  }

  /**
   * Initialize mobile-specific features
   */
  initMobileFeatures() {
    // Add mobile-specific CSS classes
    document.body.classList.add('mobile-device');

    // Optimize scrolling for mobile
    if ('scrollBehavior' in document.documentElement.style) {
      document.documentElement.style.scrollBehavior = 'smooth';
    }
  }

  /**
   * Initialize touch gestures for mobile navigation
   */
  initTouchGestures() {
    let startX = 0;
    let startY = 0;
    let threshold = 100;
    let restraint = 100;
    let allowedTime = 300;
    let startTime = 0;

    this.container.addEventListener(
      'touchstart',
      (e) => {
        if (!this.isSwipeEnabled) return;

        const touchobj = e.changedTouches[0];
        startX = touchobj.pageX;
        startY = touchobj.pageY;
        startTime = new Date().getTime();
      },
      { passive: true }
    );

    this.container.addEventListener(
      'touchend',
      (e) => {
        if (!this.isSwipeEnabled) return;

        const touchobj = e.changedTouches[0];
        const distX = touchobj.pageX - startX;
        const distY = touchobj.pageY - startY;
        const elapsedTime = new Date().getTime() - startTime;

        if (elapsedTime <= allowedTime) {
          if (Math.abs(distX) >= threshold && Math.abs(distY) <= restraint) {
            if (distX > 0) {
              this.handleSwipeRight();
            } else {
              this.handleSwipeLeft();
            }
          }
        }
      },
      { passive: true }
    );
  }

  /**
   * Handle swipe left gesture (next step)
   */
  handleSwipeLeft() {
    if (this.currentStepIndex < this.steps.length - 1) {
      this.nextStep();
    }
  }

  /**
   * Handle swipe right gesture (previous step)
   */
  handleSwipeRight() {
    if (this.currentStepIndex > 0) {
      this.showStep(this.currentStepIndex - 1);
      this.updateProgress();
    }
  }

  /**
   * Initialize mobile-optimized drag & drop
   */
  initMobileDragDrop() {
    const overlay = document.getElementById('drag-drop-overlay');
    if (!overlay) return;

    // Create mobile file input
    const mobileFileInput = document.createElement('input');
    mobileFileInput.type = 'file';
    mobileFileInput.multiple = true;
    mobileFileInput.accept = 'image/*,application/pdf,.doc,.docx,.txt';
    mobileFileInput.style.display = 'none';
    mobileFileInput.id = 'mobile-file-input';

    // Handle file selection
    mobileFileInput.addEventListener('change', (e) => {
      const files = Array.from(e.target.files);
      if (files.length > 0) {
        this.addFiles(files);
      }
      // Reset input for reuse
      e.target.value = '';
    });

    document.body.appendChild(mobileFileInput);

    // Enhanced mobile overlay interactions
    overlay.addEventListener('click', (e) => {
      e.preventDefault();
      mobileFileInput.click();
    });

    overlay.addEventListener('touchend', (e) => {
      e.preventDefault();
      mobileFileInput.click();
    });

    // Update overlay content for mobile
    const dropMessage = overlay.querySelector('.drag-drop-message');
    if (dropMessage) {
      const mobileButton = dropMessage.querySelector('#mobile-file-select');
      if (mobileButton) {
        mobileButton.addEventListener('click', (e) => {
          e.stopPropagation();
          mobileFileInput.click();
        });
      }
    }

    // Store reference for cleanup
    this.mobileFileInput = mobileFileInput;
  }
}

/**
 * Базовый класс для шага мастера
 */
class WizardStep {
  constructor(wizard) {
    this.wizard = wizard;
    this.element = null;
    this.isVisible = false;
  }

  /**
   * Создание HTML элемента шага
   */
  createElement() {
    throw new Error('Метод createElement должен быть реализован в подклассе');
  }

  /**
   * Показать шаг
   */
  async show() {
    if (!this.element) {
      this.element = this.createElement();
      this.wizard.container.appendChild(this.element);
    }

    // Анимация появления
    this.element.classList.add('entering');
    await this.delay(50);
    this.element.classList.remove('entering');
    this.element.classList.add('active');

    this.isVisible = true;
    this.onShow();
  }

  /**
   * Скрыть шаг
   */
  async hide() {
    if (!this.element || !this.isVisible) return;

    this.element.classList.add('exiting');
    this.element.classList.remove('active');

    await this.delay(400); // Время анимации

    if (this.element && this.element.parentNode) {
      this.element.parentNode.removeChild(this.element);
    }

    this.element = null;
    this.isVisible = false;
  }

  /**
   * Валидация шага
   */
  async validate() {
    return true;
  }

  /**
   * Сохранение данных шага
   */
  async saveData() {
    // Реализуется в подклассах
  }

  /**
   * Вызывается при показе шага
   */
  onShow() {
    // Реализуется в подклассах
  }

  /**
   * Утилита для задержки
   */
  delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Форматирование размера файла
   */
  formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }
}

// Снимок текущего состояния формы
function currentFormSnapshot() {
  const wiz = window.requestWizard;
  if (!wiz) return {};
  const { files, ...rest } = wiz.data || {};
  return { ...rest, _step: wiz.currentStep };
}

// Автосохранение черновика
function autosave() {
  if (IS_DEMO_USER) {
    return;
  }
  const snapshot = currentFormSnapshot();
  const hasData =
    snapshot.object ||
    (snapshot.contractors && snapshot.contractors.length > 0) ||
    (snapshot.manufacturers && snapshot.manufacturers.length > 0) ||
    (snapshot.comment && snapshot.comment.trim().length > 0);

  if (!hasData) {
    return;
  }

  writeDraft({ data: snapshot });
}

// Восстановление данных из снимка
function restoreFromSnapshot(data) {
  const wiz = window.requestWizard;
  if (!wiz) return;
  wiz.data.object = data.object || null;
  wiz.data.contractors = data.contractors || [];
  wiz.data.manufacturers = data.manufacturers || [];
  wiz.data.comment = data.comment || '';
}

// Модалка восстановления черновика
function ensureRestoreModal() {
  const root = document.getElementById('restore-draft-modal-root');
  if (!root) return;
  root.innerHTML = `
    <div class="modal fade" id="restoreDraftModal" tabindex="-1">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">Восстановить черновик?</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Закрыть"></button>
          </div>
          <div class="modal-body">
            Найдена неотправленная заявка. Восстановить заполненные данные и перейти к последнему шагу?
          </div>
          <div class="modal-footer">
            <button id="restore-draft-decline" class="btn btn-secondary" data-bs-dismiss="modal">Нет</button>
            <button id="restore-draft-confirm" class="btn btn-primary">Восстановить</button>
          </div>
        </div>
      </div>
    </div>`;
  const modalEl = document.getElementById('restoreDraftModal');
  const modal = new bootstrap.Modal(modalEl);
  let restored = false;
  modal.show();

  document
    .getElementById('restore-draft-confirm')
    .addEventListener('click', () => {
      const draft = readDraft();
      const wizard = window.requestWizard;
      if (draft?.data && wizard) {
        restoreFromSnapshot(draft.data);
        if (wizard.goToStep) {
          clearTimeout(wizard.startTimer);
          wizard.goToStep(draft.data._step || 0);
        }
      }
      restored = true;
      modal.hide();
    });

  const declineBtn = document.getElementById('restore-draft-decline');
  if (declineBtn) {
    declineBtn.addEventListener('click', () => {
      clearDraft();
    });
  }

  modalEl.addEventListener('hidden.bs.modal', () => {
    autosaveEnabled = true;
    if (!restored) {
      clearDraft();
    }
  });
}

// нициализация мастера и восстановление черновика
document.addEventListener('DOMContentLoaded', () => {
  console.log('нициализация страницы создания заявки');

  const wizardContainer = document.getElementById('request-wizard');
  if (wizardContainer) {
    window.requestWizard = new RequestWizard('request-wizard');
    const wizard = window.requestWizard;

    // Читаем черновик до подключения обработчиков
    const draft = readDraft();
    // Предложить восстановление только если не копируем заявку
    if (draft?.data && !window.COPY_REQUEST_DATA) {
      autosaveEnabled = false;
      ensureRestoreModal();
    }

    // Флаг запуска автосохранения и пропуск первого шага
    let autosaveStarted = false;
    let initialStep = true;

    // Обработчик изменений формы
    const handleChange = () => {
      if (!autosaveEnabled) return;
      if (!autosaveStarted) {
        autosaveStarted = true;
      }
      autosave();
    };

    document.addEventListener('input', handleChange);
    document.addEventListener('change', handleChange);

    wizard.onStepChange(() => {
      if (initialStep) {
        initialStep = false;
        return;
      }
      if (!autosaveEnabled) return;
      if (!autosaveStarted) {
        autosaveStarted = true;
      }
      autosave();
    });
  } else {
    console.error('Контейнер мастера не найден');
  }
});

// Предупреждение при уходе со страницы, если есть черновик
if (!IS_DEMO_USER) {
  window.addEventListener('beforeunload', (e) => {
    const draft = readDraft();
    if (draft?.data) {
      e.preventDefault();
      e.returnValue = '';
    }
  });
}

// ===== КЛАССЫ ШАГОВ МАСТЕРА =====

/**
 * Шаг 1: Выбор объекта
 */
class ObjectStep extends WizardStep {
  createElement() {
    const div = document.createElement('div');
    div.className = 'wizard-step';
    div.innerHTML = `
            <div class="wizard-field">
                <label class="form-label">Введите объект</label>
                <input type="text" class="form-control" id="wizard-object-input" 
                       placeholder="Начните вводить название объекта..." 
                       autocomplete="off" spellcheck="false">
                <div class="wizard-suggestions" id="wizard-object-suggestions"></div>
            </div>
            <div class="wizard-buttons">
                <button type="button" class="wizard-btn wizard-btn-secondary" id="object-back-btn">Назад</button>
                <button type="button" class="wizard-btn wizard-btn-primary" id="object-next-btn" disabled>Далее</button>
            </div>
        `;
    return div;
  }

  onShow() {
    const input = this.element.querySelector('#wizard-object-input');
    const suggestions = this.element.querySelector(
      '#wizard-object-suggestions'
    );
    const nextBtn = this.element.querySelector('#object-next-btn');
    const backBtn = this.element.querySelector('#object-back-btn');
    if (backBtn) {
      backBtn.style.display =
        this.wizard.currentStepIndex > 0 ? 'inline-block' : 'none';
      backBtn.onclick = () => this.wizard.prevStep();
    }

    // Автокомплит для объектов
    let searchTimeout;
    let activeIndex = -1;

    function updateActive(items) {
      items.forEach((item, index) => {
        if (index === activeIndex) {
          item.classList.add('active');
        } else {
          item.classList.remove('active');
        }
      });
    }
    input.addEventListener('input', () => {
      clearTimeout(searchTimeout);
      const query = input.value.trim();

      if (query.length < 1) {
        suggestions.innerHTML = '';
        suggestions.style.display = 'none';
        nextBtn.disabled = true;
        activeIndex = -1;
        return;
      }

      searchTimeout = setTimeout(() => {
        activeIndex = -1;
        this.performObjectSearch(query, input, suggestions, nextBtn);
      }, 150);
    });

    input.addEventListener('keydown', (e) => {
      const items = suggestions.querySelectorAll('.wizard-suggestion-item');
      if (!items.length) return;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        activeIndex = (activeIndex + 1) % items.length;
        updateActive(items);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        activeIndex = (activeIndex - 1 + items.length) % items.length;
        updateActive(items);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (activeIndex >= 0) {
          items[activeIndex].click();
        }
      } else if (e.key === 'Escape') {
        suggestions.innerHTML = '';
        suggestions.style.display = 'none';
        activeIndex = -1;
      }
    });

    // Обработчик кнопки "Далее"
    nextBtn.addEventListener('click', () => {
      this.wizard.nextStep();
    });

    // Восстанавливаем сохранённое значение
    if (this.wizard.data.object) {
      input.value = this.wizard.data.object.name;
      input.dataset.selectedId = this.wizard.data.object.id;
      nextBtn.disabled = false;
    }

    // Фокус на поле ввода
    setTimeout(() => input.focus(), 100);
  }

  performObjectSearch(query, input, suggestions, nextBtn) {
    // Объекты могут приходить в виде словаря: преобразуем к массиву
    const raw = this.wizard.cache.objects;
    const list = Array.isArray(raw)
      ? raw
      : raw && typeof raw === 'object'
        ? Object.values(raw)
        : [];
    const q = String(query || '').toLowerCase();
    const results = list
      .filter(
        (obj) =>
          obj &&
          typeof obj.name === 'string' &&
          obj.name.toLowerCase().includes(q)
      )
      .slice(0, 5);

    suggestions.innerHTML = '';

    if (results.length > 0) {
      results.forEach((item) => {
        const div = document.createElement('div');
        div.className = 'wizard-suggestion-item';
        div.textContent = item.name;
        div.addEventListener('click', () => {
          input.value = item.name;
          input.dataset.selectedId = item.id;
          suggestions.innerHTML = '';
          suggestions.style.display = 'none';
          nextBtn.disabled = false;
          this.wizard.data.object = { id: item.id, name: item.name };
          this.wizard.saveToLocalStorage();
          activeIndex = -1;
        });
        suggestions.appendChild(div);
      });
    }

    // Опция создания нового
    if (query.trim() !== '') {
      const createDiv = document.createElement('div');
      createDiv.className = 'wizard-suggestion-item create-new';
      createDiv.textContent = `Создать "${query}"`;
      createDiv.addEventListener('click', async () => {
        await this.createNewObject(query, input, suggestions, nextBtn);
      });
      suggestions.appendChild(createDiv);
    }

    suggestions.style.display = 'block';
  }

  async createNewObject(name, input, suggestions, nextBtn) {
    try {
      const formData = new FormData();
      formData.append('name', name);
      formData.append('csrf_token', window.CSRF_TOKEN);

      const headers = {
        'X-Requested-With': 'XMLHttpRequest',
        Accept: 'application/json',
      };
      if (window.CSRF_TOKEN) {
        headers['X-CSRFToken'] = window.CSRF_TOKEN;
      }

      const response = await fetchRetry(window.CRM_URLS.ADD_OBJECT, {
        method: 'POST',
        body: formData,
        headers,
      });

      const contentType = response.headers.get('Content-Type') || '';
      if (!contentType.includes('application/json')) {
        const preview = (await response.text()).slice(0, 120);
        throw new Error(
          `Неожиданный ответ сервера. ${preview ? `(${preview})` : ''}`.trim()
        );
      }

      const payload = await response.json();

      if (!response.ok) {
        if (payload?.demo_mode) {
          throw new Error('В демо-режиме создание объектов недоступно.');
        }
        throw new Error(payload?.error || 'Ошибка создания объекта');
      }

      const newObject = payload;
      input.value = newObject.name;
      input.dataset.selectedId = newObject.id;
      suggestions.innerHTML = '';
      suggestions.style.display = 'none';
      nextBtn.disabled = false;

      // Сохраняем выбор объекта
      this.wizard.data.object = { id: newObject.id, name: newObject.name };
      this.wizard.saveToLocalStorage();

      // Добавляем в кэш
      if (!Array.isArray(this.wizard.cache.objects)) {
        this.wizard.cache.objects = [];
      }
      this.wizard.cache.objects.push(newObject);
    } catch (error) {
      console.error('Ошибка создания объекта:', error);
      alert('Ошибка создания объекта: ' + error.message);
    }
  }

  async validate() {
    const input = this.element.querySelector('#wizard-object-input');
    return input.value.trim() !== '' && input.dataset.selectedId;
  }

  async saveData() {
    const input = this.element.querySelector('#wizard-object-input');
    this.wizard.data.object = {
      id: input.dataset.selectedId,
      name: input.value.trim(),
    };
    this.wizard.saveToLocalStorage();
  }
}

/**
 * Шаг 2: Выбор подрядчиков
 */
class ContractorStep extends WizardStep {
  constructor(wizard) {
    super(wizard);
    this.selectedContractors = [];
  }

  createElement() {
    const div = document.createElement('div');
    div.className = 'wizard-step';
    div.innerHTML = `
            <div class="wizard-field">
                <label class="form-label">Введите подрядчика</label>
                <input type="text" class="form-control" id="wizard-contractor-input" 
                       placeholder="Начните вводить название подрядчика..." 
                       autocomplete="off" spellcheck="false">
                <div class="wizard-suggestions" id="wizard-contractor-suggestions"></div>
            </div>
            <div id="selected-contractors" class="mt-3"></div>
            <div class="wizard-buttons">
                <button type="button" class="wizard-btn wizard-btn-secondary" id="contractor-back-btn">Назад</button>
                <button type="button" class="wizard-btn wizard-btn-success" id="add-contractor-btn" disabled>Добавить подрядчика</button>
                <button type="button" class="wizard-btn wizard-btn-primary" id="contractor-next-btn" disabled>Далее</button>
            </div>
        `;
    return div;
  }

  onShow() {
    const input = this.element.querySelector('#wizard-contractor-input');
    const suggestions = this.element.querySelector(
      '#wizard-contractor-suggestions'
    );
    const addBtn = this.element.querySelector('#add-contractor-btn');
    const nextBtn = this.element.querySelector('#contractor-next-btn');
    const selectedContainer = this.element.querySelector(
      '#selected-contractors'
    );
    const backBtn = this.element.querySelector('#contractor-back-btn');
    if (backBtn) {
      backBtn.onclick = () => this.wizard.prevStep();
    }

    // Автокомплит для подрядчиков
    let searchTimeout;
    input.addEventListener('input', () => {
      clearTimeout(searchTimeout);
      const query = input.value.trim();

      if (query.length < 1) {
        suggestions.innerHTML = '';
        suggestions.style.display = 'none';
        addBtn.disabled = true;
        return;
      }

      searchTimeout = setTimeout(() => {
        this.performContractorSearch(query, input, suggestions, addBtn);
      }, 150);
    });

    // Обработчик кнопки "Добавить подрядчика"
    addBtn.addEventListener('click', () => {
      this.addSelectedContractor(
        input,
        suggestions,
        addBtn,
        nextBtn,
        selectedContainer
      );
    });

    // Обработчик кнопки "Далее"
    nextBtn.addEventListener('click', () => {
      this.wizard.nextStep();
    });

    // Enter для добавления подрядчика
    input.addEventListener('keypress', (e) => {
      if (e.key === 'Enter' && !addBtn.disabled) {
        e.preventDefault();
        addBtn.click();
      }
    });

    // Восстанавливаем ранее выбранных подрядчиков
    if (this.wizard.data.contractors.length > 0) {
      this.selectedContractors = [...this.wizard.data.contractors];
      this.updateSelectedContractorsList(selectedContainer, nextBtn);
    }

    setTimeout(() => input.focus(), 100);
  }

  performContractorSearch(query, input, suggestions, addBtn) {
    // Подрядчики могут приходить в виде словаря: приводим к массиву
    const raw = this.wizard.cache.contractors;
    const list = Array.isArray(raw)
      ? raw
      : raw && typeof raw === 'object'
        ? Object.values(raw)
        : [];
    const q = String(query || '').toLowerCase();
    const results = list
      .filter(
        (contractor) =>
          contractor &&
          typeof contractor.name === 'string' &&
          contractor.name.toLowerCase().includes(q) &&
          !this.selectedContractors.find((sc) => sc.id === contractor.id)
      )
      .slice(0, 5);

    suggestions.innerHTML = '';

    if (results.length > 0) {
      results.forEach((item) => {
        const div = document.createElement('div');
        div.className = 'wizard-suggestion-item';
        div.textContent = item.name;
        div.addEventListener('click', () => {
          input.value = item.name;
          input.dataset.selectedId = item.id;
          suggestions.innerHTML = '';
          suggestions.style.display = 'none';
          addBtn.disabled = false;
        });
        suggestions.appendChild(div);
      });
    }

    // Опция создания нового
    if (query.trim() !== '') {
      const createDiv = document.createElement('div');
      createDiv.className = 'wizard-suggestion-item create-new';
      createDiv.textContent = `Создать "${query}"`;
      createDiv.addEventListener('click', async () => {
        await this.createNewContractor(query, input, suggestions, addBtn);
      });
      suggestions.appendChild(createDiv);
    }

    suggestions.style.display = 'block';
  }

  async createNewContractor(name, input, suggestions, addBtn) {
    try {
      const formData = new FormData();
      formData.append('name', name);
      formData.append('csrf_token', window.CSRF_TOKEN);

      const headers = {
        'X-Requested-With': 'XMLHttpRequest',
        Accept: 'application/json',
      };
      if (window.CSRF_TOKEN) {
        headers['X-CSRFToken'] = window.CSRF_TOKEN;
      }

      const response = await fetchRetry(window.CRM_URLS.ADD_CONTRACTOR, {
        method: 'POST',
        body: formData,
        headers,
      });

      const contentType = response.headers.get('Content-Type') || '';
      if (!contentType.includes('application/json')) {
        const preview = (await response.text()).slice(0, 120);
        throw new Error(
          `Неожиданный ответ сервера. ${preview ? `(${preview})` : ''}`.trim()
        );
      }

      const payload = await response.json();

      if (!response.ok) {
        if (payload?.demo_mode) {
          throw new Error('В демо-режиме создание подрядчиков недоступно.');
        }
        throw new Error(payload?.error || 'Ошибка создания подрядчика');
      }

      const newContractor = payload;
      input.value = newContractor.name;
      input.dataset.selectedId = newContractor.id;
      suggestions.innerHTML = '';
      suggestions.style.display = 'none';
      addBtn.disabled = false;

      // Добавляем в кэш
      this.wizard.cache.contractors.push(newContractor);
    } catch (error) {
      console.error('Ошибка создания подрядчика:', error);
      alert('Ошибка создания подрядчика: ' + error.message);
    }
  }

  addSelectedContractor(
    input,
    suggestions,
    addBtn,
    nextBtn,
    selectedContainer
  ) {
    const contractorData = {
      id: input.dataset.selectedId,
      name: input.value.trim(),
    };

    this.selectedContractors.push(contractorData);
    this.updateSelectedContractorsList(selectedContainer, nextBtn);
    this.wizard.data.contractors = [...this.selectedContractors];
    this.wizard.saveToLocalStorage();

    // Очищаем поле ввода
    input.value = '';
    delete input.dataset.selectedId;
    addBtn.disabled = true;
    suggestions.innerHTML = '';
    suggestions.style.display = 'none';

    setTimeout(() => input.focus(), 100);
  }

  updateSelectedContractorsList(container, nextBtn) {
    container.innerHTML = '';

    if (this.selectedContractors.length > 0) {
      const title = document.createElement('h6');
      title.textContent = 'Выбранные подрядчики:';
      container.appendChild(title);

      this.selectedContractors.forEach((contractor, index) => {
        const item = document.createElement('div');
        item.className = 'selected-file-item';
        item.innerHTML = `
                    <span class="selected-file-name">${contractor.name}</span>
                    <button type="button" class="remove-file-btn" data-index="${index}">
                        ✕
                    </button>
                `;

        item.querySelector('.remove-file-btn').addEventListener('click', () => {
          this.removeContractor(index, container, nextBtn);
        });

        container.appendChild(item);
      });

      nextBtn.disabled = false;
    } else {
      nextBtn.disabled = true;
    }
  }

  removeContractor(index, container, nextBtn) {
    this.selectedContractors.splice(index, 1);
    this.updateSelectedContractorsList(container, nextBtn);
    this.wizard.data.contractors = [...this.selectedContractors];
    this.wizard.saveToLocalStorage();
  }

  async validate() {
    return this.selectedContractors.length > 0;
  }

  async saveData() {
    this.wizard.data.contractors = [...this.selectedContractors];
    this.wizard.saveToLocalStorage();
  }
}

/**
 * Шаг 3: Выбор производителей
 */
class ManufacturerStep extends WizardStep {
  constructor(wizard) {
    super(wizard);
    this.selectedManufacturers = [];
  }

  createElement() {
    const div = document.createElement('div');
    div.className = 'wizard-step';
    div.style.minWidth = '600px';
    div.innerHTML = `
            <div class="wizard-field">
                <label class="form-label">Выберите производителей</label>
                <div class="wizard-manufacturers" id="wizard-manufacturers"></div>
            </div>
            <div class="wizard-buttons">
                <button type="button" class="wizard-btn wizard-btn-secondary" id="manufacturer-back-btn">Назад</button>
                <button type="button" class="wizard-btn wizard-btn-primary" id="manufacturer-next-btn" disabled>Далее</button>
            </div>
        `;
    return div;
  }

  onShow() {
    const container = this.element.querySelector('#wizard-manufacturers');
    const nextBtn = this.element.querySelector('#manufacturer-next-btn');
    const backBtn = this.element.querySelector('#manufacturer-back-btn');
    if (backBtn) {
      backBtn.onclick = () => this.wizard.prevStep();
    }

    // Создаем чекбоксы для производителей
    this.wizard.cache.manufacturers.forEach((manufacturer, index) => {
      const item = document.createElement('div');
      item.className = 'wizard-manufacturer-item';
      item.innerHTML = `
                <input type="checkbox" id="mfg_${index}" value="${manufacturer}">
                <label for="mfg_${index}">${manufacturer}</label>
            `;

      const checkbox = item.querySelector('input[type="checkbox"]');
      checkbox.addEventListener('change', () => {
        this.updateSelectedManufacturers(nextBtn);
      });

      // Восстанавливаем выбор
      if (this.wizard.data.manufacturers.includes(manufacturer)) {
        checkbox.checked = true;
      }

      container.appendChild(item);

      // Анимация появления с задержкой
      setTimeout(() => {
        item.classList.add('animate-in');
      }, index * 50);
    });

    // Обновляем состояние после восстановления
    if (this.wizard.data.manufacturers.length > 0) {
      this.updateSelectedManufacturers(nextBtn);
    }

    // Делаем элементы кликабельными
    container.addEventListener('click', (e) => {
      if (e.target.classList.contains('wizard-manufacturer-item')) {
        const checkbox = e.target.querySelector('input[type="checkbox"]');
        checkbox.checked = !checkbox.checked;
        checkbox.dispatchEvent(new Event('change'));
      }
    });

    nextBtn.addEventListener('click', () => {
      this.wizard.nextStep();
    });
  }

  updateSelectedManufacturers(nextBtn) {
    const checkboxes = this.element.querySelectorAll(
      'input[type="checkbox"]:checked'
    );
    this.selectedManufacturers = Array.from(checkboxes).map((cb) => cb.value);
    this.wizard.data.manufacturers = [...this.selectedManufacturers];
    this.wizard.saveToLocalStorage();

    // Обновляем стили выбранных элементов
    this.element
      .querySelectorAll('.wizard-manufacturer-item')
      .forEach((item) => {
        const checkbox = item.querySelector('input[type="checkbox"]');
        if (checkbox.checked) {
          item.classList.add('selected');
        } else {
          item.classList.remove('selected');
        }
      });

    nextBtn.disabled = this.selectedManufacturers.length === 0;
  }

  async validate() {
    return this.selectedManufacturers.length > 0;
  }

  async saveData() {
    this.wizard.data.manufacturers = [...this.selectedManufacturers];
    this.wizard.saveToLocalStorage();
  }
}

/**
 * Шаг 4: Финальный шаг с размещением полей и отправкой
 */
class FinalStep extends WizardStep {
  createElement() {
    const div = document.createElement('div');
    div.className = 'wizard-step final-step'; // Added final-step class
    // Removed hard-coded width constraints for mobile compatibility
    div.innerHTML = `
            <div class="final-form-container">
                <div class="form-group" data-field="object">
                    <label class="form-label">Объект</label>
                    <input type="text" class="form-control" readonly>
                </div>
                <div class="form-group" data-field="contractors">
                    <label class="form-label">Подрядчики</label>
                    <div class="contractors-list"></div>
                </div>
                <div class="form-group" data-field="manufacturers">
                    <label class="form-label">Производители</label>
                    <div class="manufacturers-list"></div>
                </div>
                <div class="form-group" data-field="comment">
                    <label class="form-label">Комментарий (необязательно)</label>
                    <textarea class="form-control" rows="3" placeholder="Дополнительная информация по заявке"></textarea>
                </div>
                <div class="form-group" data-field="files" style="grid-column: 1 / -1;">
                    <label class="form-label">Файлы</label>
                    <div class="file-drop-zone" id="final-file-drop-zone">
                        <div class="upload-icon">📁</div>
                        <div class="upload-text">Перетащите файлы сюда или нажмите для выбора</div>
                        <input type="file" multiple style="display: none;" id="final-file-input">
                    </div>
                    <div class="selected-files-list" id="final-selected-files"></div>
                </div>
            </div>
            <div class="wizard-buttons">
                <button type="button" class="wizard-btn wizard-btn-secondary" id="final-back-btn">Назад</button>
                <button type="button" class="wizard-btn wizard-btn-primary" id="submit-request-btn">Создать заявку</button>
            </div>
        `;
    return div;
  }

  onShow() {
    const backBtn = this.element.querySelector('#final-back-btn');
    if (backBtn) {
      backBtn.onclick = () => this.wizard.prevStep();
    }

    this.populateFields();
    this.setupFileHandling();
    this.setupSubmitButton();
    this.animateFieldsToPosition();
  }

  populateFields() {
    // Заполняем объект
    const objectInput = this.element.querySelector(
      '[data-field="object"] input'
    );
    objectInput.value =
      this.wizard.data.object && this.wizard.data.object.name
        ? this.wizard.data.object.name
        : '';

    // Заполняем подрядчиков
    const contractorsList = this.element.querySelector('.contractors-list');
    const contractorsArr = Array.isArray(this.wizard.data.contractors)
      ? this.wizard.data.contractors
      : [];
    contractorsList.innerHTML = contractorsArr
      .map((c) => `<span class="badge bg-primary me-1">${c.name}</span>`)
      .join('');

    // Заполняем производителей
    const manufacturersList = this.element.querySelector('.manufacturers-list');
    const manufacturersArr = Array.isArray(this.wizard.data.manufacturers)
      ? this.wizard.data.manufacturers
      : [];
    manufacturersList.innerHTML = manufacturersArr
      .map((m) => `<span class="badge bg-secondary me-1">${m}</span>`)
      .join('');

    // Заполняем комментарий
    const commentTextarea = this.element.querySelector(
      '[data-field="comment"] textarea'
    );
    commentTextarea.value = this.wizard.data.comment || '';
  }

  setupFileHandling() {
    const dropZone = this.element.querySelector('#final-file-drop-zone');
    const fileInput = this.element.querySelector('#final-file-input');

    // Enhanced mobile file handling
    if (this.wizard.isMobile) {
      this.setupMobileFileHandling(dropZone, fileInput);
    } else {
      this.setupDesktopFileHandling(dropZone, fileInput);
    }

    // Common file input handler
    fileInput.addEventListener('change', (e) => {
      const files = Array.from(e.target.files);
      this.wizard.addFiles(files);
      e.target.value = ''; // Reset for reuse
    });

    // Update files list
    this.updateFilesList();
  }

  setupMobileFileHandling(dropZone, fileInput) {
    // Enhance drop zone for mobile
    dropZone.innerHTML = `
            <div class="upload-icon" style="font-size: 2.5rem; margin-bottom: 1rem;">
                <i class="bi bi-cloud-upload" aria-hidden="true"></i>
            </div>
            <div class="upload-text" style="font-size: 1.1rem; margin-bottom: 1rem;">
                Выберите файлы для загрузки
            </div>
            <button type="button" class="btn btn-primary btn-lg mobile-file-btn" style="min-height: 48px;">
                <i class="bi bi-folder2-open me-2"></i>Выбрать файлы
            </button>
            <div class="mt-2">
                <small class="text-muted">Максимум 50MB на файл</small>
            </div>
        `;

    // Add mobile-specific styling
    dropZone.style.padding = '2rem 1rem';
    dropZone.style.minHeight = '180px';
    dropZone.style.textAlign = 'center';
    dropZone.style.display = 'flex';
    dropZone.style.flexDirection = 'column';
    dropZone.style.justifyContent = 'center';
    dropZone.style.alignItems = 'center';
    dropZone.style.borderRadius = '12px';
    dropZone.style.border = '2px dashed var(--gray-300)';
    dropZone.style.background = 'var(--gray-50)';
    dropZone.style.transition = 'all 0.3s ease';

    // Mobile file selection button
    const mobileBtn = dropZone.querySelector('.mobile-file-btn');
    mobileBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      fileInput.click();
    });

    // Enhanced touch feedback
    dropZone.addEventListener(
      'touchstart',
      () => {
        dropZone.style.transform = 'scale(0.98)';
        dropZone.style.background = 'var(--info-light)';
      },
      { passive: true }
    );

    dropZone.addEventListener(
      'touchend',
      () => {
        dropZone.style.transform = 'scale(1)';
        dropZone.style.background = 'var(--gray-50)';
      },
      { passive: true }
    );

    // Alternative click handler for the entire drop zone
    dropZone.addEventListener('click', (e) => {
      if (!e.target.closest('.mobile-file-btn')) {
        fileInput.click();
      }
    });

    // Camera capture for mobile (if supported)
    if ('capture' in fileInput && navigator.mediaDevices) {
      this.addCameraOption(dropZone, fileInput);
    }
  }

  setupDesktopFileHandling(dropZone, fileInput) {
    dropZone.addEventListener('click', () => {
      fileInput.click();
    });

    // Drag & Drop handlers
    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', () => {
      dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.classList.remove('drag-over');
      const files = Array.from(e.dataTransfer.files);
      this.wizard.addFiles(files);
    });
  }

  addCameraOption(dropZone, fileInput) {
    // Add camera capture button for mobile devices
    const cameraBtn = document.createElement('button');
    cameraBtn.type = 'button';
    cameraBtn.className = 'btn btn-outline-primary btn-lg mt-2';
    cameraBtn.style.minHeight = '48px';
    cameraBtn.innerHTML = '<i class="bi bi-camera me-2"></i>Сделать фото';

    cameraBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      // Create a separate file input for camera
      const cameraInput = document.createElement('input');
      cameraInput.type = 'file';
      cameraInput.accept = 'image/*';
      cameraInput.capture = 'environment'; // Use back camera
      cameraInput.style.display = 'none';

      cameraInput.addEventListener('change', (e) => {
        const files = Array.from(e.target.files);
        this.wizard.addFiles(files);
        document.body.removeChild(cameraInput);
      });

      document.body.appendChild(cameraInput);
      cameraInput.click();
    });

    dropZone.appendChild(cameraBtn);
  }

  updateFilesList() {
    const container = this.element.querySelector('#final-selected-files');

    if (this.wizard.data.files.length === 0) {
      container.innerHTML =
        '<small class="text-muted">Файлы не выбраны</small>';
      return;
    }

    const isMobile = this.wizard.isMobile;

    container.innerHTML = this.wizard.data.files
      .map((file, index) => {
        const isImage = file.type.startsWith('image/');
        const iconClass = this.getFileIcon(file.type);

        return `
                <div class="selected-file-item ${
                  isMobile ? 'mobile-file-item' : ''
                }" data-index="${index}">
                    <div class="file-info d-flex align-items-center">
                        ${
                          isImage && isMobile
                            ? `<div class="file-preview me-2">
                                <img src="${URL.createObjectURL(
                                  file
                                )}" alt="Preview" 
                                     style="width: 40px; height: 40px; object-fit: cover; border-radius: 4px;">
                            </div>`
                            : `<i class="${iconClass} me-2 text-primary" style="font-size: 1.2rem;"></i>`
                        }
                        <div class="file-details flex-grow-1">
                            <div class="selected-file-name ${
                              isMobile ? 'fw-semibold' : ''
                            }">${file.name}</div>
                            <small class="selected-file-size text-muted">${this.formatFileSize(
                              file.size
                            )}</small>
                            ${
                              isMobile && file.lastModified
                                ? `<small class="text-muted d-block">Добавлен: ${new Date(
                                    file.lastModified
                                  ).toLocaleTimeString()}</small>`
                                : ''
                            }
                        </div>
                    </div>
                    <button type="button" class="remove-file-btn ${
                      isMobile ? 'btn btn-sm btn-outline-danger' : ''
                    }" 
                            data-index="${index}" aria-label="Удалить файл ${
                              file.name
                            }">
                        ${isMobile ? '<i class="bi bi-trash"></i>' : '✕'}
                    </button>
                </div>
            `;
      })
      .join('');

    // Add remove handlers with enhanced mobile support
    container.querySelectorAll('.remove-file-btn').forEach((btn) => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const index = parseInt(btn.dataset.index);

        if (isMobile) {
          // Подтверждение удаления на мобильных
          if (await customConfirm('Удалить этот файл?')) {
            this.wizard.removeFile(index);
          }
        } else {
          this.wizard.removeFile(index);
        }
      });

      // Enhanced mobile touch feedback
      if (isMobile) {
        btn.addEventListener(
          'touchstart',
          () => {
            btn.style.transform = 'scale(0.95)';
          },
          { passive: true }
        );

        btn.addEventListener(
          'touchend',
          () => {
            btn.style.transform = 'scale(1)';
          },
          { passive: true }
        );
      }
    });

    // Add file preview functionality for mobile
    if (isMobile) {
      container.querySelectorAll('.selected-file-item').forEach((item) => {
        item.addEventListener('click', (e) => {
          if (!e.target.closest('.remove-file-btn')) {
            const index = parseInt(item.dataset.index);
            this.showFilePreview(this.wizard.data.files[index]);
          }
        });
      });
    }
  }

  getFileIcon(fileType) {
    if (fileType.startsWith('image/')) return 'bi bi-file-earmark-image';
    if (fileType.includes('pdf')) return 'bi bi-file-earmark-pdf';
    if (fileType.includes('word') || fileType.includes('document'))
      return 'bi bi-file-earmark-word';
    if (fileType.includes('text')) return 'bi bi-file-earmark-text';
    if (fileType.includes('excel') || fileType.includes('spreadsheet'))
      return 'bi bi-file-earmark-excel';
    return 'bi bi-file-earmark';
  }

  showFilePreview(file) {
    if (!file.type.startsWith('image/')) {
      // For non-image files, just show info
      alert(
        `Файл: ${file.name}\nРазмер: ${this.formatFileSize(file.size)}\nТип: ${
          file.type
        }`
      );
      return;
    }

    // Create modal for image preview
    const modal = document.createElement('div');
    modal.className = 'modal fade show';
    modal.style.display = 'block';
    modal.style.backgroundColor = 'rgba(0,0,0,0.8)';
    modal.innerHTML = `
            <div class="modal-dialog modal-lg modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">${file.name}</h5>
                        <button type="button" class="btn-close" aria-label="Закрыть"></button>
                    </div>
                    <div class="modal-body text-center">
                        <img src="${URL.createObjectURL(
                          file
                        )}" class="img-fluid" 
                             style="max-height: 70vh; border-radius: 8px;">
                        <div class="mt-2">
                            <small class="text-muted">Размер: ${this.formatFileSize(
                              file.size
                            )}</small>
                        </div>
                    </div>
                </div>
            </div>
        `;

    // Close handlers
    const closeModal = () => {
      URL.revokeObjectURL(modal.querySelector('img').src);
      document.body.removeChild(modal);
    };

    modal.querySelector('.btn-close').addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });

    document.body.appendChild(modal);
  }

  setupSubmitButton() {
    const submitBtn = this.element.querySelector('#submit-request-btn');
    const commentTextarea = this.element.querySelector(
      '[data-field="comment"] textarea'
    );

    // Сохраняем комментарий при изменении
    commentTextarea.addEventListener('input', () => {
      this.wizard.data.comment = commentTextarea.value.trim();
      this.wizard.saveToLocalStorage();
    });

    submitBtn.addEventListener('click', async () => {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Создание заявки...';

      const success = await this.wizard.nextStep();

      if (!success) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Создать заявку';
      }
    });
  }

  animateFieldsToPosition() {
    const formGroups = this.element.querySelectorAll('.form-group');

    formGroups.forEach((group, index) => {
      // Initial state - hidden and slightly below
      group.style.opacity = '0';
      group.style.transform = 'translateY(30px)';
      group.style.transition =
        'all var(--field-position-duration) var(--field-position-easing)';

      // Animate to final position with staggered timing
      setTimeout(() => {
        group.style.opacity = '1';
        group.style.transform = 'translateY(0)';

        setTimeout(() => {
          group.classList.add('animate-in');
        }, 100);
      }, index * 100);
    });
  }

  async validate() {
    return true; // Финальный шаг всегда валиден
  }

  async saveData() {
    // Данные уже сохранены в других методах
  }
}
