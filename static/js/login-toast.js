/**
 * Sistema de notificaciones Toast para Login
 * Muestra mensajes elegantes y animados
 */

// Configuración de iconos según tipo de mensaje
const TOAST_ICONS = {
  danger: 'fa-circle-exclamation',
  warning: 'fa-triangle-exclamation',
  success: 'fa-circle-check',
  info: 'fa-circle-info'
};

// Configuración de colores
const TOAST_COLORS = {
  danger: '#dc2626',
  warning: '#f59e0b',
  success: '#16a34a',
  info: '#2563eb'
};

/**
 * Crea y muestra una notificación toast
 * @param {string} message - Mensaje a mostrar
 * @param {string} type - Tipo: 'danger', 'warning', 'success', 'info'
 * @param {number} duration - Duración en ms (default: 5000)
 */
function showToast(message, type = 'info', duration = 5000) {
  const container = document.getElementById('toast-root');
  if (!container) return;

  // Crear elemento toast
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.setAttribute('role', 'alert');
  
  const icon = TOAST_ICONS[type] || TOAST_ICONS.info;
  
  toast.innerHTML = `
    <i class="fas ${icon}" style="color: ${TOAST_COLORS[type]}; font-size: 20px;"></i>
    <div class="toast-msg">${escapeHtml(message)}</div>
    <button class="toast-close" aria-label="Cerrar">
      <i class="fas fa-times"></i>
    </button>
  `;

  // Agregar al contenedor
  container.appendChild(toast);

  // Animar entrada
  setTimeout(() => toast.classList.add('show'), 10);

  // Configurar cierre
  const closeBtn = toast.querySelector('.toast-close');
  const removeToast = () => {
    toast.classList.add('hide');
    setTimeout(() => toast.remove(), 300);
  };

  closeBtn.addEventListener('click', removeToast);

  // Auto-cerrar
  if (duration > 0) {
    setTimeout(removeToast, duration);
  }
}

/**
 * Escapa HTML para prevenir XSS
 */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Procesa mensajes flash del servidor
 */
function processFlashMessages() {
  const container = document.getElementById('toast-root');
  if (!container) return;

  const flashData = container.getAttribute('data-flashes');
  if (!flashData) return;

  try {
    const flashes = JSON.parse(flashData);
    if (Array.isArray(flashes) && flashes.length > 0) {
      // Pequeño delay para que la página cargue completamente
      setTimeout(() => {
        flashes.forEach(([category, message], index) => {
          setTimeout(() => {
            showToast(message, category, 6000);
          }, index * 150); // Escalonar múltiples mensajes
        });
      }, 100);
    }
  } catch (e) {
    console.error('Error procesando mensajes flash:', e);
  }
}

/**
 * Validación del formulario en tiempo real
 */
function setupFormValidation() {
  const form = document.querySelector('.form');
  if (!form) return;

  const usuarioInput = form.querySelector('input[name="usuario"]');
  const passwordInput = form.querySelector('input[name="password"]');

  // Validación al enviar
  form.addEventListener('submit', (e) => {
    const usuario = usuarioInput?.value.trim();
    const password = passwordInput?.value;

    // Validación cliente
    if (!usuario || usuario.length < 3) {
      e.preventDefault();
      showToast('Por favor ingrese un usuario válido (mínimo 3 caracteres)', 'warning', 4000);
      usuarioInput?.focus();
      return;
    }

    if (!password || password.length < 4) {
      e.preventDefault();
      showToast('Por favor ingrese una contraseña válida', 'warning', 4000);
      passwordInput?.focus();
      return;
    }

    // Mostrar indicador de carga
    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Verificando...';
    }
  });

  // Eliminar espacios al inicio/fin del usuario
  usuarioInput?.addEventListener('blur', () => {
    usuarioInput.value = usuarioInput.value.trim();
  });
}

/**
 * Añade efectos visuales al formulario
 */
function enhanceFormUI() {
  const inputs = document.querySelectorAll('.input-group input');
  
  inputs.forEach(input => {
    // Efecto focus en el grupo
    input.addEventListener('focus', () => {
      input.parentElement.classList.add('focused');
    });

    input.addEventListener('blur', () => {
      input.parentElement.classList.remove('focused');
    });

    // Indicador de campo lleno
    input.addEventListener('input', () => {
      if (input.value.trim()) {
        input.parentElement.classList.add('filled');
      } else {
        input.parentElement.classList.remove('filled');
      }
    });
  });
}

/**
 * Añade shake animation a la tarjeta en caso de error
 */
function addErrorAnimation() {
  const flashData = document.getElementById('toast-root')?.getAttribute('data-flashes');
  if (!flashData) return;

  try {
    const flashes = JSON.parse(flashData);
    const hasError = flashes.some(([category]) => category === 'danger' || category === 'warning');
    
    if (hasError) {
      const formCard = document.querySelector('.form-card');
      if (formCard) {
        formCard.classList.add('shake');
        setTimeout(() => formCard.classList.remove('shake'), 500);
      }
    }
  } catch (e) {
    // Ignorar errores de parsing
  }
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
  processFlashMessages();
  setupFormValidation();
  enhanceFormUI();
  addErrorAnimation();
});

// Exponer función global para uso desde otros scripts
window.showToast = showToast;
