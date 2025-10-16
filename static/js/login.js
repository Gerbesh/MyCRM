// Скрипт для страницы авторизации: анимация и reCAPTCHA

document.addEventListener('DOMContentLoaded', function () {
  const body = document.body;
  const loginForm = document.getElementById('loginForm');
  const loginBtn = document.getElementById('loginBtn');
  const demoForm = document.getElementById('demoLoginForm');
  const demoBtn = document.getElementById('demoLoginBtn');
  const loginScreen = document.getElementById('loginScreen');
  const loginFormContainer = document.getElementById('loginFormContainer');
  const needRecaptcha = body.dataset.needRecaptcha === 'true';
  const recaptchaSiteKey = body.dataset.recaptchaSiteKey || '';

  function submitWithAnimation(form) {
    setTimeout(() => {
      loginFormContainer.classList.add('slide-out');
      setTimeout(() => {
        loginScreen.classList.add('fade-out');
        setTimeout(() => {
          form.submit();
        }, 400);
      }, 600);
    }, 1000);
  }

  loginForm.addEventListener('submit', function (e) {
    e.preventDefault();

    loginBtn.classList.add('loading');
    loginBtn.innerHTML = '<span class="spinner"></span>Вход...';

    if (
      needRecaptcha &&
      typeof grecaptcha !== 'undefined' &&
      recaptchaSiteKey
    ) {
      try {
        grecaptcha.ready(function () {
          grecaptcha
            .execute(recaptchaSiteKey, { action: 'login' })
            .then(function (token) {
              const input = document.getElementById('g-recaptcha-response');
              if (input) {
                input.value = token;
              }
              submitWithAnimation(loginForm);
            })
            .catch(function () {
              submitWithAnimation(loginForm);
            });
        });
      } catch (err) {
        submitWithAnimation(loginForm);
      }
    } else {
      submitWithAnimation(loginForm);
    }
  });

  if (demoForm && demoBtn) {
    demoForm.addEventListener('submit', function (event) {
      event.preventDefault();
      demoBtn.classList.add('loading');
      demoBtn.innerHTML = '<span class="spinner"></span>Демо-вход...';
      submitWithAnimation(demoForm);
    });
  }

  setTimeout(() => {
    document.getElementById('username').focus();
  }, 1000);

  const inputs = document.querySelectorAll('.form-control');
  inputs.forEach((input) => {
    input.addEventListener('focus', function () {
      this.parentElement.style.transform = 'scale(1.02)';
      this.parentElement.style.transition = 'transform 0.2s ease';
    });

    input.addEventListener('blur', function () {
      this.parentElement.style.transform = 'scale(1)';
    });
  });
});
