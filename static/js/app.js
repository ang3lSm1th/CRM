// static/js/app.js - CÓDIGO CORREGIDO
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    // --- Bloque de Seguimiento (No modificado, es correcto) ---
    const procesoSelect   = document.getElementById("proceso_select");
    const canalSelect     = document.getElementById("canal_contacto");
    const fechaProgInput  = document.getElementById("fecha_programada");
    const cotInput        = document.getElementById("cotizacion");
    const montoInput      = document.getElementById("monto");
    const monedaSelect    = document.getElementById("moneda");
    const motivoSelect    = document.getElementById("motivo_no_venta_id");
    const secCanal = document.getElementById("sec-canal");
    const secFecha = document.getElementById("sec-fecha");
    const secCot   = document.getElementById("sec-cotizacion");
    const secMot   = document.getElementById("sec-motivo");
    const form     = document.getElementById("form-seguimiento");

    // Si no es la vista de seguimiento, no hacemos nada (y evitamos que falle este bloque)
    if (form && procesoSelect && secCanal && secFecha && secCot && secMot) {
        // --- Lógica de Seguimiento (omitida por brevedad, no necesita cambios) ---
        const blocks = [secCanal, secFecha, secCot, secMot];

        function show(el){ if(el) el.style.display = "block"; }
        function hide(el){ if(el) el.style.display = "none"; }
        function setDisabled(el, disabled){
            if (!el) return;
            el.querySelectorAll("input, select, textarea, button").forEach(ctrl => { ctrl.disabled = disabled; });
        }
        function addRequired(ctrl){ ctrl?.setAttribute("required","required"); }
        function remRequired(ctrl){ ctrl?.removeAttribute("required"); }
        function clearCotizadoRequired(){
            remRequired(cotInput); remRequired(montoInput); remRequired(monedaSelect);
        }

        function updateUI(){
            const selectedText = procesoSelect.options[procesoSelect.selectedIndex]?.text?.trim() || "";
            blocks.forEach(hide);
            [canalSelect, fechaProgInput, motivoSelect].forEach(remRequired);
            clearCotizadoRequired();
            blocks.forEach(b => setDisabled(b, false));

            if (selectedText === "Seguimiento") {
                show(secCanal); addRequired(canalSelect);
            } else if (selectedText === "Programado") {
                show(secCanal); show(secFecha);
                addRequired(canalSelect); addRequired(fechaProgInput);
            } else if (selectedText === "Cotizado") {
                show(secCanal); show(secCot);
                addRequired(canalSelect); addRequired(cotInput); addRequired(montoInput); addRequired(monedaSelect);
            } else if (selectedText === "Cerrado") {
                show(secCanal); show(secFecha); show(secCot);
                if (!canalSelect?.value) {
                    addRequired(canalSelect);
                    setDisabled(secFecha, true); setDisabled(secCot, true);
                } else {
                    setDisabled(secCanal, true); setDisabled(secFecha, true); setDisabled(secCot, true);
                }
            } else if (selectedText === "Cerrado No Vendido") {
                show(secMot); show(secCanal); show(secFecha); show(secCot);
                // addRequired(canalSelect); addRequired(fechaProgInput); addRequired(motivoSelect);
            }
        }

        procesoSelect.addEventListener("change", updateUI);
        updateUI();

        function pushToast(message, kind="warning"){
            // ... (función pushToast omitida por brevedad, no necesita cambios)
            const stack = document.getElementById('toast-stack');
            if(!stack) { alert(message); return; }
            const div = document.createElement("div");
            div.className = `toast toast-${kind}`;

            const span = document.createElement("span");
            span.className = "toast-msg";
            span.textContent = message;

            const btn = document.createElement("button");
            btn.className = "toast-close";
            btn.setAttribute("aria-label", "Cerrar");
            btn.textContent = "×";
            btn.addEventListener("click", () => div.remove());

            div.appendChild(span);
            div.appendChild(btn);
            stack.appendChild(div);

            const timer = setTimeout(() => {
                div.classList.add('fade-out');
                setTimeout(() => div.remove(), 250);
            }, 4500);

            div.addEventListener('mouseenter', ()=> clearTimeout(timer));
        }

        form.addEventListener("submit", function(e){
            const procesoTxt = procesoSelect.options[procesoSelect.selectedIndex]?.text?.trim() || "";
            const requiereCanal = ["Seguimiento","Programado","Cotizado","Cerrado No Vendido","Cerrado"].includes(procesoTxt);

            if (requiereCanal && !canalSelect?.value){
                e.preventDefault();
                pushToast("⚠️ Debes seleccionar un canal de comunicación.", "warning");
                show(secCanal); canalSelect?.focus(); return;
            }

            if (procesoTxt === "Cotizado") {
                const cot = (cotInput?.value || "").trim();
                const mon = (monedaSelect?.value || "").trim();
                const montoVal = parseFloat(montoInput?.value);

                if (!cot) { e.preventDefault(); pushToast("⚠️ Debes ingresar el código de cotización.", "warning"); show(secCot); cotInput?.focus(); return; }
                if (!montoInput?.value || isNaN(montoVal) || montoVal < 0) { e.preventDefault(); pushToast("⚠️ Debes ingresar un monto válido (0 o mayor).", "warning"); show(secCot); montoInput?.focus(); return; }
                if (!mon) { e.preventDefault(); pushToast("⚠️ Debes seleccionar una moneda.", "warning"); show(secCot); monedaSelect?.focus(); return; }
            }

            if (procesoTxt === "Cerrado No Vendido" && !motivoSelect?.value) {
                e.preventDefault();
                pushToast("⚠️ Debes seleccionar un motivo de no venta.", "warning");
                show(secMot); motivoSelect?.focus(); return;
            }

            blocks.forEach(b => setDisabled(b, false));
        });
    }
  });
})();

// static/js/leads-buscador.js
// ===============================
// 🔎 Buscador y export (búsqueda en 'comentario' + búsqueda universal server-side)
// ===============================
function editarLead(codigo){
  location.href = "/leads/edit/" + codigo;
}

document.addEventListener('DOMContentLoaded', function(){

  const table = document.getElementById('tabla-leads');

  // Si la tabla no existe (p.ej. en páginas de edición), detenemos todo.
  if (!table) return;

  const searchInput = document.getElementById('search-input');
  const fIni = document.getElementById('f_ini');
  const fFin = document.getElementById('f_fin');
  const showAllCheckbox = document.getElementById('show-all-checkbox');
  const exportBtn = document.getElementById('export-btn');
  const form = document.getElementById('filter-form');

  // Si los elementos críticos para la lógica de fechas no se encuentran, salimos.
  if (!fIni || !fFin) return;

  // ===== Helper: quitar acentos =====
  function stripDiacritics(s){ return s? s.normalize("NFD").replace(/[\u0300-\u036f]/g,""):""; }

  // ===== Resaltar texto =====
  function highlightTextNode(node,q){
    const text = node.data;
    const idx = stripDiacritics(text).toLowerCase().indexOf(stripDiacritics(q).toLowerCase());
    if(idx===-1) return;
    const mark = document.createElement("mark"); mark.textContent = text.slice(idx, idx+q.length); mark.className="hl";
    const after = document.createTextNode(text.slice(idx+q.length));
    const before = document.createTextNode(text.slice(0, idx));
    node.replaceWith(before, mark, after);
  }

  function highlightWithin(el,q){
    if(!q) return;
    el.childNodes.forEach(node=>{
      if(node.nodeType===3) highlightTextNode(node,q);
      else if(node.nodeType===1 && !["script","style"].includes(node.tagName.toLowerCase()))
        highlightWithin(node,q);
    });
  }

  function unhighlight(){
    table.querySelectorAll("mark.hl").forEach(m => m.replaceWith(document.createTextNode(m.textContent)));
  }

  // ===== Helper: obtener texto relevante de la fila =====
  // Incluye texto de celdas, atributos data-* y elementos con clase .comentario
  function getRowSearchText(tr){
    let parts = [];
    // 1) texto visible de la fila (todas las celdas)
    parts.push(tr.textContent || "");
    // 2) atributos data-* del tr (por si guardas comentario en data-comment)
    for(const attr of tr.attributes){
      if(attr.name.startsWith('data-')) parts.push(attr.value);
    }
    // 3) elementos con clase .comentario (si tu template usa esa clase)
    const comentarioEls = tr.querySelectorAll('.comentario, .comment, [data-comment]');
    comentarioEls.forEach(el=>{
      parts.push(el.textContent || el.value || "");
      // si tiene atributo data-comment explícito
      if(el.dataset && el.dataset.comment) parts.push(el.dataset.comment);
    });
    return stripDiacritics(parts.join(" ")).toLowerCase();
  }

  // ===== Filtrar tabla (cliente) =====
  function filterTableLocal(){
    const q = (searchInput.value||"").trim();
    unhighlight();
    const qnorm = stripDiacritics(q).toLowerCase();

    Array.from(table.tBodies[0].rows).forEach(tr=>{
      let match = true;

      // Búsqueda en nombre/codigo/comentario/otras celdas
      if(q){
        const hay = getRowSearchText(tr).includes(qnorm);
        match = hay;
      }

      // Filtrar por fechas si se usan
      if(match && (fIni.value || fFin.value)){
        const fechaTd = tr.cells[1]; // columna Fecha (ajusta índice si tu fecha no está en la columna 1)
        if(fechaTd){
          const f = fechaTd.textContent.trim();
          const fObj = new Date(f);
          if(fIni.value){ const minDate = new Date(fIni.value); if(fObj < minDate) match=false; }
          if(fFin.value){ const maxDate = new Date(fFin.value); if(fObj > maxDate) match=false; }
        }
      }

      tr.style.display = match ? "" : "none";
      if(match && q) highlightWithin(tr, searchInput.value);
    });

    // actualizar contador (opcional)
    const visible = Array.from(table.tBodies[0].rows).filter(r=> r.style.display !== "none").length;
    const cntEl = document.querySelector('#tabla-leads-count');
    if(cntEl) cntEl.textContent = visible;
  }

  // ===== Checkbox "Mostrar todo" =====
  function updateCheckboxState(){
    const hasDate = (fIni.value || fFin.value);

    if(!showAllCheckbox) return;
    if(hasDate) showAllCheckbox.removeAttribute('disabled');
    else { showAllCheckbox.checked=false; showAllCheckbox.setAttribute('disabled','disabled'); }
  }

  updateCheckboxState();

  if(showAllCheckbox){
    showAllCheckbox.addEventListener('change', function(){
      if(!(fIni.value || fFin.value)){
        alert('Seleccione al menos una fecha para usar "Mostrar todo".');
        showAllCheckbox.checked=false;
        return;
      }
      // Agregar input oculto y enviar form para "mostrar todo"
      let hidden = form.querySelector('input[name="show_all"]');
      if(!hidden){
        hidden = document.createElement('input');
        hidden.type='hidden'; hidden.name='show_all';
        form.appendChild(hidden);
      }
      hidden.value = showAllCheckbox.checked ? '1' : '';
      form.submit();
    });
  }

  // ===== Server-side universal search (fetch show_all=1 y reemplazo tbody) =====
  function debounce(fn, wait){
    let t;
    return function(...args){
      clearTimeout(t);
      t = setTimeout(()=>fn.apply(this,args), wait);
    };
  }

  async function fetchAndReplaceRows({q, f_ini, f_fin}){
    try{
      const params = new URLSearchParams();
      if(q) params.set('q', q);
      if(f_ini) params.set('f_ini', f_ini);
      if(f_fin) params.set('f_fin', f_fin);
      params.set('show_all', '1');

      const url = `${window.location.pathname}?${params.toString()}`;
      const resp = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' }});
      if(!resp.ok) return;
      const html = await resp.text();

      // parse response HTML
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');

      // replace tbody
      const newTbody = doc.querySelector('#tabla-leads tbody');
      const currentTbody = document.querySelector('#tabla-leads tbody');
      if(newTbody && currentTbody){
        currentTbody.replaceWith(newTbody.cloneNode(true));
      }

      // hide/replace pagination
      const newNav = doc.querySelector('nav[aria-label="Paginación leads"]');
      const currentNav = document.querySelector('nav[aria-label="Paginación leads"]');
      if(newNav && currentNav){
        // Si pedimos show_all=1 es probable que la respuesta venga en modo "mostrar todo".
        currentNav.style.display = 'none';
      } else if(currentNav){
        if(newNav) currentNav.replaceWith(newNav.cloneNode(true));
        else currentNav.style.display = 'none';
      }

      // reattach dblclick handlers for new rows
      document.querySelectorAll('#tabla-leads tbody tr.row-clickable').forEach(tr=>{
        tr.ondblclick = function(){ const codigo = this.querySelector('td:first-child')?.textContent?.trim(); if(codigo) editarLead(codigo); };
      });

    }catch(err){
      console.error('Error fetchAndReplaceRows:', err);
    }
  }

  const serverSearchHandler = debounce(function(){
    const q = (searchInput.value || "").trim();
    const f_ini_val = fIni.value || "";
    const f_fin_val = fFin.value || "";
    // si no hay criterio, recargar para restablecer paginación
    if(!q && !f_ini_val && !f_fin_val){
      window.location.href = window.location.pathname + location.search.replace(/(&|^)show_all=[^&]*/,'');
      return;
    }
    fetchAndReplaceRows({ q, f_ini: f_ini_val, f_fin: f_fin_val });
  }, 350);

  // ===== Listeners =====
  if(searchInput){
    // combinación: filtro local inmediato + búsqueda server-side (debounced)
    searchInput.addEventListener('input', function(){
      filterTableLocal();
      serverSearchHandler();
    });
  }
  if(fIni) fIni.addEventListener('change', ()=>{ updateCheckboxState(); filterTableLocal(); serverSearchHandler(); });
  if(fFin) fFin.addEventListener('change', ()=>{ updateCheckboxState(); filterTableLocal(); serverSearchHandler(); });

  // ===== Export helpers (mantuve tu lógica) =====
  function cellText(td){ return (td.textContent||"").trim(); }
  function rowIsVisible(tr){ return getComputedStyle(tr).display !== "none"; }

  function autoWidthsFromAOA(aoa){
    const cols = []; const maxCols = Math.max(...aoa.map(r=>r.length));
    for(let c=0;c<maxCols;c++){
      let w=8;
      for(let r=0;r<aoa.length;r++){
        const v = aoa[r][c] == null ? "" : String(aoa[r][c]);
        if(v.length>w) w=v.length;
      }
      cols.push({wch: Math.min(40, Math.max(8, w+2))});
    }
    return cols;
  }

  function tableToXLSX(selector, filename){
    const tbl = document.querySelector(selector); if(!tbl) return;
    const aoa=[]; const headRow = tbl.tHead.rows[0];
    if(headRow) aoa.push([...headRow.cells].map(cell=>cellText(cell)));
    Array.from(tbl.tBodies[0].rows).filter(rowIsVisible).forEach(tr=>{
      aoa.push([...tr.cells].map(cell=>{
        let txt = cellText(cell);
        if(/^-?\d+([.,]\d+)?$/.test(txt)){
          const n = Number(txt.replace(",",".")); if(!isNaN(n)) return n;
        }
        return txt;
      }));
    });
    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.aoa_to_sheet(aoa);
    ws["!cols"] = autoWidthsFromAOA(aoa);
    XLSX.utils.book_append_sheet(wb, ws, "Leads");
    XLSX.writeFile(wb, filename||"leads.xlsx");
  }

  if(exportBtn) exportBtn.addEventListener('click', ()=>tableToXLSX("#tabla-leads","leads.xlsx"));

  // inicializa estado local
  filterTableLocal();

});


// ==============================
// UBIGEO: departamento -> provincia -> distrito (SIN CAMBIOS, YA ES CORRECTO)
// ==============================
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    const selDep = document.getElementById('departamento');
    const selProv = document.getElementById('provincia');
    const selDist = document.getElementById('distrito');

    // Si no encuentra los 3 selects, salimos.
    if (!selDep || !selProv || !selDist) return;

    const API = window.UBIGEO_API;
    if (!API) return console.error('UBIGEO_API no definido');

    // ... (Resto de la lógica de Ubigeo es correcta y no se modificó) ...
    const reset = (el, placeholder) => {
      el.innerHTML = `<option value="">${placeholder || '-- Seleccione --'}</option>`;
      el.disabled = true;
    };
    const fill = (el, items, placeholder) => {
      reset(el, placeholder);
      items.forEach(it => {
        const opt = document.createElement('option');
        opt.value = it.id; // usar ID como value
        opt.textContent = it.nombre;
        el.appendChild(opt);
      });
      el.disabled = false;
    };
    const fetchJson = async (url) => {
      const r = await fetch(url, { credentials: 'same-origin' });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    };
    const loadDepartamentos = async () => {
      try {
        const data = await fetchJson(API.departamentos);
        fill(selDep, data, '-- Seleccione departamento --');
        const selectedId = selDep.dataset.selectedId;
        if (selectedId) {
          selDep.value = selectedId;
          await loadProvincias(selectedId);
        }
      } catch (err) {
        console.error('Error cargando departamentos:', err);
        reset(selDep, '-- Error cargando --');
        reset(selProv, '-- Seleccione provincia --');
        reset(selDist, '-- Seleccione distrito --');
      }
    };
    const loadProvincias = async (depId) => {
      if (!depId) { reset(selProv, '-- Seleccione provincia --'); reset(selDist, '-- Seleccione distrito --'); return; }
      try {
        const url = `${API.provincias}/${depId}`;
        const data = await fetchJson(url);
        fill(selProv, data, '-- Seleccione provincia --');
        const selectedId = selProv.dataset.selectedId;
        if (selectedId) {
          selProv.value = selectedId;
          await loadDistritos(selectedId);
        }
      } catch (err) {
        console.error('Error cargando provincias:', err);
        reset(selProv, '-- Error cargando --');
        reset(selDist, '-- Seleccione distrito --');
      }
    };
    const loadDistritos = async (provId) => {
      if (!provId) { reset(selDist, '-- Seleccione distrito --'); return; }
      try {
        const url = `${API.distritos}/${provId}`;
        const data = await fetchJson(url);
        fill(selDist, data, '-- Seleccione distrito --');
        const selectedId = selDist.dataset.selectedId;
        if (selectedId) selDist.value = selectedId;
      } catch (err) {
        console.error('Error cargando distritos:', err);
        reset(selDist, '-- Error cargando --');
      }
    };

    // Eventos onchange
    selDep.addEventListener('change', async () => {
      const depId = selDep.value || null;
      reset(selProv, '-- Cargando provincias --');
      reset(selDist, '-- Seleccione distrito --');
      if (depId) await loadProvincias(depId);
    });
    selProv.addEventListener('change', async () => {
      const provId = selProv.value || null;
      reset(selDist, '-- Cargando distritos --');
      if (provId) await loadDistritos(provId);
    });
    // Inicializa
    loadDepartamentos();
  });
})();

// -----------------------
// Notificaciones (polling + render) - REEMPLAZAR BLOQUE ANTIGUO
// -----------------------
(function () {
  'use strict';

  // función pública que inicializa el módulo (reusable)
  function initNotifModule(opts) {
    // ... (rest of initNotifModule omitted for brevity, no necesita cambios) ...
    opts = opts || {};
    const API = opts.api || '/leads/notifications/panel';
    const root = document.getElementById(opts.rootId || 'notif-dropdown-root-sidebar');
    const toggle = document.getElementById(opts.toggleId || 'notifDropdown');
    const menu = document.getElementById(opts.menuId || 'notif-list-sidebar');
    const badge = document.getElementById(opts.badgeId || 'notif-count');
    const itemsProg = document.getElementById(opts.itemsProgramadasId || 'notif-items-programadas');
    const itemsSin = document.getElementById(opts.itemsSinId || 'notif-items-sin-iniciar');

    if (!root || !toggle || !menu || !badge || !itemsProg || !itemsSin) {
      console.debug('initNotifModule: elementos no encontrados', {
        root: !!root, toggle: !!toggle, menu: !!menu, badge: !!badge, itemsProg: !!itemsProg, itemsSin: !!itemsSin
      });
      return { ok: false };
    }

    if (root.__notif_inited) {
      console.debug('initNotifModule: ya inicializado');
      return { ok: true };
    }
    root.__notif_inited = true;

    const LS_KEY = 'crm_seen_notifs_v1';

    function readSeenMap() {
      try { return JSON.parse(localStorage.getItem(LS_KEY) || '{}'); }
      catch (e) { return {}; }
    }
    function writeSeenMap(obj) {
      try { localStorage.setItem(LS_KEY, JSON.stringify(obj)); } catch (e) { /* ignore */ }
    }
    // ... (otras funciones internas como showQuickToast y escapeHtml omitidas) ...

    function renderList(container, items, type) {
      // ... (cuerpo de renderList omitido)
      container.innerHTML = '';
      if (!items || items.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'dropdown-item small text-muted';
        empty.textContent = '— Ninguno —';
        container.appendChild(empty);
        return;
      }

      const MAX_VISIBLE = 3;

      if (type === 'programadas') {
        items.forEach(it => {
          const a = document.createElement('a');
          a.className = 'dropdown-item small';
          a.href = '/leads/seguimiento/' + (it.codigo || it.id);
          const smallDate = it.fecha_programada
            ? `<div class="small text-muted">${it.fecha_programada}</div>`
            : '';
          a.innerHTML = `<strong>${it.codigo ? it.codigo + ' — ' : ''}${it.nombre || 'Sin nombre'}</strong>${smallDate}`;
          container.appendChild(a);
        });

        const more = document.createElement('div');
        more.className = 'dropdown-item small text-center text-muted';
        more.style.borderTop = '1px solid #eef2f7';
        more.style.marginTop = '.1rem';
        more.innerHTML = `           <a href="/leads/programados" style="display:block">Ver todos los programados</a>         `;
        container.appendChild(more);
        return;
      }

      if (type === 'sin') {
        const toShow = items.slice(0, MAX_VISIBLE);
        toShow.forEach(it => {
          const a = document.createElement('a');
          a.className = 'dropdown-item small';
          a.href = '/leads/seguimiento/' + (it.codigo || it.id);
          a.innerHTML = `<strong>${it.codigo ? it.codigo + ' — ' : ''}${it.nombre || 'Sin nombre'}</strong>`;
          container.appendChild(a);
        });

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
    // ... (resto de funciones y listeners del módulo de notificaciones omitido) ...

    async function fetchAndProcess() {
        try {
            const resp = await fetch(API, { credentials: 'same-origin' });
            if (!resp.ok) { console.warn('Notif fetch failed', resp.status); return; }
            const data = await resp.json();
            const prev = readSeenMap();
            updateUI(data);
            // La función notifyNew no está definida aquí, si da error debes definirla o quitarla
            // const newState = notifyNew(prev, data.programadas || [], data.sin_iniciar || []);
            // writeSeenMap(newState);
            writeSeenMap(prev); // Mantiene el mapa de vistos si no hay función notifyNew
        } catch (err) {
            console.error('Error fetching notifications', err);
        }
    }

    function showMenu() { root.classList.add('open'); menu.style.display = 'block'; toggle.setAttribute('aria-expanded', 'true'); }
    function hideMenu() { root.classList.remove('open'); menu.style.display = 'none'; toggle.setAttribute('aria-expanded', 'false'); }
    function toggleMenu(ev) {
        ev && ev.preventDefault(); ev && ev.stopPropagation();
        const visible = menu.style.display === 'block' || root.classList.contains('open');
        visible ? hideMenu() : showMenu();
    }

    if (!toggle.__notif_bound) {
        toggle.addEventListener('click', toggleMenu, { passive: false });
        toggle.__notif_bound = true;
    }

    if (!document.__notif_outbound) {
        document.addEventListener('click', function (ev) {
            if (!root.contains(ev.target)) hideMenu();
        });
        document.addEventListener('keydown', function (ev) { if (ev.key === 'Escape') hideMenu(); });
        document.__notif_outbound = true;
    }

    fetchAndProcess();
    root.__notif_poll = setInterval(fetchAndProcess, 60 * 1000);

    return {
        ok: true,
        refresh: fetchAndProcess,
        teardown: function () {
            clearInterval(root.__notif_poll);
            root.__notif_inited = false;
        }
    };
  }

  window.initNotifModule = initNotifModule;
  document.addEventListener('DOMContentLoaded', function () {
    try { initNotifModule(); } catch (e) { console.error('initNotifModule error', e); }
  });
})();
