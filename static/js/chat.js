/**
 * ======================================================
 * CHAT INTERNO DEL SISTEMA
 * ======================================================
 * Sistema de mensajería interna para comunicación entre usuarios
 */

(function () {
  'use strict';

  let chatWindow = null;
  let chatMessages = null;
  let chatInput = null;
  let currentChatType = 'grupal'; // 'grupal' o 'individual'
  let currentDestinatarioId = null;
  let refreshInterval = null;
  let mensajesNoLeidos = 0;

  /**
   * Inicializar el chat
   */
  function initChat() {
    // Crear botón flotante
    createFloatingButton();

    // Crear ventana del chat
    createChatWindow();

    // Obtener elementos
    chatWindow = document.getElementById('chatWindow');
    chatMessages = document.getElementById('chatMessages');
    chatInput = document.getElementById('chatInput');

    // Event listeners
    document.getElementById('chatFloatBtn').addEventListener('click', toggleChat);
    document.getElementById('chatCloseBtn').addEventListener('click', toggleChat);
    document.getElementById('chatTabGrupal').addEventListener('click', () => switchTab('grupal'));
    document.getElementById('chatTabIndividual').addEventListener('click', () => switchTab('individual'));
    document.getElementById('chatSendBtn').addEventListener('click', sendMessage);

    chatInput.addEventListener('keypress', function (e) {
      if (e.key === 'Enter') {
        sendMessage();
      }
    });

    // Actualizar contador de no leídos cada 30 segundos
    updateUnreadCount();
    setInterval(updateUnreadCount, 30000);
  }

  /**
   * Crear botón flotante
   */
  function createFloatingButton() {
    const btn = document.createElement('div');
    btn.id = 'chatFloatBtn';
    btn.className = 'chat-float-btn';
    btn.innerHTML = `
      <i class="fa-solid fa-comments"></i>
      <span class="badge" id="chatBadge" style="display: none;">0</span>
    `;
    document.body.appendChild(btn);
  }

  /**
   * Crear ventana del chat
   */
  function createChatWindow() {
    const window = document.createElement('div');
    window.id = 'chatWindow';
    window.className = 'chat-window';
    window.innerHTML = `
      <div class="chat-header">
        <h5><i class="fa-solid fa-comments"></i> Chat Interno</h5>
        <div class="chat-header-actions">
          <button id="chatCloseBtn" title="Cerrar">
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>
      </div>
      
      <div class="chat-tabs">
        <button class="chat-tab active" id="chatTabGrupal">
          <i class="fa-solid fa-users"></i> Grupal
        </button>
        <button class="chat-tab" id="chatTabIndividual">
          <i class="fa-solid fa-user"></i> Individual
        </button>
      </div>
      
      <div id="chatContent" style="flex: 1; display: flex; flex-direction: column; overflow: hidden; min-height: 0;">
        <div id="chatMessages" class="chat-messages"></div>
      </div>
      
      <div class="chat-input">
        <input type="text" id="chatInput" placeholder="Escribe un mensaje..." autocomplete="off">
        <button id="chatSendBtn">
          <i class="fa-solid fa-paper-plane"></i>
        </button>
      </div>
    `;
    document.body.appendChild(window);
  }

  /**
   * Alternar ventana del chat
   */
  function toggleChat() {
    chatWindow.classList.toggle('active');

    if (chatWindow.classList.contains('active')) {
      if (currentChatType === 'grupal') {
        loadMessages();
        startAutoRefresh();
      } else {
        loadUsers();
      }
      chatInput.focus();
    } else {
      stopAutoRefresh();
    }
  }

  /**
   * Cambiar pestaña
   */
  function switchTab(tipo) {
    currentChatType = tipo;

    // Actualizar pestañas activas
    document.querySelectorAll('.chat-tab').forEach(tab => tab.classList.remove('active'));
    document.getElementById('chatTab' + (tipo === 'grupal' ? 'Grupal' : 'Individual')).classList.add('active');

    // Limpiar contenido
    chatMessages.innerHTML = '';

    if (tipo === 'grupal') {
      showChatMessages();
      loadMessages();
      startAutoRefresh();
    } else {
      stopAutoRefresh();
      loadUsers();
    }
  }

  /**
   * Mostrar área de mensajes
   */
  function showChatMessages() {
    const content = document.getElementById('chatContent');
    content.style.flex = '1';
    content.style.display = 'flex';
    content.style.flexDirection = 'column';
    content.style.overflow = 'hidden';
    content.style.minHeight = '0';
    content.innerHTML = `
      <div id="chatMessages" class="chat-messages"></div>
    `;
    chatMessages = document.getElementById('chatMessages');

    document.querySelector('.chat-input').style.display = 'flex';
  }

  /**
   * Cargar mensajes
   */
  async function loadMessages() {
    try {
      let url = '/chat/mensajes?tipo=' + currentChatType;
      if (currentChatType === 'individual' && currentDestinatarioId) {
        url += '&destinatario_id=' + currentDestinatarioId;
      }

      const response = await fetch(url);
      const mensajes = await response.json();

      renderMessages(mensajes);
      scrollToBottom();

    } catch (error) {
      console.error('Error al cargar mensajes:', error);
    }
  }

  /**
   * Renderizar mensajes
   */
  function renderMessages(mensajes) {
    const userId = parseInt(document.body.dataset.userId || '0');

    if (!mensajes || mensajes.length === 0) {
      chatMessages.innerHTML = `
        <div class="chat-empty">
          <i class="fa-solid fa-message"></i>
          <p>No hay mensajes aún.<br>¡Sé el primero en escribir!</p>
        </div>
      `;
      return;
    }

    chatMessages.innerHTML = '';

    // Invertir orden para grupal (más recientes abajo)
    if (currentChatType === 'grupal') {
      mensajes.reverse();
    }

    mensajes.forEach((msg, index) => {
      const isSent = msg.usuario_id === userId;
      const messageDiv = document.createElement('div');
      messageDiv.className = 'chat-message ' + (isSent ? 'sent' : 'received');

      const fecha = new Date(msg.fecha_envio);
      const horaFormato = fecha.toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' });

      // Indicador de visto (solo para mensajes enviados en chat individual)
      let vistoHTML = '';
      if (isSent && currentChatType === 'individual') {
        if (msg.leido) {
          vistoHTML = '<i class="fa-solid fa-check-double" style="color: #3b82f6; font-size: 10px; margin-left: 4px;" title="Visto"></i>';
        } else {
          vistoHTML = '<i class="fa-solid fa-check" style="color: #94a3b8; font-size: 10px; margin-left: 4px;" title="Enviado"></i>';
        }
      }

      messageDiv.innerHTML = `
        ${!isSent ? '<div class="chat-message-header">' + escapeHtml(msg.usuario_nombre) + '</div>' : ''}
        <div class="chat-message-bubble">${escapeHtml(msg.mensaje)}</div>
        <div class="chat-message-time">${horaFormato} ${vistoHTML}</div>
      `;

      chatMessages.appendChild(messageDiv);
    });
  }

  /**
   * Enviar mensaje
   */
  async function sendMessage() {
    const mensaje = chatInput.value.trim();

    if (!mensaje) return;

    const sendBtn = document.getElementById('chatSendBtn');
    sendBtn.disabled = true;

    try {
      const data = {
        mensaje: mensaje,
        tipo: currentChatType
      };

      if (currentChatType === 'individual' && currentDestinatarioId) {
        data.destinatario_id = currentDestinatarioId;
      }

      const response = await fetch('/chat/enviar', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
      });

      if (response.ok) {
        chatInput.value = '';
        await loadMessages();
        setTimeout(scrollToBottom, 100); // Asegurar que se haga scroll después de cargar
      } else {
        alert('Error al enviar mensaje');
      }

    } catch (error) {
      console.error('Error al enviar mensaje:', error);
      alert('Error al enviar mensaje');
    } finally {
      sendBtn.disabled = false;
      chatInput.focus();
    }
  }

  /**
   * Cargar usuarios para chat individual
   */
  async function loadUsers() {
    try {
      const response = await fetch('/chat/usuarios');
      const data = await response.json();

      // Manejar respuesta de error o array de usuarios
      const usuarios = Array.isArray(data) ? data : (data.usuarios || []);

      renderUsers(usuarios);

    } catch (error) {
      console.error('Error al cargar usuarios:', error);
      renderUsers([]);
    }
  }

  /**
   * Renderizar lista de usuarios
   */
  function renderUsers(usuarios) {
    const content = document.getElementById('chatContent');
    content.style.flex = '1';
    content.style.display = 'flex';
    content.style.flexDirection = 'column';
    content.style.overflow = 'hidden';
    content.style.minHeight = '0';
    content.innerHTML = `
      <div style="padding: 10px; background: white; border-bottom: 1px solid #e2e8f0; flex-shrink: 0;">
        <input 
          type="text" 
          id="chatUserSearch" 
          placeholder="🔍 Buscar usuario..." 
          style="width: 100%; padding: 10px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; outline: none;"
        />
      </div>
      <div class="chat-users-list" id="chatUsersList"></div>
    `;

    const usersList = document.getElementById('chatUsersList');
    const searchInput = document.getElementById('chatUserSearch');
    document.querySelector('.chat-input').style.display = 'none';

    if (!usuarios || usuarios.length === 0) {
      usersList.innerHTML = `
        <div class="chat-empty">
          <i class="fa-solid fa-users"></i>
          <p>No hay usuarios disponibles</p>
        </div>
      `;
      return;
    }

    // Ordenar: primero los que tienen mensajes no leídos
    usuarios.sort((a, b) => {
      const noLeidosA = a.mensajes_no_leidos || 0;
      const noLeidosB = b.mensajes_no_leidos || 0;

      if (noLeidosA > 0 && noLeidosB === 0) return -1;
      if (noLeidosA === 0 && noLeidosB > 0) return 1;
      if (noLeidosA !== noLeidosB) return noLeidosB - noLeidosA;

      // Si ambos tienen o no tienen no leídos, ordenar alfabéticamente
      return (a.nombre || '').localeCompare(b.nombre || '');
    });

    // Función para renderizar usuarios filtrados
    function renderFilteredUsers(filteredUsers) {
      usersList.innerHTML = '';

      if (filteredUsers.length === 0) {
        usersList.innerHTML = `
          <div class="chat-empty">
            <i class="fa-solid fa-search"></i>
            <p>No se encontraron usuarios</p>
          </div>
        `;
        return;
      }

      filteredUsers.forEach(user => {
        const userDiv = document.createElement('div');
        userDiv.className = 'chat-user-item';
        userDiv.onclick = () => openUserChat(user.id, user.nombre);

        const iniciales = user.nombre.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
        const noLeidos = user.mensajes_no_leidos || 0;

        // Obtener nombre del rol
        let nombreRol = 'Usuario';
        if (user.nombre_rol) {
          nombreRol = user.nombre_rol;
        } else if (user.id_rol) {
          // Mapeo manual por si el backend no envía nombre_rol
          const rolesMap = {
            'administrador': 'Administrador',
            'gerente': 'Gerente',
            'RRHH': 'RRHH',
            'asesor': 'Asesor'
          };
          nombreRol = rolesMap[user.id_rol] || user.id_rol.charAt(0).toUpperCase() + user.id_roslice(1);
        }

        let badgeHTML = '';
        if (noLeidos > 0) {
          badgeHTML = `<span class="chat-user-badge">${noLeidos}</span>`;
        }

        // Mostrar solo mensajes no leídos abajo del rol
        let mensajesHTML = '';
        if (noLeidos > 0) {
          mensajesHTML = `<span style="font-size: 11px; color: #ef4444; font-weight: 500;">${noLeidos} mensaje${noLeidos > 1 ? 's' : ''} nuevo${noLeidos > 1 ? 's' : ''}</span>`;
        }

        userDiv.innerHTML = `
          <div class="chat-user-avatar">${iniciales}</div>
          <div class="chat-user-info">
            <div class="chat-user-name">${escapeHtml(user.nombre)}</div>
            <div class="chat-user-role">${escapeHtml(nombreRol)}</div>
            ${mensajesHTML}
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            ${badgeHTML}
            <i class="fa-solid fa-chevron-right text-muted"></i>
          </div>
        `;

        usersList.appendChild(userDiv);
      });
    }

    // Renderizar todos inicialmente
    renderFilteredUsers(usuarios);

    // Evento de búsqueda
    searchInput.addEventListener('input', function () {
      const searchTerm = this.value.toLowerCase().trim();

      if (!searchTerm) {
        renderFilteredUsers(usuarios);
        return;
      }

      const filtered = usuarios.filter(user => {
        const nombre = (user.nombre || '').toLowerCase();
        const rol = (user.nombre_rol || user.id_rol_texto || '').toLowerCase();
        return nombre.includes(searchTerm) || rol.includes(searchTerm);
      });

      renderFilteredUsers(filtered);
    });

    // Focus automático en el input de búsqueda
    searchInput.focus();
  }

  /**
   * Abrir chat con usuario específico
   */
  function openUserChat(userId, userName) {
    currentDestinatarioId = userId;
    showChatMessages();

    // Actualizar header con nombre de usuario y estado
    const header = document.querySelector('.chat-header h5');
    header.innerHTML = `
      <button onclick="window.chatVolver()" style="background: none; border: none; color: white; cursor: pointer; margin-right: 10px;">
        <i class="fa-solid fa-arrow-left"></i>
      </button>
      <i class="fa-solid fa-user"></i> ${escapeHtml(userName)}
      <span id="chatUserStatus" style="font-size: 11px; font-weight: normal; opacity: 0.8; margin-left: 8px;"></span>
    `;

    loadMessages();
    startAutoRefresh();

    // Marcar mensajes como leídos
    markAsRead(userId);
  }

  /**
   * Volver a lista de usuarios
   */
  window.chatVolver = function () {
    currentDestinatarioId = null;
    stopAutoRefresh();

    // Restaurar header
    const header = document.querySelector('.chat-header h5');
    header.innerHTML = '<i class="fa-solid fa-comments"></i> Chat Interno';

    loadUsers();
  };

  /**
   * Auto-refresh de mensajes
   */
  function startAutoRefresh() {
    stopAutoRefresh();
    refreshInterval = setInterval(loadMessages, 5000); // Cada 5 segundos
  }

  function stopAutoRefresh() {
    if (refreshInterval) {
      clearInterval(refreshInterval);
      refreshInterval = null;
    }
  }

  /**
   * Actualizar contador de mensajes no leídos
   */
  async function updateUnreadCount() {
    try {
      const response = await fetch('/chat/no-leidos');
      const data = await response.json();
      const total = data.total || 0;

      const badge = document.getElementById('chatBadge');
      if (badge) {
        if (total > 0) {
          badge.textContent = total > 99 ? '99+' : total;
          badge.style.display = 'flex';
        } else {
          badge.style.display = 'none';
        }
      }

    } catch (error) {
      console.error('Error al obtener mensajes no leídos:', error);
    }
  }

  /**
   * Scroll al final
   */
  function scrollToBottom() {
    if (chatMessages) {
      chatMessages.scrollTop = chatMessages.scrollHeight;
      // Intento adicional después de un pequeño delay para asegurar que el DOM se actualizó
      setTimeout(() => {
        if (chatMessages) {
          chatMessages.scrollTop = chatMessages.scrollHeight;
        }
      }, 50);
    }
  }

  /**
   * Marcar mensajes como leídos
   */
  async function markAsRead(destinatarioId) {
    try {
      await fetch('/chat/marcar-leido', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ destinatario_id: destinatarioId })
      });

      // Actualizar contador de no leídos
      updateUnreadCount();

    } catch (error) {
      console.error('Error al marcar como leído:', error);
    }
  }

  /**
   * Escapar HTML
   */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
  }

  /**
   * Guardar userId en body para comparaciones
   */
  document.addEventListener('DOMContentLoaded', function () {
    // Intentar obtener el userId de la sesión (debes agregarlo en base.html)
    const userIdMeta = document.querySelector('meta[name="user-id"]');
    if (userIdMeta) {
      document.body.dataset.userId = userIdMeta.content;
    }

    initChat();
  });

})();
