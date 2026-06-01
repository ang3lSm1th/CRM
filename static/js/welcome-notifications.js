/**
 * ======================================================
 * MODAL DE NOTIFICACIONES DE BIENVENIDA
 * ======================================================
 * Se muestra automáticamente al iniciar sesión
 * Muestra recordatorios del día (programadas y sin iniciar)
 */

(function() {
  'use strict';

  const API_URL = '/leads/notifications/panel';
  const SHOW_DELAY = 1000; // 1 segundo después de cargar la página

  /**
   * Escapa HTML para prevenir XSS
   */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
  }

  /**
   * Renderiza las notificaciones programadas en el modal
   */
  function renderModalProgramadas(items) {
    const container = document.getElementById('modal-items-programadas');
    const countBadge = document.getElementById('modal-count-programadas');
    const section = document.getElementById('modal-programadas-section');
    
    if (!container || !countBadge) return;

    countBadge.textContent = items.length;

    if (items.length === 0) {
      section.style.display = 'none';
      return;
    }

    section.style.display = 'block';
    container.innerHTML = '';

    items.forEach(function(item) {
      const div = document.createElement('a');
      div.href = '/leads/seguimiento/' + (item.codigo || item.id);
      div.className = 'list-group-item list-group-item-action';
      
      const fecha = item.fecha_programada 
        ? '<small class="text-muted d-block mt-1"><i class="fa-solid fa-calendar"></i> ' + escapeHtml(item.fecha_programada) + '</small>'
        : '';
      
      const asesor = item.usuario_nombre
        ? '<small class="text-muted d-block mt-1"><i class="fa-solid fa-user"></i> ' + escapeHtml(item.usuario_nombre) + '</small>'
        : '';
      
      div.innerHTML = 
        '<div class="d-flex justify-content-between align-items-start">' +
          '<div class="flex-grow-1">' +
            '<strong>' + (item.codigo ? escapeHtml(item.codigo) + ' — ' : '') + escapeHtml(item.nombre || 'Sin nombre') + '</strong>' +
            asesor +
            fecha +
          '</div>' +
          '<i class="fa-solid fa-chevron-right text-muted ms-2"></i>' +
        '</div>';
      
      container.appendChild(div);
    });

    // Botón ver todos
    const btnVerTodos = document.createElement('a');
    btnVerTodos.href = '/leads/programados';
    btnVerTodos.className = 'list-group-item list-group-item-action text-center text-primary fw-semibold';
    btnVerTodos.innerHTML = '<small><i class="fa-solid fa-eye"></i> Ver todos los programados</small>';
    container.appendChild(btnVerTodos);
  }

  /**
   * Renderiza las notificaciones sin iniciar en el modal
   */
  function renderModalSinIniciar(items) {
    const container = document.getElementById('modal-items-sin-iniciar');
    const countBadge = document.getElementById('modal-count-sin-iniciar');
    const section = document.getElementById('modal-sin-iniciar-section');
    
    if (!container || !countBadge) return;

    countBadge.textContent = items.length;

    if (items.length === 0) {
      section.style.display = 'none';
      return;
    }

    section.style.display = 'block';
    container.innerHTML = '';

    const MAX_VISIBLE = 5;
    const toShow = items.slice(0, MAX_VISIBLE);

    toShow.forEach(function(item) {
      const div = document.createElement('a');
      div.href = '/leads/seguimiento/' + (item.codigo || item.id);
      div.className = 'list-group-item list-group-item-action';
      
      const asesor = item.usuario_nombre
        ? '<small class="text-muted d-block mt-1"><i class="fa-solid fa-user"></i> ' + escapeHtml(item.usuario_nombre) + '</small>'
        : '';
      
      div.innerHTML = 
        '<div class="d-flex justify-content-between align-items-start">' +
          '<div class="flex-grow-1">' +
            '<strong>' + (item.codigo ? escapeHtml(item.codigo) + ' — ' : '') + escapeHtml(item.nombre || 'Sin nombre') + '</strong>' +
            asesor +
          '</div>' +
          '<i class="fa-solid fa-chevron-right text-muted ms-2"></i>' +
        '</div>';
      
      container.appendChild(div);
    });

    // Si hay más items
    if (items.length > MAX_VISIBLE) {
      const remaining = document.createElement('div');
      remaining.className = 'list-group-item text-center text-muted';
      remaining.innerHTML = '<small>... y ' + (items.length - MAX_VISIBLE) + ' más</small>';
      container.appendChild(remaining);
    }

    // Botón ver todos
    const btnVerTodos = document.createElement('a');
    btnVerTodos.href = '/leads/sin-iniciar';
    btnVerTodos.className = 'list-group-item list-group-item-action text-center text-warning fw-semibold';
    btnVerTodos.innerHTML = '<small><i class="fa-solid fa-eye"></i> Ver todos sin iniciar</small>';
    container.appendChild(btnVerTodos);
  }

  /**
   * Carga las notificaciones y muestra el modal
   */
  async function loadAndShowModal() {
    try {
      const response = await fetch(API_URL, { credentials: 'same-origin' });
      
      if (!response.ok) {
        console.warn('Error cargando notificaciones:', response.status);
        return;
      }

      const data = await response.json();
      const programadas = data.programadas || [];
      const sinIniciar = data.sin_iniciar || [];
      const total = programadas.length + sinIniciar.length;

      // Renderizar notificaciones
      renderModalProgramadas(programadas);
      renderModalSinIniciar(sinIniciar);

      // Mostrar/ocultar mensaje de "sin notificaciones"
      const noNotifMsg = document.getElementById('modal-no-notifications');
      const progSection = document.getElementById('modal-programadas-section');
      const sinSection = document.getElementById('modal-sin-iniciar-section');

      if (total === 0) {
        if (noNotifMsg) noNotifMsg.style.display = 'block';
        if (progSection) progSection.style.display = 'none';
        if (sinSection) sinSection.style.display = 'none';
      } else {
        if (noNotifMsg) noNotifMsg.style.display = 'none';
      }

      // Mostrar el modal (permitir cierre con backdrop/Esc y botón)
      const modalElement = document.getElementById('welcomeNotificationsModal');
      if (modalElement && typeof bootstrap !== 'undefined') {
        const modal = new bootstrap.Modal(modalElement, {
          backdrop: true,
          keyboard: true
        });
        modal.show();
      }

    } catch (error) {
      console.error('Error cargando notificaciones de bienvenida:', error);
    }
  }

  /**
   * Inicialización automática
   */
  document.addEventListener('DOMContentLoaded', function() {
    // Verificar que estamos en una página con sesión activa
    const modalElement = document.getElementById('welcomeNotificationsModal');
    
    if (modalElement) {
      // Verificar si ya se mostró en esta sesión
      const modalShown = sessionStorage.getItem('welcomeModalShown');
      
      if (modalShown === 'true') {
        console.log('Modal ya mostrada en esta sesión');
        return;
      }
      
      // Mostrar el modal después de un pequeño delay
      setTimeout(function() {
        loadAndShowModal();
        // Marcar como mostrada en esta sesión
        sessionStorage.setItem('welcomeModalShown', 'true');
      }, SHOW_DELAY);
    }
  });

})();
