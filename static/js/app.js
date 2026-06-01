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
// UBIGEO: departamento -> provincia -> distrito
// ==============================
(function () {
    'use strict';

    const UBIGEO = {};
    window.UBIGEO = UBIGEO; // exponer globalmente para poder llamar desde create.html

    document.addEventListener('DOMContentLoaded', function () {
        const selDep = document.getElementById('departamento');
        const selProv = document.getElementById('provincia');
        const selDist = document.getElementById('distrito');

        if (!selDep || !selProv || !selDist) return;

        const API = window.UBIGEO_API;
        if (!API) return console.error('UBIGEO_API no definido');

        const reset = (el, placeholder) => {
            el.innerHTML = `<option value="">${placeholder || '-- Seleccione --'}</option>`;
            el.disabled = true;
        };

        const fill = (el, items, placeholder) => {
            reset(el, placeholder);
            items.forEach(it => {
                const opt = document.createElement('option');
                opt.value = it.id;
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

        // Función principal para cargar departamentos
        UBIGEO.loadDepartamentos = async (selectedDep = null, selectedProv = null, selectedDist = null) => {
            try {
                const data = await fetchJson(API.departamentos);
                fill(selDep, data, '-- Seleccione departamento --');

                const depId = selectedDep || selDep.dataset.selectedId || '';
                if (depId) {
                    selDep.value = depId;
                    await UBIGEO.loadProvincias(depId, selectedProv, selectedDist);
                }
            } catch (err) {
                console.error('Error cargando departamentos:', err);
                reset(selDep, '-- Error cargando --');
                reset(selProv, '-- Seleccione provincia --');
                reset(selDist, '-- Seleccione distrito --');
            }
        };

        UBIGEO.loadProvincias = async (depId, selectedProv = null, selectedDist = null) => {
            if (!depId) { reset(selProv, '-- Seleccione provincia --'); reset(selDist, '-- Seleccione distrito --'); return; }
            try {
                const url = `${API.provincias}/${depId}`;
                const data = await fetchJson(url);
                fill(selProv, data, '-- Seleccione provincia --');

                const provId = selectedProv || selProv.dataset.selectedId || '';
                if (provId) {
                    selProv.value = provId;
                    await UBIGEO.loadDistritos(provId, selectedDist);
                }
            } catch (err) {
                console.error('Error cargando provincias:', err);
                reset(selProv, '-- Error cargando --');
                reset(selDist, '-- Seleccione distrito --');
            }
        };

        UBIGEO.loadDistritos = async (provId, selectedDist = null) => {
            if (!provId) { reset(selDist, '-- Seleccione distrito --'); return; }
            try {
                const url = `${API.distritos}/${provId}`;
                const data = await fetchJson(url);
                fill(selDist, data, '-- Seleccione distrito --');

                const distId = selectedDist || selDist.dataset.selectedId || '';
                if (distId) selDist.value = distId;
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
            if (depId) await UBIGEO.loadProvincias(depId);
        });

        selProv.addEventListener('change', async () => {
            const provId = selProv.value || null;
            reset(selDist, '-- Cargando distritos --');
            if (provId) await UBIGEO.loadDistritos(provId);
        });

        // Inicializa
        const dep = selDep.dataset.selectedId || '';
        const prov = selProv.dataset.selectedId || '';
        const dist = selDist.dataset.selectedId || '';

        UBIGEO.loadDepartamentos(dep, prov, dist);
    });
})();

// -----------------------
// Notificaciones - Ahora en módulo separado
// -----------------------
// El módulo de notificaciones se ha movido a: /static/js/notifications/notif-module.js
// Se carga automáticamente desde base.html
// API disponible: window.initNotifModule(opciones)

// =========================================================================
    // 2. Lógica de Modales de Flash (Duplicado y Éxito) y Botones
    // =========================================================================

    const flashMessages = window.FLASH_MESSAGES || [];
    const $form = document.querySelector('form[action*="/leads/crear"]');
    const $forceSaveInput = document.getElementById('forceSaveInput');
    const $rucDniInput = document.getElementById('ruc_dni');
    const $telefonoInput = document.getElementById('telefono');
    
    // Elementos del Modal de Duplicados
    const $modalEl = document.getElementById('leadDuplicateModal');
    const $duplicateField = document.getElementById('duplicateField');
    const $firstLeadRow = document.getElementById('firstLeadRow');
    const $additionalLeadsContainer = document.getElementById('additionalLeadsContainer');
    const $additionalLeadsTableBody = document.getElementById('additionalLeadsTableBody');
    const $toggleAdditionalLeads = document.getElementById('toggleAdditionalLeads');
    const $btnGoToExisting = document.getElementById('btnGoToExistingLead');
    const $btnForceSave = document.getElementById('btnForceSave');

    /** Genera una fila de tabla para un lead. */
    function createLeadRow(lead) {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${lead.codigo}</td>
            <td>${lead.estado}</td>
            <td>${lead.asignado_a}</td>
            <td>${lead.ultima_actualizacion}</td>
            <td class="text-center">
                <a href="${window.URL_SEGUIMIENTO_PREFIX}${lead.codigo}" class="btn btn-sm btn-outline-primary">Ver</a>
            </td>
        `;
        return row;
    }

    /** Maneja la carga de la tabla de leads duplicados. */
    async function loadDuplicateLeads(searchValue, searchParam) {
        $firstLeadRow.innerHTML = '';
        $additionalLeadsTableBody.innerHTML = '';
        $additionalLeadsContainer.style.display = 'none';
        $toggleAdditionalLeads.style.display = 'none';

        if (!searchValue || !window.URL_DUPLICATES_API) return;

        try {
            const url = window.URL_DUPLICATES_API + searchValue;
            const response = await fetch(url);
            const leads = await response.json(); // Esperamos un array de leads

            if (leads.length > 0) {
                // 1. Mostrar el PRIMER Lead en la sección principal
                const firstLead = leads[0];
                $firstLeadRow.appendChild(createLeadRow(firstLead));
                $btnGoToExisting.href = `${window.URL_SEGUIMIENTO_PREFIX}${firstLead.codigo}`;
                $btnGoToExisting.disabled = false;
                
                // 2. Si hay MÁS leads, mostrarlos en la sección adicional
                if (leads.length > 1) {
                    const additionalLeads = leads.slice(1);
                    
                    additionalLeads.forEach(lead => {
                        $additionalLeadsTableBody.appendChild(createLeadRow(lead));
                    });

                    $toggleAdditionalLeads.style.display = 'block';
                    $toggleAdditionalLeads.textContent = `Mostrar los ${leads.length - 1} Leads Adicionales`;
                    
                    // Manejar el toggle
                    $toggleAdditionalLeads.onclick = () => {
                        const isHidden = $additionalLeadsContainer.style.display === 'none';
                        $additionalLeadsContainer.style.display = isHidden ? 'block' : 'none';
                        $toggleAdditionalLeads.textContent = isHidden ? 'Ocultar Leads Adicionales' : `Mostrar los ${leads.length - 1} Leads Adicionales`;
                    };
                }
            }
        } catch (error) {
            console.error('Error al cargar leads duplicados:', error);
            // Mostrar un mensaje de error en el modal si falla la API
            $firstLeadRow.innerHTML = `<tr><td colspan="5" class="text-danger text-center">Error al cargar la lista de leads relacionados.</td></tr>`;
            $btnGoToExisting.disabled = true;
        }
    }


    flashMessages.forEach(flash => {
        const { category, message } = flash;

        // --- Manejo de éxito de creación (lead_created) ---
        if (category === 'lead_created') {
            const match = message.match(/Lead (L\d+) creado/i);
            const leadCode = match ? match[1] : null;

            if (leadCode) {
                const modal = new bootstrap.Modal(document.getElementById('leadCreatedModal')); 
                document.getElementById('successMessage').textContent = message;
                document.getElementById('btnGoToSeguimiento').href = window.URL_SEGUIMIENTO_PREFIX + leadCode;
                modal.show();
            }
        }
        
        // --- Manejo de duplicado de creación (warning_duplicate) ---
        if (category === 'warning_duplicate') {
            // Ejemplo de mensaje esperado: "Duplicado detectado por DNI/RUC."
            const matchField = message.match(/Duplicado detectado por ([A-Z\/]+)\./i);
            const duplicatedFieldType = matchField ? matchField[1] : 'Desconocido'; 

            // 1. Configuración de parámetros de búsqueda
            let searchValue = '';
            let searchParam = '';
            
            if (duplicatedFieldType.includes('DNI/RUC') && $rucDniInput) {
                searchValue = $rucDniInput.value.trim();
                searchParam = 'ruc_dni';
            } else if (duplicatedFieldType.includes('TELÉFONO') && $telefonoInput) {
                searchValue = $telefonoInput.value.trim();
                searchParam = 'telefono';
            }
            
            // 2. Mostrar tipo de duplicidad
            $duplicateField.textContent = duplicatedFieldType;

            // 3. Cargar datos de duplicados desde la API y configurar tabla/botones
            if (searchValue) {
                loadDuplicateLeads(searchValue);
            } else {
                $firstLeadRow.innerHTML = `<tr><td colspan="5" class="text-muted text-center">No se encontró el valor de búsqueda (DNI/RUC o Teléfono) para consultar leads.</td></tr>`;
                $btnGoToExisting.disabled = true;
            }

            // 4. Manejar el botón "Guardar de Todas Formas"
            if ($btnForceSave && $forceSaveInput && $form) {
                $btnForceSave.onclick = function() {
                    $forceSaveInput.value = 'true';
                    const modalInstance = bootstrap.Modal.getInstance($modalEl) || new bootstrap.Modal($modalEl);
                    modalInstance.hide(); 
                    $form.submit();
                };
            }
            
            // 5. Mostrar modal
            const modal = new bootstrap.Modal($modalEl);
            modal.show();
        }
    });

  // =========================================
// Exportar a PDF con columnas específicas
// =========================================
function exportToPDF() {
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF("l", "pt", "a4");

  const table = document.querySelector("#tabla-leads tbody");
  if (!table) {
    Swal.fire({
      icon: "warning",
      title: "Sin datos",
      text: "No se encontró ninguna tabla para exportar.",
      confirmButtonColor: "#198754"
    });
    return;
  }

  const selectedColumns = [0, 1, 3, 4, 5, 6, 7, 8, 14, 16];

  const headers = Array.from(document.querySelectorAll("#tabla-leads thead th"))
    .map((th, idx) => ({ text: th.innerText.trim(), index: idx }))
    .filter(h => selectedColumns.includes(h.index))
    .map(h => h.text);

  const rows = Array.from(table.querySelectorAll("tr"))
    .filter(tr => tr.style.display !== "none")
    .map(tr =>
      Array.from(tr.querySelectorAll("td"))
        .filter((_, idx) => selectedColumns.includes(idx))
        .map(td => td.innerText.trim())
    );

  if (rows.length === 0) {
    Swal.fire({
      icon: "info",
      title: "Sin registros visibles",
      text: "No hay registros visibles para exportar.",
      confirmButtonColor: "#198754"
    });
    return;
  }

  // ============================
  // Usuario en el título
  // ============================
  const loggedUserName =
    window.loggedUserName ??
    document.querySelector('meta[name="logged-user-name"]')?.content ??
    "Usuario";
  const loggedUserUsername =
    window.loggedUserUsername ??
    document.querySelector('meta[name="logged-user-username"]')?.content ??
    "sin_usuario";
  const leadsViewName =
    window.leadsViewName ??
    document.querySelector("#leads-view-name")?.dataset.viewName ??
    "";

  let titleText = "Reporte de Leads";
  if (leadsViewName) titleText += ` - ${leadsViewName}`;
  titleText += ` (${loggedUserName} - ${loggedUserUsername})`;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(14);
  doc.text(titleText, 40, 50);

  // ============================
  // Intento de cargar el logo
  // ============================
  const brandForPdf = document.documentElement.getAttribute('data-brand') || (document.cookie.match(/(?:^|; )brand=([^;]+)/) || [])[1] || 'orbes';
  const logoPath = brandForPdf === 'lovol' ? "/static/img/lovol-peru.png" : "/static/img/logo.png";
  const logoWidth = 180;
  const logoHeight = 40;

  const pageWidth = doc.internal.pageSize.getWidth();
  const logoX = pageWidth - logoWidth - 40;
  const logoY = 25;

  const img = new Image();
  img.src = logoPath;

  img.onload = function () {
    doc.addImage(img, "PNG", logoX, logoY, logoWidth, logoHeight);
    generarTablaYGuardar(doc, headers, rows);
  };

  // Si falla → igual se genera el PDF
  img.onerror = function () {
    generarTablaYGuardar(doc, headers, rows);
  };
}

// =============================
// Función que SIEMPRE genera PDF
// =============================
function generarTablaYGuardar(doc, headers, rows) {
  doc.autoTable({
    startY: 80,
    head: [headers],
    body: rows,
    styles: { fontSize: 8, halign: "center", valign: "middle" },
    headStyles: {
      fillColor: [205, 225, 255],
      textColor: 0,
      fontStyle: "bold",
    },
    alternateRowStyles: { fillColor: [245, 245, 245] },
    margin: { left: 40, right: 40 },
  });

  const date = new Date().toLocaleString();
  const loggedUserName =
    window.loggedUserName ??
    document.querySelector('meta[name="logged-user-name"]')?.content ??
    "Usuario";
  const loggedUserUsername =
    window.loggedUserUsername ??
    document.querySelector('meta[name="logged-user-username"]')?.content ??
    "sin_usuario";
  const pageHeight = doc.internal.pageSize.height;
  
  doc.setFontSize(8);
  doc.text(`Generado: ${date}`, 40, pageHeight - 30);
  doc.text(`Descargado por: ${loggedUserName} (${loggedUserUsername})`, 40, pageHeight - 20);

  doc.save("reporte_leads.pdf");
}

document.addEventListener("DOMContentLoaded", () => {
  const btnPdf = document.getElementById("btn-export-pdf");
  if (btnPdf) {
    btnPdf.addEventListener("click", exportToPDF);
  }
});

// Brand toggle: clicking the sidebar logo swaps brand, animates logo and sets cookie
document.addEventListener('DOMContentLoaded', function() {
  function getCookie(name) {
    const m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]+)'));
    return m ? decodeURIComponent(m[1]) : null;
  }
  function setCookie(name, value, days) {
    const maxAge = days ? String(60 * 60 * 24 * days) : '';
    document.cookie = name + '=' + encodeURIComponent(value) + ';path=/' + (maxAge ? ';max-age=' + maxAge : '');
  }
  function currentBrand() {
    return document.documentElement.getAttribute('data-brand') || getCookie('brand') || 'orbes';
  }
  function brandLogoPath(brand) {
    return brand === 'lovol' ? '/static/img/lovol-peru.png' : '/static/img/logo.png';
  }

  function animateLogoSwap(container, oldImg, newSrc) {
    if (!container || !oldImg) return;
    container.style.position = container.style.position || 'relative';
    const newImg = document.createElement('img');
    newImg.src = newSrc;
    newImg.alt = oldImg.alt || '';
    newImg.style.position = 'absolute';
    newImg.style.left = '0';
    newImg.style.top = '0';
    newImg.style.width = '100%';
    newImg.style.height = 'auto';
    newImg.style.opacity = '0';
    newImg.style.transition = 'opacity 400ms ease, transform 400ms ease';
    newImg.style.transform = 'scale(0.95)';
    // keep same id after swap
    newImg.id = 'app-logo-temp';
    container.appendChild(newImg);

    newImg.onload = function() {
      requestAnimationFrame(function() {
        newImg.style.opacity = '1';
        newImg.style.transform = 'scale(1)';
        oldImg.style.transition = 'opacity 350ms ease, transform 350ms ease';
        oldImg.style.opacity = '0';
        oldImg.style.transform = 'scale(1.05)';
      });

      setTimeout(function() {
        try { oldImg.remove(); } catch (e) {}
        newImg.id = 'app-logo';
      }, 420);
    };
  }

  const toggle = document.getElementById('brand-toggle');
  if (!toggle) return;
  toggle.addEventListener('click', function() {
    const cur = currentBrand();
    const next = cur === 'lovol' ? 'orbes' : 'lovol';
    // persist brand for server-side filtering
    setCookie('brand', next, 30);
    // update immediate UI
    document.documentElement.setAttribute('data-brand', next);
    const container = toggle.closest('.logo') || document.querySelector('.logo');
    const oldImg = container ? container.querySelector('#app-logo') : null;
    animateLogoSwap(container, oldImg, brandLogoPath(next));
    // reload after animation so server-side lists (campañas/ferias) are filtered
    setTimeout(function(){ window.location.reload(); }, 700);
  });
});
