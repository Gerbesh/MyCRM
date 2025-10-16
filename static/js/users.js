'use strict';

(function () {
  function getConfig() {
    const addUserForm = document.getElementById('addUserForm');
    const resetModal = document.getElementById('resetPasswordModal');
    return {
      addUserUrl:
        (addUserForm && addUserForm.getAttribute('data-add-user-url')) ||
        '/user/add',
      resetUserPasswordBase:
        (resetModal &&
          resetModal.getAttribute('data-reset-user-password-base')) ||
        '/user/reset_password/',
    };
  }

  document.addEventListener('DOMContentLoaded', function () {
    const { addUserUrl, resetUserPasswordBase } = getConfig();

    const addUserForm = document.getElementById('addUserForm');
    if (addUserForm) {
      addUserForm.addEventListener('submit', function (e) {
        e.preventDefault();
        const username = (
          document.getElementById('newUsername') || {}
        ).value?.trim();
        const password = (document.getElementById('newPassword') || {}).value;
        const role = (document.getElementById('newRole') || {}).value;
        if (!username || !password || !role) {
          alert('Заполните все поля');
          return;
        }
        fetch(addUserUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': window.getCSRFToken ? window.getCSRFToken() : '',
          },
          body: JSON.stringify({ username, password, role }),
          credentials: 'same-origin',
        })
          .then((response) => {
            if (!response.ok) {
              return response.json().then((err) => {
                throw new Error((err && err.error) || 'Ошибка сервера');
              });
            }
            return response.json();
          })
          .then((data) => {
            if (data && data.success) {
              alert(
                `Пользователь "${username}" создан! Пароль: ${data.password}`
              );
              location.reload();
            } else {
              alert(
                'Ошибка: ' + ((data && data.error) || 'Неизвестная ошибка')
              );
            }
          })
          .catch((err) => {
            console.error('Error:', err);
            alert('Ошибка: ' + err.message);
          });
      });
    }

    const resetButtons = document.querySelectorAll('.reset-password');
    // eslint-disable-next-line no-undef
    const resetModal = new bootstrap.Modal(
      document.getElementById('resetPasswordModal')
    );
    const confirmResetBtn = document.getElementById('confirmResetPassword');
    let currentUserId = null;

    resetButtons.forEach((button) => {
      button.addEventListener('click', function () {
        currentUserId = this.dataset.userId;
        const usernameEl =
          this.closest('.card-body').querySelector('.card-title');
        const username = usernameEl ? usernameEl.textContent : '';
        const resetUsername = document.getElementById('resetUsername');
        if (resetUsername) resetUsername.textContent = username;
        resetModal.show();
      });
    });

    if (confirmResetBtn) {
      confirmResetBtn.addEventListener('click', function () {
        if (!currentUserId) return;
        confirmResetBtn.disabled = true;
        fetch(`${resetUserPasswordBase}${currentUserId}`, {
          method: 'POST',
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': window.getCSRFToken ? window.getCSRFToken() : '',
          },
        })
          .then((response) => {
            if (!response.ok) {
              return response.json().then((err) => {
                throw new Error((err && err.error) || 'Ошибка сервера');
              });
            }
            return response.json();
          })
          .then((data) => {
            resetModal.hide();
            alert(`Пароль сброшен! Новый пароль: ${data.new_password}`);
          })
          .catch((err) => {
            console.error('Error:', err);
            alert('Ошибка: ' + err.message);
          })
          .finally(() => {
            confirmResetBtn.disabled = false;
          });
      });
    }
  });
})();
