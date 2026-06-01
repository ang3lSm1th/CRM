/**
 * ======================================================
 * MÓDULO DE NOTIFICACIONES - CRM
 * ======================================================
 * Sistema de notificaciones en tiempo real para leads
 * Muestra programadas y sin iniciar con polling cada minuto
 */

(function () {
  'use strict';

  /**
   * Inicializa el módulo de notificaciones
   * @param {Object} opts - Opciones de configuración
   * @returns {Object} - Objeto con métodos de control
   */
  function initNotifModule(opts) {
    opts = opts || {};
    
    // Configuración de selectores (con valores por defecto)
    const API = opts.api || '/leads/notifications/panel';
    const root = document.getElementById(opts.rootId || 'notif-dropdown-root-sidebar');
    const toggle = document.getElementById(opts.toggleId || 'notifDropdown');
    const menu = document.getElementById(opts.menuId || 'notif-list-sidebar');
    const badge = document.getElementById(opts.badgeId || 'notif-count');
    const itemsProg = document.getElementById(opts.itemsProgramadasId || 'notif-items-programadas');
    const itemsSin = document.getElementById(opts.itemsSinId || 'notif-items-sin-iniciar');

    // Validar que existan los elementos necesarios
    if (!root || !toggle || !menu || !badge || !itemsProg || !itemsSin) {
      console.debug('initNotifModule: elementos no encontrados', {
        root: !!root, 
        toggle: !!toggle, 
        menu: !!menu, 
        badge: !!badge, 
        itemsProg: !!itemsProg, 
        itemsSin: !!itemsSin
      });
      return { ok: false };
    }

    // Prevenir inicialización múltiple
    if (root.__notif_inited) {
      console.debug('initNotifModule: ya inicializado');
      return { ok: true };
    }
    root.__notif_inited = true;

    // LocalStorage para notificaciones vistas
    const LS_KEY = 'crm_seen_notifs_v1';

    /**
     * Lee el mapa de notificaciones vistas
     */
    function readSeenMap() {
      try { 
        return JSON.parse(localStorage.getItem(LS_KEY) || '{}'); 
      } catch (e) { 
        return {}; 
      }
    }

    /**
     * Guarda el mapa de notificaciones vistas
     */
    function writeSeenMap(obj) {
      try { 
        localStorage.setItem(LS_KEY, JSON.stringify(obj)); 
      } catch (e) { 
        console.warn('Error guardando notificaciones vistas:', e);
      }
    }

    /**
     * Muestra un toast rápido (opcional)
     */
    function showQuickToast(message, type = 'info') {
      // Buscar el contenedor de toasts del sistema
      const toastStack = document.getElementById('toast-stack');
      if (!toastStack) return;

      const toast = document.createElement('div');
      toast.className = `toast toast-${type}`;
      toast.innerHTML = `
        <span class="toast-msg">${escapeHtml(message)}</span>
        <button class="toast-close" aria-label="Cerrar">×</button>
      `;

      toastStack.appendChild(toast);

      const closeBtn = toast.querySelector('.toast-close');
      closeBtn.addEventListener('click', () => toast.remove());

      setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 300);
      }, 4000);
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
     * Renderiza la lista de notificaciones
     */
    function renderList(container, items, type) {
      container.innerHTML = '';
      
      if (!items || items.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'dropdown-item small text-muted';
        empty.textContent = '— Ninguno —';
        container.appendChild(empty);
        return;
      }

      const MAX_VISIBLE = 3;

      // Notificaciones programadas
      if (type === 'programadas') {
        items.forEach(it => {
          const a = document.createElement('a');
          a.className = 'dropdown-item small';
          a.href = '/leads/seguimiento/' + (it.codigo || it.id);
          
          const smallDate = it.fecha_programada
            ? `<div class="small text-muted">${escapeHtml(it.fecha_programada)}</div>`
            : '';
          
          a.innerHTML = `
            <strong>${it.codigo ? escapeHtml(it.codigo) + ' — ' : ''}${escapeHtml(it.nombre || 'Sin nombre')}</strong>
            ${smallDate}
          `;
          
          container.appendChild(a);
        });

        // Enlace "Ver todos"
        const more = document.createElement('div');
        more.className = 'dropdown-item small text-center text-muted';
        more.style.borderTop = '1px solid #eef2f7';
        more.style.marginTop = '.1rem';
        more.innerHTML = `
          <a href="/leads/programados" style="display:block">Ver todos los programados</a>
        `;
        container.appendChild(more);
        return;
      }

      // Notificaciones sin iniciar
      if (type === 'sin') {
        const toShow = items.slice(0, MAX_VISIBLE);
        
        toShow.forEach(it => {
          const a = document.createElement('a');
          a.className = 'dropdown-item small';
          a.href = '/leads/seguimiento/' + (it.codigo || it.id);
          a.innerHTML = `
            <strong>${it.codigo ? escapeHtml(it.codigo) + ' — ' : ''}${escapeHtml(it.nombre || 'Sin nombre')}</strong>
          `;
          container.appendChild(a);
        });

        // Si hay más items, mostrar enlace
        if (items.length > MAX_VISIBLE) {
          const more = document.createElement('div');
          more.className = 'dropdown-item small text-center text-muted';
          more.style.borderTop = '1px solid #eef2f7';
          more.style.marginTop = '.4rem';
          more.innerHTML = `
            <div>${items.length - MAX_VISIBLE} más...</div>
            <a href="/leads/sin-iniciar" style="margin-top:.3rem; display:block">Ver todos no iniciados</a>
          `;
          container.appendChild(more);
        }
        return;
      }
    }

    /**
     * Actualiza la UI con nuevos datos
     */
    function updateUI(data) {
      const programadas = data.programadas || [];
      const sinIniciar = data.sin_iniciar || [];

      renderList(itemsProg, programadas, 'programadas');
      renderList(itemsSin, sinIniciar, 'sin');

      const total = programadas.length + sinIniciar.length;
      
      if (total > 0) {
        badge.style.display = 'inline-block';
        badge.textContent = String(total);
        badge.setAttribute('aria-label', `${total} notificaciones`);
      } else {
        badge.style.display = 'none';
        badge.textContent = '0';
        badge.removeAttribute('aria-label');
      }
    }

    /**
     * Obtiene datos desde el servidor
     */
    async function fetchAndProcess() {
      try {
        const resp = await fetch(API, { credentials: 'same-origin' });
        
        if (!resp.ok) { 
          console.warn('Notificaciones: fetch falló con status', resp.status); 
          return; 
        }
        
        const data = await resp.json();
        const prev = readSeenMap();
        
        updateUI(data);
        
        // Guardar estado (para futuras implementaciones de notificaciones nuevas)
        writeSeenMap(prev);
        
      } catch (err) {
        console.error('Error obteniendo notificaciones:', err);
      }
    }

    /**
     * Muestra el menú de notificaciones
     */
    function showMenu() { 
      root.classList.add('open'); 
      menu.style.display = 'block'; 
      toggle.setAttribute('aria-expanded', 'true'); 
    }

    /**
     * Oculta el menú de notificaciones
     */
    function hideMenu() { 
      root.classList.remove('open'); 
      menu.style.display = 'none'; 
      toggle.setAttribute('aria-expanded', 'false'); 
    }

    /**
     * Alterna visibilidad del menú
     */
    function toggleMenu(ev) {
      if (ev) {
        ev.preventDefault(); 
        ev.stopPropagation();
      }
      
      const visible = menu.style.display === 'block' || root.classList.contains('open');
      visible ? hideMenu() : showMenu();
    }

    // ===== EVENT LISTENERS =====

    // Toggle del botón de notificaciones
    if (!toggle.__notif_bound) {
      toggle.addEventListener('click', toggleMenu, { passive: false });
      toggle.__notif_bound = true;
    }

    // Cerrar al hacer clic fuera
    if (!document.__notif_outbound) {
      document.addEventListener('click', function (ev) {
        if (!root.contains(ev.target)) {
          hideMenu();
        }
      });
      
      document.addEventListener('keydown', function (ev) { 
        if (ev.key === 'Escape') {
          hideMenu();
        }
      });
      
      document.__notif_outbound = true;
    }

    // ===== INICIALIZACIÓN =====

    // Primera carga
    fetchAndProcess();
    
    // Polling cada minuto
    root.__notif_poll = setInterval(fetchAndProcess, 60 * 1000);

    // Retornar API pública
    return {
      ok: true,
      refresh: fetchAndProcess,
      teardown: function () {
        clearInterval(root.__notif_poll);
        root.__notif_inited = false;
      }
    };
  }

  // ===== EXPORTAR GLOBALMENTE =====
  window.initNotifModule = initNotifModule;

  // ===== AUTO-INICIALIZACIÓN =====
  document.addEventListener('DOMContentLoaded', function () {
    try { 
      initNotifModule(); 
    } catch (e) { 
      console.error('Error inicializando módulo de notificaciones:', e); 
    }
  });

})();
