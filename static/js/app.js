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

// static/js/app.js
(function () {
  const ICONS = {
    danger:  'fa-triangle-exclamation',
    warning: 'fa-circle-exclamation',
    success: 'fa-circle-check',
    info:    'fa-circle-info'
  };

  function createToast(root, category, msg) {
    const type = ['danger','warning','success','info'].includes(category) ? category : 'info';
    const div = document.createElement('div');
    div.className = `toast toast-${type}`;
    div.innerHTML = `
      <i class="fa-solid ${ICONS[type]}" aria-hidden="true"></i>
      <div class="toast-msg">${msg}</div>
      <button class="toast-close" aria-label="Cerrar">&times;</button>
    `;

    root.appendChild(div);

    const close = () => { div.classList.add('hide'); setTimeout(() => div.remove(), 200); };
    div.querySelector('.toast-close').addEventListener('click', close);
    setTimeout(close, type === 'danger' ? 6000 : 4000);
  }

  document.addEventListener('DOMContentLoaded', function () {
    const root = document.getElementById('toast-root');
    if (!root) return;

    let flashes = [];
    try {
      const raw = root.dataset.flashes || '[]';
      flashes = JSON.parse(raw);
    } catch (e) {
      console.error('Flashes JSON inválido:', e);
    }

    if (Array.isArray(flashes)) {
      flashes.forEach(([category, msg]) => createToast(root, category, msg));
      // Limpia el dato para que no se reinyecte si haces navegación parcial
      root.dataset.flashes = '[]';
    }
  });
})();
