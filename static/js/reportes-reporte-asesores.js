function exportarExcel() {
  const table = document.getElementById("tablaAsesores");
  if (!table) return;

  let csv = "";
  const rows = table.querySelectorAll("tr");
  rows.forEach(function (row) {
    const cells = row.querySelectorAll("th, td");
    const values = Array.from(cells).map(function (cell) {
      const text = cell.textContent.trim().replace(/\s+/g, " ");
      return '"' + text.replace(/"/g, '""') + '"';
    });
    csv += values.join(",") + "\n";
  });

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "reporte_asesores_" + new Date().toISOString().split("T")[0] + ".csv";
  link.click();
}

window.exportarExcel = exportarExcel;
