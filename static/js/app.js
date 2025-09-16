// static/js/app.js
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    // --- Elementos de la vista de seguimiento ---
    const procesoSelect   = document.getElementById("proceso_select");
    const canalSelect     = document.getElementById("canal_contacto"); // <— corregido
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

    // Si no es la vista de seguimiento, no hacemos nada
    if (!form || !procesoSelect || !secCanal || !secFecha || !secCot || !secMot) return;

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
    updateUI(); // al cargar con lo que ya esté seleccionado

    function pushToast(message, kind="warning"){
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

      // Validación cliente (usa el id nuevo)
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

      // Aseguramos que ningún bloque quede disabled al enviar
      blocks.forEach(b => setDisabled(b, false));
    });
  });
})();


// ===============================
// 🔎 Buscador y exportar (SIN CAMBIOS)
// ===============================
(function(){
  document.addEventListener("DOMContentLoaded", function(){
    function stripDiacritics(s){
      if (!s) return "";
      try { return s.normalize("NFD").replace(/[\u0300-\u036f]/g, ""); }
      catch { return String(s); }
    }
    function buildNormMap(s){
      const map = []; let norm = "";
      for (let i = 0; i < s.length; i++){
        const base = stripDiacritics(s[i]);
        for (let j = 0; j < base.length; j++){ norm += base[j]; map.push(i); }
      }
      return { norm, map };
    }
    function findRanges(orig, q){
      const { norm, map } = buildNormMap(orig);
      const n = norm.toLowerCase();
      const nq = stripDiacritics(q).toLowerCase();
      const ranges = []; if (!nq) return ranges;
      let idx = 0;
      while ((idx = n.indexOf(nq, idx)) !== -1){
        const start = map[idx]; const end = map[idx + nq.length - 1] + 1;
        ranges.push([start, end]); idx += nq.length;
      }
      return ranges;
    }
    function highlightTextNode(node, q){
      const text = node.data; const ranges = findRanges(text, q);
      if (!ranges.length) return;
      const frag = document.createDocumentFragment(); let last = 0;
      for (const [s, e] of ranges){
        if (s > last) frag.appendChild(document.createTextNode(text.slice(last, s)));
        const mark = document.createElement("mark"); mark.className = "hl";
        mark.textContent = text.slice(s, e); frag.appendChild(mark); last = e;
      }
      if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
      node.replaceWith(frag);
    }
    function highlightWithin(el, q){
      if (!q) return; const nodes = Array.from(el.childNodes);
      for (const node of nodes){
        if (node.nodeType === 3){ highlightTextNode(node, q); }
        else if (node.nodeType === 1){
          const tag = node.tagName.toLowerCase();
          if (tag === "script" || tag === "style") continue;
          highlightWithin(node, q);
        }
      }
    }
    function unhighlight(container){
      container.querySelectorAll("mark.hl").forEach(m => {
        m.replaceWith(document.createTextNode(m.textContent));
      });
    }
    function ensureNoResultsRow(tbody, colSpan){
      let row = tbody.querySelector("tr.no-results-row");
      if (!row){
        row = document.createElement("tr"); row.className = "no-results-row";
        const td = document.createElement("td"); td.colSpan = colSpan || 1;
        td.className = "text-center text-muted";
        td.textContent = "No hay resultados para el filtro.";
        row.appendChild(td); tbody.appendChild(row);
      }
      return row;
    }
    function filterTable(input){
      const targetSel  = input.getAttribute("data-target");
      const counterSel = input.getAttribute("data-counter");
      if (!targetSel) return;
      const table = document.querySelector(targetSel); if (!table) return;
      const q = (input.value || "").trim();
      const tbody = table.tBodies[0] || table.querySelector("tbody"); if (!tbody) return;
      unhighlight(table);
      const rows = [...tbody.querySelectorAll("tr")].filter(tr =>
        !tr.classList.contains("no-data") && !tr.classList.contains("no-results-row")
      );
      if (rows.length === 0) return;
      let visibleCount = 0; const qNorm = stripDiacritics(q).toLowerCase();
      rows.forEach(tr => {
        const text = stripDiacritics(tr.textContent || "").toLowerCase();
        const match = q === "" || text.includes(qNorm);
        tr.style.display = match ? "" : "none"; if (match) visibleCount++;
      });
      const colSpan = (table.tHead && table.tHead.rows[0]) ? table.tHead.rows[0].cells.length : 1;
      let noRes = tbody.querySelector("tr.no-results-row");
      if (visibleCount === 0){
        noRes = ensureNoResultsRow(tbody, colSpan); noRes.style.display = "";
      } else if (noRes){ noRes.style.display = "none"; }
      if (q){
        rows.forEach(tr => {
          if (tr.style.display === "none") return;
          [...tr.cells].forEach(td => highlightWithin(td, q));
        });
      }
      if (counterSel){
        const cnt = document.querySelector(counterSel);
        if (cnt) cnt.textContent = visibleCount;
      }
    }
    document.querySelectorAll("button.search-btn").forEach(btn => {
      btn.addEventListener("click", function(){ const inputSel = btn.getAttribute("data-input");
        const input = inputSel ? document.querySelector(inputSel) : null; if (input) filterTable(input);
      });
    });
    document.querySelectorAll("input.live-search").forEach(inp => {
      if (inp.form){ inp.form.addEventListener("submit", e => { e.preventDefault(); filterTable(inp); }); }
      inp.addEventListener("keydown", e => { if (e.key === "Enter"){ e.preventDefault(); filterTable(inp); } });
    });
    document.querySelectorAll("button.clear-btn").forEach(btn => {
      btn.addEventListener("click", function(){
        const inputSel = btn.getAttribute("data-input");
        const input = inputSel ? document.querySelector(inputSel) : null; if (!input) return;
        const table = document.querySelector(input.getAttribute("data-target"));
        if (table) unhighlight(table); input.value = ""; filterTable(input); input.focus();
      });
    });
    document.querySelectorAll("input.live-search").forEach(inp => {
      if (inp.getAttribute("data-counter")) filterTable(inp);
    });
  });
})();

(function () {
  if (window.__EXPORT_TABLE_INIT__) return;
  window.__EXPORT_TABLE_INIT__ = true;
  document.addEventListener("DOMContentLoaded", function () {
    function cellText(td){ return (td.textContent || "").replace(/\s+/g, " ").trim(); }
    function rowIsVisible(tr){ return getComputedStyle(tr).display !== "none"; }
    function autoWidthsFromAOA(aoa){
      const cols = []; const maxCols = Math.max(...aoa.map(r => r.length));
      for (let c = 0; c < maxCols; c++){
        let w = 8;
        for (let r = 0; r < aoa.length; r++){
          const v = (aoa[r][c] == null ? "" : String(aoa[r][c]));
          if (v.length > w) w = v.length;
        }
        cols.push({ wch: Math.min(40, Math.max(8, w + 2)) });
      }
      return cols;
    }
    function tableToXLSX(tableSelector, filename){
      if (typeof XLSX === "undefined"){ alert("No se encontró la librería XLSX. Revisa el <script> en base.html."); return; }
      const table = document.querySelector(tableSelector); if (!table) return;
      const aoa = []; const headRow = table.tHead && table.tHead.rows[0];
      let colCount = 0;
      if (headRow){ const headers = [...headRow.cells].map(th => cellText(th)); colCount = headers.length; aoa.push(headers); }
      const tbody = table.tBodies[0] || table.querySelector("tbody");
      if (tbody){
        const rows = [...tbody.querySelectorAll("tr")].filter(
          tr => !tr.classList.contains("no-data") && !tr.classList.contains("no-results-row") && rowIsVisible(tr)
        );
        rows.forEach(tr => {
          const cells = [...tr.cells].slice(0, colCount || tr.cells.length).map(td => {
            let txt = cellText(td);
            if (/^-?\d+([.,]\d+)?$/.test(txt)){ const num = Number(txt.replace(",", ".")); if (!Number.isNaN(num)) return num; }
            return txt;
          });
          aoa.push(cells);
        });
      }
      const wb = XLSX.utils.book_new(); const ws = XLSX.utils.aoa_to_sheet(aoa);
      ws["!cols"] = autoWidthsFromAOA(aoa); XLSX.utils.book_append_sheet(wb, ws, "Reporte");
      const fname = (filename && filename.trim()) || "reportes.xlsx"; XLSX.writeFile(wb, fname);
    }
    document.querySelectorAll("button.export-btn").forEach(btn => {
      if (btn.dataset.exportBound === "1") return; btn.dataset.exportBound = "1";
      btn.addEventListener("click", function (e) {
        e.preventDefault(); e.stopPropagation();
        const tableSel = btn.getAttribute("data-table") || "#tabla-leads";
        const name = btn.getAttribute("data-filename") || "reportes.xlsx";
        tableToXLSX(tableSel, name);
      }, { once: false });
    });
  });
})();


// ==============================
// UBIGEO: departamento -> provincia -> distrito
// ==============================
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    const selDep = document.getElementById('departamento');
    const selProv = document.getElementById('provincia');
    const selDist = document.getElementById('distrito');

    // Si no existen los selects en la página actual, salir sin tocar nada.
    if (!selDep || !selProv || !selDist) return;

    const API = (window && window.UBIGEO_API) ? window.UBIGEO_API : null;
    if (!API || !API.departamentos || !API.provincias || !API.distritos) {
      console.error('UBIGEO API no definido en window.UBIGEO_API');
      return;
    }

    const reset = (el, label) => {
      el.innerHTML = '';
      const o = document.createElement('option');
      o.value = '';
      o.textContent = label || '-- Seleccione --';
      el.appendChild(o);
    };

    const fill = (el, items, placeholder) => {
      reset(el, placeholder);
      (items || []).forEach(it => {
        const o = document.createElement('option');
        o.value = it.nombre || '';       // value = nombre (mantener esquema DB)
        o.textContent = it.nombre || '';
        if (it.id !== undefined && it.id !== null) o.dataset.id = String(it.id);
        el.appendChild(o);
      });
    };

    const fetchJson = async (url) => {
      const r = await fetch(url, { credentials: 'same-origin' });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return await r.json();
    };

    const loadDepartamentos = async () => {
      try {
        const data = await fetchJson(API.departamentos);
        fill(selDep, data, '-- Seleccione departamento --');

        // Preselección por atributo data-selected-name (edit) o value ya presente
        const preDep = (selDep.dataset && selDep.dataset.selectedName) ? selDep.dataset.selectedName : (selDep.value || '');
        if (preDep) {
          const opt = [...selDep.options].find(o => o.value === preDep);
          if (opt) {
            selDep.value = opt.value;
            const depId = opt.dataset.id;
            if (depId) await loadProvincias(depId);
          }
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
        const url = API.provincias.endsWith('/') ? API.provincias + depId : API.provincias + '/' + depId;
        const data = await fetchJson(url);
        fill(selProv, data, '-- Seleccione provincia --');

        const preProv = (selProv.dataset && selProv.dataset.selectedName) ? selProv.dataset.selectedName : (selProv.value || '');
        if (preProv) {
          const opt = [...selProv.options].find(o => o.value === preProv);
          if (opt) {
            selProv.value = opt.value;
            const provId = opt.dataset.id;
            if (provId) await loadDistritos(provId);
          }
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
        const url = API.distritos.endsWith('/') ? API.distritos + provId : API.distritos + '/' + provId;
        const data = await fetchJson(url);
        fill(selDist, data, '-- Seleccione distrito --');

        const preDist = (selDist.dataset && selDist.dataset.selectedName) ? selDist.dataset.selectedName : (selDist.value || '');
        if (preDist) {
          const opt = [...selDist.options].find(o => o.value === preDist);
          if (opt) selDist.value = opt.value;
        }
      } catch (err) {
        console.error('Error cargando distritos:', err);
        reset(selDist, '-- Error cargando --');
      }
    };

    // Eventos
    selDep.addEventListener('change', async function () {
      const opt = selDep.selectedOptions[0];
      const depId = opt ? opt.dataset.id : null;
      reset(selProv, '-- Cargando provincias --');
      reset(selDist, '-- Seleccione distrito --');
      await loadProvincias(depId);
    });

    selProv.addEventListener('change', async function () {
      const opt = selProv.selectedOptions[0];
      const provId = opt ? opt.dataset.id : null;
      reset(selDist, '-- Cargando distritos --');
      await loadDistritos(provId);
    });

    // Inicializa
    loadDepartamentos();
  });
})();
