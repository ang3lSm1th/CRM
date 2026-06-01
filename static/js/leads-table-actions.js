document.addEventListener("DOMContentLoaded", function () {
  const cfg = document.getElementById("leads-table-config");
  const btnClear = document.getElementById("btn-clear");

  function initPredictionPopovers() {
    if (typeof bootstrap === "undefined" || !bootstrap.Popover) return;

    document.querySelectorAll("[data-bs-toggle='popover']").forEach(function (el) {
      if (bootstrap.Popover.getInstance(el)) return;
      new bootstrap.Popover(el, {
        trigger: "hover focus",
        placement: "left",
        html: true,
        sanitize: false,
      });
    });
  }

  initPredictionPopovers();

  if (btnClear) {
    btnClear.addEventListener("click", function () {
      window.location.href = window.location.pathname;
    });
  }

  if (!cfg) return;

  if (cfg.dataset.viewName) {
    window.leadsViewName = cfg.dataset.viewName;
  }

  const followBase = cfg.dataset.followBase || "";
  const preset = cfg.dataset.preset || "";

  function irSeguimiento(codigo) {
    if (!codigo || codigo === "None") {
      if (typeof Swal !== "undefined") {
        Swal.fire({ icon: "warning", title: "Codigo de lead no valido." });
      } else {
        alert("Codigo de lead no valido.");
      }
      return;
    }

    if (!followBase) return;
    const params = new URLSearchParams();
    if (preset) params.set("preset", preset);
    params.set("next", window.location.pathname + window.location.search);
    const suffix = params.toString() ? ("?" + params.toString()) : "";
    window.location.href = followBase + encodeURIComponent(codigo) + suffix;
  }

  window.irSeguimiento = irSeguimiento;

  document.querySelectorAll(".row-clickable").forEach(function (row) {
    row.addEventListener("dblclick", function () {
      const codigo = this.getAttribute("data-codigo") || (this.children[0] ? this.children[0].textContent.trim() : "");
      irSeguimiento(codigo);
    });
  });

  // Re-init in case rows are refreshed dynamically.
  setTimeout(initPredictionPopovers, 0);
});
