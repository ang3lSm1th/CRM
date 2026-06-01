(function () {
  function filtrarTabla(tablaId, query) {
    const tabla = document.getElementById(tablaId);
    if (!tabla || !tabla.tBodies[0]) return;

    const filas = tabla.tBodies[0].rows;
    const filtro = String(query || "").toLowerCase();

    Array.from(filas).forEach(function (fila) {
      const texto = fila.textContent.toLowerCase();
      fila.style.display = texto.includes(filtro) ? "" : "none";
    });
  }

  function exportarDatos() {
    const tabActiva = document.querySelector(".tab-pane.active");
    const tabla = tabActiva ? tabActiva.querySelector("table") : null;

    if (!tabla) {
      if (typeof Swal !== "undefined") {
        Swal.fire({ icon: "info", title: "No hay datos para exportar" });
      } else {
        alert("No hay datos para exportar");
      }
      return;
    }

    let csv = "";
    tabla.querySelectorAll("tr").forEach(function (fila) {
      const celdas = fila.querySelectorAll("th, td");
      const valores = Array.from(celdas).map(function (celda) {
        const texto = celda.textContent.trim().replace(/\s+/g, " ");
        return '"' + texto.replace(/"/g, '""') + '"';
      });
      csv += valores.join(",") + "\n";
    });

    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "analisis_clientes_" + new Date().toISOString().split("T")[0] + ".csv";
    link.click();
  }

  document.addEventListener("DOMContentLoaded", function () {
    const searchLineas = document.getElementById("searchLineas");
    const searchFrecuencia = document.getElementById("searchFrecuencia");

    if (searchLineas) {
      searchLineas.addEventListener("keyup", function () {
        filtrarTabla("tablaLineas", this.value);
      });
    }

    if (searchFrecuencia) {
      searchFrecuencia.addEventListener("keyup", function () {
        filtrarTabla("tablaFrecuencia", this.value);
      });
    }
  });

  window.exportarDatos = exportarDatos;
})();
