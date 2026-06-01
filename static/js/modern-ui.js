// ========================================
// DATE PICKER ICON ACTIVATION
// ========================================
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.date-input-group').forEach(function (group) {
    const input = group.querySelector('input[type="date"]');
    const icon = group.querySelector('.date-icon');
    if (input && icon) {
      icon.addEventListener('click', function (e) {
        e.preventDefault();
        input.showPicker ? input.showPicker() : input.focus();
      });
    }
  });
});
// Global modal/backdrop cleanup to prevent orphaned overlays that block the UI
document.addEventListener('DOMContentLoaded', function () {
  try {
    const backdrops = document.querySelectorAll('.modal-backdrop');
    const visibleModal = document.querySelector('.modal.show');
    if (backdrops.length && !visibleModal) {
      backdrops.forEach(el => el.remove());
      document.body.classList.remove('modal-open');
      document.body.style.overflow = '';
      document.body.style.paddingRight = '';
      console.debug('Removed orphan modal backdrops on load');
    }
  } catch (err) {
    console.error('Error during modal/backdrop cleanup on load', err);
  }

  // Ensure cleanup after any modal is hidden (Bootstrap event)
  document.addEventListener('hidden.bs.modal', function () {
    setTimeout(function () {
      const anyShown = document.querySelector('.modal.show');
      if (!anyShown) {
        document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
        document.body.classList.remove('modal-open');
        document.body.style.overflow = '';
        document.body.style.paddingRight = '';
      }
    }, 60);
  }, true);
});
/**
 * Modern UI Utilities - CRM Orbes Agricola
 * Enhanced user experience with modern JavaScript
 */

// ========================================
// TOAST NOTIFICATION SYSTEM
// ========================================

class ToastManager {
  constructor() {
    this.container = null;
    this.init();
  }

  init() {
    // Create toast container if it doesn't exist
    if (!document.getElementById('toast-container')) {
      this.container = document.createElement('div');
      this.container.id = 'toast-container';
      this.container.className = 'toast-container';
      this.container.setAttribute('aria-live', 'polite');
      this.container.setAttribute('aria-atomic', 'true');
      document.body.appendChild(this.container);
    } else {
      this.container = document.getElementById('toast-container');
    }
  }

  show(message, type = 'info', duration = 5000) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type} animate-slide-in-right`;
    toast.setAttribute('role', 'alert');

    const icons = {
      success: 'bi-check-circle-fill',
      error: 'bi-x-circle-fill',
      warning: 'bi-exclamation-triangle-fill',
      info: 'bi-info-circle-fill'
    };

    const icon = icons[type] || icons.info;

    toast.innerHTML = `
      <div class="toast-icon">
        <i class="bi ${icon}"></i>
      </div>
      <div class="toast-content">
        <p class="toast-message">${this.escapeHtml(message)}</p>
      </div>
      <button class="toast-close" aria-label="Close notification">
        <i class="bi bi-x"></i>
      </button>
    `;

    this.container.appendChild(toast);

    // Close button handler
    const closeBtn = toast.querySelector('.toast-close');
    closeBtn.addEventListener('click', () => this.remove(toast));

    // Auto remove
    if (duration > 0) {
      setTimeout(() => this.remove(toast), duration);
    }

    // Pause auto-remove on hover
    toast.addEventListener('mouseenter', () => {
      toast.dataset.paused = 'true';
    });

    toast.addEventListener('mouseleave', () => {
      delete toast.dataset.paused;
    });

    return toast;
  }

  remove(toast) {
    if (toast.dataset.paused) return;
    
    toast.classList.remove('animate-slide-in-right');
    toast.classList.add('animate-fade-out');
    
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 300);
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  success(message, duration) {
    return this.show(message, 'success', duration);
  }

  error(message, duration) {
    return this.show(message, 'error', duration);
  }

  warning(message, duration) {
    return this.show(message, 'warning', duration);
  }

  info(message, duration) {
    return this.show(message, 'info', duration);
  }
}

// Create global toast instance
window.toast = new ToastManager();

// ========================================
// LOADING OVERLAY
// ========================================

class LoadingOverlay {
  constructor() {
    this.overlay = null;
  }

  show(message = 'Cargando...') {
    if (this.overlay) return;

    this.overlay = document.createElement('div');
    this.overlay.className = 'loading-overlay animate-fade-in';
    this.overlay.innerHTML = `
      <div class="loading-content animate-scale-in">
        <div class="spinner"></div>
        <p class="loading-message">${message}</p>
      </div>
    `;

    document.body.appendChild(this.overlay);
    document.body.style.overflow = 'hidden';
  }

  hide() {
    if (!this.overlay) return;

    this.overlay.classList.remove('animate-fade-in');
    this.overlay.classList.add('animate-fade-out');

    setTimeout(() => {
      if (this.overlay && this.overlay.parentNode) {
        this.overlay.parentNode.removeChild(this.overlay);
        this.overlay = null;
        document.body.style.overflow = '';
      }
    }, 300);
  }

  updateMessage(message) {
    if (this.overlay) {
      const messageEl = this.overlay.querySelector('.loading-message');
      if (messageEl) {
        messageEl.textContent = message;
      }
    }
  }
}

window.loadingOverlay = new LoadingOverlay();

// ========================================
// FORM VALIDATION UTILITIES
// ========================================

class FormValidator {
  constructor(formElement) {
    this.form = formElement;
    this.init();
  }

  init() {
    if (!this.form) return;

    // Add real-time validation
    const inputs = this.form.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
      input.addEventListener('blur', () => this.validateField(input));
      input.addEventListener('input', () => this.clearFieldError(input));
    });

    // Handle form submission
    this.form.addEventListener('submit', (e) => {
      if (!this.validateForm()) {
        e.preventDefault();
        e.stopPropagation();
        window.toast.error('Por favor corrija los errores en el formulario');
      }
    });
  }

  validateField(field) {
    let isValid = true;
    let message = '';

    // Required validation
    if (field.hasAttribute('required') && !field.value.trim()) {
      isValid = false;
      message = 'Este campo es obligatorio';
    }

    // Email validation
    if (field.type === 'email' && field.value) {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(field.value)) {
        isValid = false;
        message = 'Ingrese un email válido';
      }
    }

    // Min length validation
    if (field.hasAttribute('minlength') && field.value) {
      const minLength = parseInt(field.getAttribute('minlength'));
      if (field.value.length < minLength) {
        isValid = false;
        message = `Mínimo ${minLength} caracteres`;
      }
    }

    // Pattern validation
    if (field.hasAttribute('pattern') && field.value) {
      const pattern = new RegExp(field.getAttribute('pattern'));
      if (!pattern.test(field.value)) {
        isValid = false;
        message = 'Formato no válido';
      }
    }

    if (isValid) {
      this.clearFieldError(field);
    } else {
      this.showFieldError(field, message);
    }

    return isValid;
  }

  validateForm() {
    const fields = this.form.querySelectorAll('input, select, textarea');
    let isValid = true;

    fields.forEach(field => {
      if (!this.validateField(field)) {
        isValid = false;
      }
    });

    return isValid;
  }

  showFieldError(field, message) {
    field.classList.add('is-invalid');
    field.classList.remove('is-valid');

    // Remove existing error message
    this.clearFieldError(field);

    // Add error message
    const errorDiv = document.createElement('div');
    errorDiv.className = 'invalid-feedback animate-fade-in-down';
    errorDiv.textContent = message;
    field.parentNode.appendChild(errorDiv);
  }

  clearFieldError(field) {
    field.classList.remove('is-invalid');
    if (field.value) {
      field.classList.add('is-valid');
    } else {
      field.classList.remove('is-valid');
    }

    const errorDiv = field.parentNode.querySelector('.invalid-feedback');
    if (errorDiv) {
      errorDiv.remove();
    }
  }
}

// ========================================
// RIPPLE EFFECT FOR BUTTONS
// ========================================

function addRippleEffect(element) {
  element.addEventListener('click', function(e) {
    const ripple = document.createElement('span');
    ripple.className = 'ripple';
    
    const rect = this.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    const x = e.clientX - rect.left - size / 2;
    const y = e.clientY - rect.top - size / 2;
    
    ripple.style.width = ripple.style.height = size + 'px';
    ripple.style.left = x + 'px';
    ripple.style.top = y + 'px';
    
    this.appendChild(ripple);
    
    setTimeout(() => ripple.remove(), 600);
  });
}

// ========================================
// SMOOTH SCROLL TO TOP
// ========================================

function createScrollToTopButton() {
  const button = document.createElement('button');
  button.id = 'scroll-to-top';
  button.className = 'scroll-to-top-btn';
  button.innerHTML = '<i class="bi bi-arrow-up"></i>';
  button.setAttribute('aria-label', 'Volver arriba');
  button.style.display = 'none';

  document.body.appendChild(button);

  // Show/hide based on scroll position
  window.addEventListener('scroll', () => {
    if (window.pageYOffset > 300) {
      button.style.display = 'flex';
      button.classList.add('animate-fade-in-up');
    } else {
      button.style.display = 'none';
    }
  });

  // Scroll to top on click
  button.addEventListener('click', () => {
    window.scrollTo({
      top: 0,
      behavior: 'smooth'
    });
  });
}

// ========================================
// DEBOUNCE UTILITY
// ========================================

function debounce(func, wait = 300) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// ========================================
// THROTTLE UTILITY
// ========================================

function throttle(func, limit = 200) {
  let inThrottle;
  return function(...args) {
    if (!inThrottle) {
      func.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

// ========================================
// LOCAL STORAGE UTILITIES
// ========================================

const storage = {
  set(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
      return true;
    } catch (e) {
      console.error('Error saving to localStorage:', e);
      return false;
    }
  },

  get(key, defaultValue = null) {
    try {
      const item = localStorage.getItem(key);
      return item ? JSON.parse(item) : defaultValue;
    } catch (e) {
      console.error('Error reading from localStorage:', e);
      return defaultValue;
    }
  },

  remove(key) {
    try {
      localStorage.removeItem(key);
      return true;
    } catch (e) {
      console.error('Error removing from localStorage:', e);
      return false;
    }
  },

  clear() {
    try {
      localStorage.clear();
      return true;
    } catch (e) {
      console.error('Error clearing localStorage:', e);
      return false;
    }
  }
};

// ========================================
// COPY TO CLIPBOARD
// ========================================

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    window.toast.success('Copiado al portapapeles');
    return true;
  } catch (err) {
    console.error('Failed to copy:', err);
    window.toast.error('Error al copiar');
    return false;
  }
}

// ========================================
// FORMAT UTILITIES
// ========================================

const formatters = {
  currency(amount, currency = 'USD') {
    return new Intl.NumberFormat('es-PE', {
      style: 'currency',
      currency: currency
    }).format(amount);
  },

  date(date, format = 'short') {
    const options = {
      short: { year: 'numeric', month: '2-digit', day: '2-digit' },
      long: { year: 'numeric', month: 'long', day: 'numeric' },
      full: { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }
    };

    return new Intl.DateTimeFormat('es-PE', options[format] || options.short)
      .format(new Date(date));
  },

  number(num, decimals = 0) {
    return new Intl.NumberFormat('es-PE', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    }).format(num);
  },

  phone(phoneNumber) {
    const cleaned = ('' + phoneNumber).replace(/\D/g, '');
    const match = cleaned.match(/^(\d{3})(\d{3})(\d{4})$/);
    if (match) {
      return '(' + match[1] + ') ' + match[2] + '-' + match[3];
    }
    return phoneNumber;
  }
};

// ========================================
// INITIALIZE ON DOM READY
// ========================================

document.addEventListener('DOMContentLoaded', function() {
  // Add ripple effect to buttons
  document.querySelectorAll('.btn, button').forEach(btn => {
    if (!btn.classList.contains('no-ripple')) {
      addRippleEffect(btn);
    }
  });

  // Create scroll to top button
  createScrollToTopButton();

  // Initialize form validators
  document.querySelectorAll('form[data-validate]').forEach(form => {
    new FormValidator(form);
  });

  // Add stagger animation to list items
  document.querySelectorAll('.animate-stagger').forEach(container => {
    container.querySelectorAll(':scope > *').forEach((item, index) => {
      item.classList.add('stagger-item');
      item.style.animationDelay = `${index * 0.05}s`;
    });
  });

  // Enhance input focus states
  document.querySelectorAll('input, select, textarea').forEach(input => {
    input.addEventListener('focus', function() {
      this.parentElement?.classList.add('focused');
    });

    input.addEventListener('blur', function() {
      this.parentElement?.classList.remove('focused');
    });
  });

  console.log('🎨 Modern UI utilities initialized');
});

// Export utilities for global use
window.FormValidator = FormValidator;
window.debounce = debounce;
window.throttle = throttle;
window.storage = storage;
window.copyToClipboard = copyToClipboard;
window.formatters = formatters;
