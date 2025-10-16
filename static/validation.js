/**
 * Client-side validation utilities for CRM application
 */

// Configuration
const VALIDATION_CONFIG = {
  maxFileSize: 10 * 1024 * 1024, // 10MB
  allowedExtensions: [
    'jpg',
    'jpeg',
    'png',
    'gif',
    'bmp',
    'webp',
    'pdf',
    'txt',
    'doc',
    'docx',
    'xls',
    'xlsx',
  ],
  dangerousExtensions: [
    'exe',
    'scr',
    'bat',
    'cmd',
    'com',
    'pif',
    'scf',
    'vbs',
    'js',
    'jar',
    'php',
    'asp',
    'aspx',
  ],
  maxFieldLengths: {
    username: 50,
    password: 255,
    name: 200,
    address: 300,
    phone: 20,
    email: 100,
    comment: 1000,
  },
};

/**
 * Validate file before upload
 * @param {File} file - File object to validate
 * @returns {Object} - {valid: boolean, errors: string[]}
 */
function validateFile(file) {
  const errors = [];

  if (!file) {
    errors.push('No file selected');
    return { valid: false, errors };
  }

  // Check file size
  if (file.size > VALIDATION_CONFIG.maxFileSize) {
    const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
    const maxMB = (VALIDATION_CONFIG.maxFileSize / (1024 * 1024)).toFixed(1);
    errors.push(`File size (${sizeMB}MB) exceeds maximum allowed (${maxMB}MB)`);
  }

  // Check file extension
  const extension = file.name.split('.').pop().toLowerCase();

  if (VALIDATION_CONFIG.dangerousExtensions.includes(extension)) {
    errors.push(`Dangerous file extension: .${extension}`);
  }

  if (!VALIDATION_CONFIG.allowedExtensions.includes(extension)) {
    errors.push(
      `File extension .${extension} is not allowed. Allowed: ${VALIDATION_CONFIG.allowedExtensions.join(
        ', '
      )}`
    );
  }

  // Check filename for dangerous characters
  if (
    file.name.includes('<') ||
    file.name.includes('>') ||
    file.name.includes('"') ||
    file.name.includes('|') ||
    file.name.includes('?') ||
    file.name.includes('*') ||
    file.name.includes('..') ||
    file.name.includes('/') ||
    file.name.includes('\\')
  ) {
    errors.push('Filename contains dangerous characters');
  }

  return { valid: errors.length === 0, errors };
}

/**
 * Validate text input field
 * @param {string} value - Input value
 * @param {Object} rules - Validation rules
 * @returns {Object} - {valid: boolean, errors: string[]}
 */
function validateTextInput(value, rules = {}) {
  const errors = [];

  // Required field check
  if (rules.required && (!value || value.trim() === '')) {
    errors.push(`${rules.fieldName || 'Field'} is required`);
    return { valid: false, errors };
  }

  if (value && value.trim() !== '') {
    const trimmedValue = value.trim();

    // Length validation
    if (rules.maxLength && trimmedValue.length > rules.maxLength) {
      errors.push(
        `${rules.fieldName || 'Field'} must be no more than ${
          rules.maxLength
        } characters`
      );
    }

    if (rules.minLength && trimmedValue.length < rules.minLength) {
      errors.push(
        `${rules.fieldName || 'Field'} must be at least ${
          rules.minLength
        } characters`
      );
    }

    // Pattern validation
    if (rules.pattern && !rules.pattern.test(trimmedValue)) {
      errors.push(`${rules.fieldName || 'Field'} format is invalid`);
    }

    // Check for dangerous characters (basic XSS prevention)
    if (
      trimmedValue.includes('<script') ||
      trimmedValue.includes('javascript:') ||
      trimmedValue.includes('vbscript:') ||
      trimmedValue.includes('onload=') ||
      trimmedValue.includes('onerror=') ||
      trimmedValue.includes('onclick=')
    ) {
      errors.push(
        `${rules.fieldName || 'Field'} contains potentially dangerous content`
      );
    }
  }

  return { valid: errors.length === 0, errors };
}

/**
 * Validate email format
 * @param {string} email - Email to validate
 * @returns {Object} - {valid: boolean, errors: string[]}
 */
function validateEmail(email) {
  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const errors = [];

  if (email && !emailPattern.test(email)) {
    errors.push('Invalid email format');
  }

  return { valid: errors.length === 0, errors };
}

/**
 * Validate phone number
 * @param {string} phone - Phone number to validate
 * @returns {Object} - {valid: boolean, errors: string[]}
 */
function validatePhone(phone) {
  const phonePattern = /^[\d\s\-\+\(\)]+$/;
  const errors = [];

  if (phone && !phonePattern.test(phone)) {
    errors.push(
      'Phone number can only contain digits, spaces, hyphens, plus signs, and parentheses'
    );
  }

  return { valid: errors.length === 0, errors };
}

/**
 * Display validation errors in UI
 * @param {string} fieldId - Field identifier
 * @param {string[]} errors - Array of error messages
 */
function displayFieldErrors(fieldId, errors) {
  const field = document.getElementById(fieldId);
  if (!field) return;

  // Remove existing error display
  const existingError = field.parentNode.querySelector('.validation-error');
  if (existingError) {
    existingError.remove();
  }

  // Remove error class
  field.classList.remove('is-invalid', 'border-danger');

  if (errors.length > 0) {
    // Add error class
    field.classList.add('is-invalid', 'border-danger');

    // Create error display
    const errorDiv = document.createElement('div');
    errorDiv.className = 'validation-error text-danger small mt-1';
    errorDiv.innerHTML = errors.map((error) => `• ${error}`).join('<br>');

    field.parentNode.appendChild(errorDiv);
  }
}

/**
 * Clear all validation errors
 */
function clearAllErrors() {
  document.querySelectorAll('.validation-error').forEach((el) => el.remove());
  document.querySelectorAll('.is-invalid, .border-danger').forEach((el) => {
    el.classList.remove('is-invalid', 'border-danger');
  });
}

/**
 * Validate login form
 * @param {HTMLFormElement} form - Form element
 * @returns {boolean} - Form validity
 */
function validateLoginForm(form) {
  clearAllErrors();
  let isValid = true;

  const username = form.querySelector('#username').value;
  const password = form.querySelector('#password').value;

  // Validate username
  const usernameResult = validateTextInput(username, {
    required: true,
    fieldName: 'Username',
    maxLength: VALIDATION_CONFIG.maxFieldLengths.username,
    pattern: /^[a-zA-Z0-9_.-]+$/,
  });

  if (!usernameResult.valid) {
    displayFieldErrors('username', usernameResult.errors);
    isValid = false;
  }

  // Validate password
  const passwordResult = validateTextInput(password, {
    required: true,
    fieldName: 'Password',
    maxLength: VALIDATION_CONFIG.maxFieldLengths.password,
    minLength: 3,
  });

  if (!passwordResult.valid) {
    displayFieldErrors('password', passwordResult.errors);
    isValid = false;
  }

  return isValid;
}

/**
 * Validate create request form
 * @param {HTMLFormElement} form - Form element
 * @returns {boolean} - Form validity
 */
function validateCreateRequestForm(form) {
  clearAllErrors();
  let isValid = true;

  // Validate object selection
  const objectId = form.querySelector('[name="object_id"]').value;
  if (!objectId) {
    alert('Please select an object');
    isValid = false;
  }

  // Validate contractors selection
  const contractors = form.querySelectorAll(
    '[name="contractor_ids[]"]:checked'
  );
  if (contractors.length === 0) {
    alert('Please select at least one contractor');
    isValid = false;
  }

  // Validate manufacturers selection
  const manufacturers = form.querySelectorAll(
    '[name="manufacturers[]"]:checked'
  );
  if (manufacturers.length === 0) {
    alert('Please select at least one manufacturer');
    isValid = false;
  }

  // Validate comment if present
  const comment = form.querySelector('[name="request_comment"]');
  if (comment && comment.value) {
    const commentResult = validateTextInput(comment.value, {
      fieldName: 'Comment',
      maxLength: VALIDATION_CONFIG.maxFieldLengths.comment,
    });

    if (!commentResult.valid) {
      displayFieldErrors('request_comment', commentResult.errors);
      isValid = false;
    }
  }

  // Validate files if present
  const fileInputs = form.querySelectorAll('input[type="file"]');
  fileInputs.forEach((input) => {
    if (input.files && input.files.length > 0) {
      Array.from(input.files).forEach((file) => {
        const fileResult = validateFile(file);
        if (!fileResult.valid) {
          alert(
            `File validation error for ${file.name}:\n${fileResult.errors.join(
              '\n'
            )}`
          );
          isValid = false;
        }
      });
    }
  });

  return isValid;
}

/**
 * Real-time validation for input fields
 * @param {HTMLInputElement} field - Input field
 * @param {Object} rules - Validation rules
 */
function setupRealtimeValidation(field, rules) {
  let timeout;

  field.addEventListener('input', function () {
    clearTimeout(timeout);
    timeout = setTimeout(() => {
      let result;

      if (field.type === 'email') {
        result = validateEmail(field.value);
      } else if (field.dataset.type === 'phone') {
        result = validatePhone(field.value);
      } else {
        result = validateTextInput(field.value, rules);
      }

      displayFieldErrors(field.id, result.errors);
    }, 500); // Debounce for 500ms
  });
}

/**
 * Initialize validation for the entire page
 */
function initializeValidation() {
  // Setup real-time validation for common fields
  const usernameField = document.getElementById('username');
  if (usernameField) {
    setupRealtimeValidation(usernameField, {
      fieldName: 'Username',
      maxLength: VALIDATION_CONFIG.maxFieldLengths.username,
      pattern: /^[a-zA-Z0-9_.-]+$/,
    });
  }

  const emailFields = document.querySelectorAll('input[type="email"]');
  emailFields.forEach((field) => {
    setupRealtimeValidation(field, {
      fieldName: 'Email',
      maxLength: VALIDATION_CONFIG.maxFieldLengths.email,
    });
  });

  const phoneFields = document.querySelectorAll('input[data-type="phone"]');
  phoneFields.forEach((field) => {
    setupRealtimeValidation(field, {
      fieldName: 'Phone',
      maxLength: VALIDATION_CONFIG.maxFieldLengths.phone,
    });
  });

  // Setup file validation
  const fileInputs = document.querySelectorAll('input[type="file"]');
  fileInputs.forEach((input) => {
    input.addEventListener('change', function () {
      if (this.files && this.files.length > 0) {
        Array.from(this.files).forEach((file) => {
          const result = validateFile(file);
          if (!result.valid) {
            alert(
              `File validation error for ${file.name}:\n${result.errors.join(
                '\n'
              )}`
            );
            this.value = ''; // Clear invalid file
          }
        });
      }
    });
  });

  // Setup form validation
  const loginForm = document.querySelector('form[action*="login"]');
  if (loginForm) {
    loginForm.addEventListener('submit', function (e) {
      if (!validateLoginForm(this)) {
        e.preventDefault();
      }
    });
  }

  const createRequestForm = document.querySelector(
    'form[action*="create_request"]'
  );
  if (createRequestForm) {
    createRequestForm.addEventListener('submit', function (e) {
      if (!validateCreateRequestForm(this)) {
        e.preventDefault();
      }
    });
  }
}

// Initialize validation when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeValidation);
} else {
  initializeValidation();
}

// Export functions for global use
window.CRMValidation = {
  validateFile,
  validateTextInput,
  validateEmail,
  validatePhone,
  validateLoginForm,
  validateCreateRequestForm,
  displayFieldErrors,
  clearAllErrors,
  setupRealtimeValidation,
};
