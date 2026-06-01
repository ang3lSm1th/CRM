document.addEventListener("DOMContentLoaded", function () {
  function ensureToastContainer() {
    let container = document.getElementById("mini-toast-container");
    if (container) return container;

    container = document.createElement("div");
    container.id = "mini-toast-container";
    container.style.position = "fixed";
    container.style.top = "1rem";
    container.style.right = "1rem";
    container.style.zIndex = "1080";
    container.style.display = "flex";
    container.style.flexDirection = "column";
    container.style.gap = "0.5rem";
    document.body.appendChild(container);
    return container;
  }

  function showMiniToast(message, level) {
    const container = ensureToastContainer();
    const toast = document.createElement("div");
    const colors = {
      success: { bg: "#198754", border: "#146c43" },
      warning: { bg: "#fd7e14", border: "#ca6510" },
      danger: { bg: "#dc3545", border: "#b02a37" },
      info: { bg: "#0d6efd", border: "#0a58ca" }
    };
    const palette = colors[level] || colors.info;

    toast.style.background = palette.bg;
    toast.style.border = `1px solid ${palette.border}`;
    toast.style.color = "#fff";
    toast.style.padding = "0.65rem 0.8rem";
    toast.style.borderRadius = "0.5rem";
    toast.style.minWidth = "260px";
    toast.style.boxShadow = "0 10px 24px rgba(0,0,0,0.18)";
    toast.style.fontSize = "0.9rem";
    toast.style.opacity = "0";
    toast.style.transform = "translateY(-6px)";
    toast.style.transition = "opacity 0.2s ease, transform 0.2s ease";
    toast.textContent = message || "Operacion completada";

    container.appendChild(toast);
    requestAnimationFrame(function () {
      toast.style.opacity = "1";
      toast.style.transform = "translateY(0)";
    });

    window.setTimeout(function () {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(-6px)";
      window.setTimeout(function () {
        toast.remove();
      }, 220);
    }, 2400);
  }

  function showConfirmationToast(message, onAccept, onCancel) {
    // Remover cualquier overlay existente
    const existingOverlay = document.getElementById("confirmation-toast-overlay");
    if (existingOverlay && existingOverlay.parentNode) {
      existingOverlay.remove();
    }

    const container = document.createElement("div");
    container.id = "confirmation-toast-overlay";
    container.style.position = "fixed";
    container.style.top = "0";
    container.style.left = "0";
    container.style.width = "100%";
    container.style.height = "100%";
    container.style.background = "rgba(0, 0, 0, 0.4)";
    container.style.display = "flex";
    container.style.alignItems = "center";
    container.style.justifyContent = "center";
    container.style.zIndex = "1090";
    container.style.opacity = "1";
    container.style.transition = "opacity 0.2s ease";

    const toast = document.createElement("div");
    toast.style.background = "#fff";
    toast.style.border = "1px solid #ddd";
    toast.style.borderRadius = "0.5rem";
    toast.style.padding = "1.5rem";
    toast.style.boxShadow = "0 10px 40px rgba(0,0,0,0.2)";
    toast.style.minWidth = "320px";
    toast.style.minHeight = "120px";
    toast.style.display = "flex";
    toast.style.flexDirection = "column";
    toast.style.gap = "1rem";
    toast.style.animation = "slideUp 0.3s ease forwards";

    const messageEl = document.createElement("div");
    messageEl.style.fontSize = "1rem";
    messageEl.style.color = "#333";
    messageEl.style.fontWeight = "500";
    messageEl.textContent = message;

    const buttonsDiv = document.createElement("div");
    buttonsDiv.style.display = "flex";
    buttonsDiv.style.gap = "0.5rem";
    buttonsDiv.style.justifyContent = "flex-end";

    const btnAceptar = document.createElement("button");
    btnAceptar.textContent = "Aceptar";
    btnAceptar.style.padding = "0.5rem 1.2rem";
    btnAceptar.style.background = "#198754";
    btnAceptar.style.color = "#fff";
    btnAceptar.style.border = "none";
    btnAceptar.style.borderRadius = "0.3rem";
    btnAceptar.style.cursor = "pointer";
    btnAceptar.style.fontSize = "0.9rem";
    btnAceptar.style.fontWeight = "500";
    btnAceptar.addEventListener("click", function () {
      container.style.opacity = "0";
      container.style.transition = "opacity 0.2s ease";
      setTimeout(function () {
        if (container && container.parentNode) {
          container.remove();
        }
      }, 200);
      if (onAccept) onAccept();
    });
    btnAceptar.addEventListener("mouseover", function () {
      btnAceptar.style.background = "#157347";
    });
    btnAceptar.addEventListener("mouseout", function () {
      btnAceptar.style.background = "#198754";
    });

    const btnCancelar = document.createElement("button");
    btnCancelar.textContent = "Cancelar";
    btnCancelar.style.padding = "0.5rem 1.2rem";
    btnCancelar.style.background = "#6c757d";
    btnCancelar.style.color = "#fff";
    btnCancelar.style.border = "none";
    btnCancelar.style.borderRadius = "0.3rem";
    btnCancelar.style.cursor = "pointer";
    btnCancelar.style.fontSize = "0.9rem";
    btnCancelar.style.fontWeight = "500";
    btnCancelar.addEventListener("click", function () {
      container.style.opacity = "0";
      container.style.transition = "opacity 0.2s ease";
      setTimeout(function () {
        if (container && container.parentNode) {
          container.remove();
        }
      }, 200);
      if (onCancel) onCancel();
    });
    btnCancelar.addEventListener("mouseover", function () {
      btnCancelar.style.background = "#5a6268";
    });
    btnCancelar.addEventListener("mouseout", function () {
      btnCancelar.style.background = "#6c757d";
    });

    buttonsDiv.appendChild(btnCancelar);
    buttonsDiv.appendChild(btnAceptar);

    toast.appendChild(messageEl);
    toast.appendChild(buttonsDiv);
    container.appendChild(toast);
    document.body.appendChild(container);

    const style = document.createElement("style");
    style.textContent = "@keyframes slideUp { from { transform: translateY(20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }";
    document.head.appendChild(style);
  }

  function bindToggleAll() {
    const toggleAll = document.getElementById("toggle-all");
    if (toggleAll) {
      toggleAll.addEventListener("change", function () {
        document.querySelectorAll(".lead-check").forEach(function (cb) {
          cb.checked = toggleAll.checked;
        });
      });
    }

    const toggleAllLinked = document.getElementById("toggle-all-linked");
    if (toggleAllLinked) {
      toggleAllLinked.addEventListener("change", function () {
        document.querySelectorAll(".unlink-check").forEach(function (cb) {
          cb.checked = toggleAllLinked.checked;
        });
      });
    }
  }

  async function refreshCampaignCards() {
    const response = await fetch(window.location.href, {
      headers: { "X-Requested-With": "XMLHttpRequest" }
    });
    const html = await response.text();
    const doc = new DOMParser().parseFromString(html, "text/html");

    const newCandidates = doc.getElementById("campaign-candidates-card");
    const newLinked = doc.getElementById("campaign-linked-card");
    const currentCandidates = document.getElementById("campaign-candidates-card");
    const currentLinked = document.getElementById("campaign-linked-card");

    if (newCandidates && currentCandidates) currentCandidates.replaceWith(newCandidates);
    if (newLinked && currentLinked) currentLinked.replaceWith(newLinked);
  }

  function bindCampaignForms() {
    const forms = document.querySelectorAll(".js-campaign-action-form");

    document.addEventListener("click", function (event) {
      if (event.target.classList.contains("js-unlink-single")) {
        event.preventDefault();
        const form = event.target.closest("form.js-campaign-action-form");
        showConfirmationToast("¿Desvincular este lead?", function () {
          if (form) form.dispatchEvent(new Event("submit"));
        });
        return false;
      }
      if (event.target.classList.contains("js-unlink-mass")) {
        event.preventDefault();
        const form = document.getElementById("mass-unlink-form");
        showConfirmationToast("¿Desvincular los leads seleccionados?", function () {
          if (form) form.dispatchEvent(new Event("submit"));
        });
        return false;
      }
      if (event.target.classList.contains("js-auto-vincular-btn")) {
        event.preventDefault();
        const form = event.target.closest("form.js-campaign-action-form");
        showConfirmationToast("¿Auto-vincular leads del periodo con este bien/servicio?", function () {
          if (form) form.dispatchEvent(new Event("submit"));
        });
        return false;
      }
    });

    forms.forEach(function (form) {
      form.addEventListener("submit", async function (event) {
        event.preventDefault();

        const submitBtn = form.querySelector('button[type="submit"]');
        const previousHtml = submitBtn ? submitBtn.innerHTML : "";
        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Procesando...';
        }

        try {
          const body = new URLSearchParams(new FormData(form));
          const postResponse = await fetch(window.location.href, {
            method: "POST",
            headers: {
              "X-Requested-With": "XMLHttpRequest",
              "Accept": "application/json",
              "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"
            },
            body
          });

          const payload = await postResponse.json();
          if (!postResponse.ok || !payload.ok) {
            throw new Error(payload.message || "No se pudo completar la operacion.");
          }

          await refreshCampaignCards();
          bindToggleAll();
          bindCampaignForms();
          showMiniToast(payload.message || "Operacion completada", payload.level || "success");
        } catch (error) {
          showMiniToast(error.message || "Ocurrio un error inesperado.", "danger");
        } finally {
          if (submitBtn && submitBtn.isConnected) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = previousHtml;
          }
        }
      });
    });
  }

  bindToggleAll();
  bindCampaignForms();
});
