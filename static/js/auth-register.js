document.addEventListener("DOMContentLoaded", function () {
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get("success") === "1" && window.toast && typeof window.toast.success === "function") {
    window.toast.success("Usuario registrado exitosamente.");
  }

  // Toggle requirement of negocio selection depending on role chosen
  const rolSelect = document.querySelector('select[name="rol"]');
  const negocioSelect = document.querySelector('select[name="negocio_id"]');

  function updateNegocioRequired() {
    if (!rolSelect || !negocioSelect) return;
    const roleText = (rolSelect.options[rolSelect.selectedIndex] || {}).text || '';
    if (roleText.trim().toLowerCase() !== 'administrador') {
      negocioSelect.setAttribute('required', 'required');
    } else {
      negocioSelect.removeAttribute('required');
    }
  }

  if (rolSelect) {
    rolSelect.addEventListener('change', updateNegocioRequired);
    updateNegocioRequired();
  }
});
