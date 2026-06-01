document.addEventListener("DOMContentLoaded", function () {
  const negocio = document.getElementById("linea-negocio");
  const familia = document.getElementById("linea-familia");
  const producto = document.getElementById("linea-producto");
  const cfg = document.getElementById("marketing-campanas-config");

  if (!negocio || !familia || !producto || !cfg) return;

  const familiaApi = cfg.dataset.familiaApi;
  const productoApi = cfg.dataset.productoApi;

  function resetSelect(selectEl, placeholder) {
    selectEl.innerHTML = "";
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = placeholder;
    selectEl.appendChild(opt);
  }

  function fillSelect(selectEl, items) {
    items.forEach(function (item) {
      const opt = document.createElement("option");
      opt.value = String(item.id);
      opt.textContent = item.nombre;
      selectEl.appendChild(opt);
    });
  }

  function showWarn(message) {
    if (typeof Swal !== "undefined") {
      Swal.fire({ icon: "warning", title: message, confirmButtonText: "Aceptar" });
      return;
    }
    alert(message);
  }

  async function cargarFamilias(lineaNegocioId) {
    resetSelect(familia, "Cargando...");
    familia.disabled = true;
    resetSelect(producto, "Seleccionar primero linea de familia");
    producto.disabled = true;

    if (!lineaNegocioId) {
      resetSelect(familia, "Seleccionar primero linea de negocio");
      return;
    }

    const resp = await fetch(familiaApi + "?linea_negocio_id=" + encodeURIComponent(lineaNegocioId));
    const data = await resp.json();
    resetSelect(familia, "Seleccionar familia");

    if (!data.ok) {
      showWarn(data.message || "No se pudo cargar lineas de familia.");
      return;
    }

    fillSelect(familia, data.items || []);
    familia.disabled = false;
  }

  async function cargarProductos(lineaNegocioId) {
    resetSelect(producto, "Cargando...");
    producto.disabled = true;

    if (!lineaNegocioId) {
      resetSelect(producto, "Seleccionar primero linea de familia");
      return;
    }

    const resp = await fetch(productoApi + "?linea_negocio_id=" + encodeURIComponent(lineaNegocioId));
    const data = await resp.json();
    resetSelect(producto, "Seleccionar linea de producto");

    if (!data.ok) {
      showWarn(data.message || "No se pudo cargar lineas de producto.");
      return;
    }

    fillSelect(producto, data.items || []);
    producto.disabled = false;
  }

  negocio.addEventListener("change", function () {
    cargarFamilias(negocio.value).catch(function () {
      resetSelect(familia, "No se pudo cargar");
      familia.disabled = true;
    });
  });

  familia.addEventListener("change", function () {
    cargarProductos(negocio.value).catch(function () {
      resetSelect(producto, "No se pudo cargar");
      producto.disabled = true;
    });
  });
});
