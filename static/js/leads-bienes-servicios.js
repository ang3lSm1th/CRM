document.addEventListener("DOMContentLoaded", function () {
  const flashesNode = document.getElementById("flashed-messages-json");
  let flashedMessages = [];

  try {
    flashedMessages = JSON.parse(flashesNode?.dataset.messages || "[]");
  } catch (_) {
    flashedMessages = [];
  }

  const formAgregar = document.getElementById("form-agregar");
  if (formAgregar) {
    formAgregar.addEventListener("submit", function (e) {
      e.preventDefault();
      Swal.fire({
        title: "Deseas agregar este bien o servicio?",
        icon: "question",
        showCancelButton: true,
        confirmButtonText: "Si, agregar",
        cancelButtonText: "Cancelar",
        confirmButtonColor: "#0d6efd",
        cancelButtonColor: "#6c757d"
      }).then((result) => {
        if (result.isConfirmed) this.submit();
      });
    });
  }

  document.querySelectorAll(".form-eliminar").forEach((form) => {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      Swal.fire({
        title: "Seguro que deseas eliminar este registro?",
        icon: "warning",
        showCancelButton: true,
        confirmButtonText: "Si, eliminar",
        cancelButtonText: "Cancelar",
        confirmButtonColor: "#dc3545",
        cancelButtonColor: "#6c757d"
      }).then((result) => {
        if (result.isConfirmed) this.submit();
      });
    });
  });

  document.querySelectorAll(".form-editar").forEach((form) => {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      Swal.fire({
        title: "Deseas guardar los cambios?",
        icon: "question",
        showCancelButton: true,
        confirmButtonText: "Si, guardar",
        cancelButtonText: "Cancelar",
        confirmButtonColor: "#198754",
        cancelButtonColor: "#6c757d"
      }).then((result) => {
        if (result.isConfirmed) this.submit();
      });
    });
  });

  if (!Array.isArray(flashedMessages) || !flashedMessages.length) return;
  flashedMessages.forEach(function (item) {
    const category = item[0];
    const message = item[1];
    if (!message) return;

    let icon = "info";
    if (category === "success") icon = "success";
    else if (category === "danger" || category === "error") icon = "error";

    Swal.fire({
      icon: icon,
      title: message,
      confirmButtonText: "Aceptar",
      allowOutsideClick: false,
      allowEscapeKey: true
    });
  });
});
