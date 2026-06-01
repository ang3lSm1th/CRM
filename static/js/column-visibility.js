(function () {
  function getViewKey() {
    try {
      if (window.leadsViewName && typeof window.leadsViewName === 'string') {
        return window.leadsViewName;
      }
      const title = document.title || 'Leads';
      return title.trim();
    } catch (e) {
      return 'Leads';
    }
  }

  function storageKey(tableId) {
    return `colvis:${getViewKey()}:${tableId || 'tabla-leads'}`;
  }

  function readHiddenSet(key) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return new Set();
      const arr = JSON.parse(raw);
      if (Array.isArray(arr)) return new Set(arr);
      return new Set();
    } catch (e) {
      return new Set();
    }
  }

  function writeHiddenSet(key, set) {
    try {
      localStorage.setItem(key, JSON.stringify(Array.from(set)));
    } catch (e) {
      // ignore
    }
  }

  function applyVisibility(table, hiddenSet) {
    const rows = Array.from(table.rows);
    rows.forEach((row) => {
      const cells = Array.from(row.cells);
      cells.forEach((cell, idx) => {
        if (hiddenSet.has(idx)) {
          cell.style.display = 'none';
        } else {
          cell.style.display = '';
        }
      });
    });
  }

  function buildPanel(panel, headers, hiddenSet, onToggle, onBulk) {
    panel.innerHTML = '';

    const headerBar = document.createElement('div');
    headerBar.className = 'colvis-header d-flex justify-content-between align-items-center';
    const title = document.createElement('div');
    title.textContent = 'Columnas visibles';
    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'btn btn-sm btn-outline-secondary';
    closeBtn.innerHTML = '<i class="bi bi-x"></i>';
    closeBtn.addEventListener('click', closeOverlay);
    headerBar.appendChild(title);
    headerBar.appendChild(closeBtn);
    panel.appendChild(headerBar);

    const list = document.createElement('div');
    list.className = 'colvis-list';
    headers.forEach((th, idx) => {
      const labelText = (th.textContent || th.innerText || `Columna ${idx + 1}`).trim() || `Columna ${idx + 1}`;
      const item = document.createElement('label');
      item.className = 'colvis-item form-check';

      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.className = 'form-check-input';
      cb.checked = !hiddenSet.has(idx);
      cb.dataset.colIndex = String(idx);

      const span = document.createElement('span');
      span.className = 'form-check-label';
      span.textContent = labelText;

      // Bloquear columnas críticas
      if (window.__colvisLocked && window.__colvisLocked.has(idx)) {
        cb.checked = true;
        cb.disabled = true;
        item.title = 'Esta columna no se puede ocultar';
      }

      item.appendChild(cb);
      item.appendChild(span);
      list.appendChild(item);
    });

    panel.appendChild(list);

    const actions = document.createElement('div');
    actions.className = 'colvis-actions';

    const btnAll = document.createElement('button');
    btnAll.type = 'button';
    btnAll.className = 'btn btn-sm btn-light';
    btnAll.textContent = 'Mostrar todo';
    btnAll.addEventListener('click', () => onBulk('show'));

    const btnNone = document.createElement('button');
    btnNone.type = 'button';
    btnNone.className = 'btn btn-sm btn-light';
    btnNone.textContent = 'Ocultar todo';
    btnNone.addEventListener('click', () => onBulk('hide'));

    actions.appendChild(btnAll);
    actions.appendChild(btnNone);
    panel.appendChild(actions);

    panel.addEventListener('change', (ev) => {
      const t = ev.target;
      if (!(t instanceof HTMLInputElement)) return;
      if (t.type !== 'checkbox') return;
      const idx = Number(t.dataset.colIndex);
      const visible = t.checked;
      onToggle(idx, visible);
    });
  }

  // Overlay creation helpers
  let overlayEl = null;
  let dialogEl = null;
  function ensureOverlay() {
    if (overlayEl) return overlayEl;
    overlayEl = document.createElement('div');
    overlayEl.id = 'colvis-overlay';
    overlayEl.setAttribute('hidden', '');
    overlayEl.addEventListener('click', (ev) => {
      if (ev.target === overlayEl) closeOverlay();
    });
    dialogEl = document.createElement('div');
    dialogEl.className = 'colvis-dialog';
    overlayEl.appendChild(dialogEl);
    document.body.appendChild(overlayEl);
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !overlayEl.hasAttribute('hidden')) closeOverlay();
    });
    return overlayEl;
  }

  function openOverlay(contentEl) {
    ensureOverlay();
    dialogEl.innerHTML = '';
    dialogEl.appendChild(contentEl);
    contentEl.removeAttribute('hidden');
    dialogEl.setAttribute('role', 'dialog');
    dialogEl.setAttribute('aria-modal', 'true');
    dialogEl.setAttribute('aria-label', 'Selector de columnas');
    overlayEl.removeAttribute('hidden');
    setTimeout(() => overlayEl.classList.add('open'), 10);
  }

  function closeOverlay() {
    if (!overlayEl) return;
    overlayEl.classList.remove('open');
    overlayEl.setAttribute('hidden', '');
  }

  function init() {
    const table = document.getElementById('tabla-leads');
    if (!table) return;

    const toggleBtn = document.getElementById('colvis-toggle');
    let panel = document.getElementById('colvis-panel');
    if (!toggleBtn) return;
    // Beautify toggle button appearance and icon (reference chat floating button)
    try {
      toggleBtn.innerHTML = '<i class="fa-solid fa-table-columns" aria-hidden="true"></i>';
      toggleBtn.setAttribute('aria-label', 'Columnas visibles');
      toggleBtn.setAttribute('title', 'Columnas');
    } catch(e) { /* ignore */ }
    // Create a panel element if not present
    if (!panel) {
      panel = document.createElement('div');
      panel.id = 'colvis-panel';
    }

    const headers = Array.from(table.querySelectorAll('thead th'));
    // Detectar columnas bloqueadas por nombre
    function norm(t){
      try { return (t||'').toString().normalize('NFD').replace(/\p{Diacritic}/gu,'').toLowerCase().trim(); } catch(e){ return (t||'').toString().toLowerCase().trim(); }
    }
    const locked = new Set();
    headers.forEach((th, idx) => {
      const label = norm(th.textContent || th.innerText || '');
      const isCodigo = label.includes('codigo');
      const isFecha = label.includes('fecha'); // también cubre 'fecha programada'
      const isTelefono = label.includes('telefono');
      const isRucDni = label.includes('ruc') || label.includes('dni');
      const isNombre = label.includes('nombre');
      if (isCodigo || isFecha || isTelefono || isRucDni || isNombre) locked.add(idx);
    });
    window.__colvisLocked = locked;

    const key = storageKey(table.id);
    const hiddenSet = readHiddenSet(key);
    // Asegurar que las bloqueadas nunca se oculten
    locked.forEach(i => hiddenSet.delete(i));

    applyVisibility(table, hiddenSet);

    function onToggle(idx, visible) {
      if (locked.has(idx)) return;
      if (!visible) hiddenSet.add(idx); else hiddenSet.delete(idx);
      writeHiddenSet(key, hiddenSet);
      applyVisibility(table, hiddenSet);
    }

    function onBulk(mode) {
      hiddenSet.clear();
      if (mode === 'hide') {
        headers.forEach((_, idx) => { if (!locked.has(idx)) hiddenSet.add(idx); });
      }
      writeHiddenSet(key, hiddenSet);
      applyVisibility(table, hiddenSet);
      buildPanel(panel, headers, hiddenSet, onToggle, onBulk);
    }

    buildPanel(panel, headers, hiddenSet, onToggle, onBulk);

    toggleBtn.addEventListener('click', (e) => {
      e.preventDefault();
      // Move panel into overlay dialog and show
      openOverlay(panel);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
