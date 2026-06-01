document.addEventListener("DOMContentLoaded", function () {
  const root = document.getElementById("wa-api-config-endpoints");
  if (!root) return;

  const testUrl = root.dataset.testUrl;
  const templateTestUrl = root.dataset.templateTestUrl;

  const testBtn = document.getElementById("wa-test-send");
  const testTo = document.getElementById("wa-test-to");
  const testText = document.getElementById("wa-test-text");
  const testOut = document.getElementById("wa-test-output");

  const tplBtn = document.getElementById("wa-tpl-send");
  const tplTo = document.getElementById("wa-tpl-to");
  const tplName = document.getElementById("wa-tpl-name");
  const tplLang = document.getElementById("wa-tpl-lang");
  const tplOut = document.getElementById("wa-tpl-output");

  function popupError(message) {
    if (typeof Swal !== "undefined") {
      Swal.fire({ icon: "error", title: "Error", text: message });
      return;
    }
    alert(message);
  }

  if (testBtn) {
    testBtn.addEventListener("click", async function () {
      const to = (testTo?.value || "").trim();
      const text = (testText?.value || "").trim();
      testOut.textContent = "Enviando...";
      try {
        const res = await fetch(testUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ to: to, text: text })
        });
        const data = await res.json().catch(function () { return {}; });
        testOut.textContent = JSON.stringify(data, null, 2);
        if (!res.ok || !data.ok) {
          popupError((data && data.error) ? data.error : "Fallo en el envio de prueba.");
        }
      } catch (err) {
        testOut.textContent = String(err);
        popupError("Error de red realizando la prueba.");
      }
    });
  }

  if (tplBtn) {
    tplBtn.addEventListener("click", async function () {
      tplOut.textContent = "Enviando plantilla...";
      try {
        const res = await fetch(templateTestUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            to: (tplTo?.value || "").trim(),
            template_name: (tplName?.value || "").trim(),
            language_code: (tplLang?.value || "").trim()
          })
        });
        const data = await res.json().catch(function () { return {}; });
        tplOut.textContent = JSON.stringify(data, null, 2);
        if (!res.ok || !data.ok) {
          popupError((data && data.error) ? data.error : "Fallo en el envio de plantilla.");
        }
      } catch (err) {
        tplOut.textContent = String(err);
        popupError("Error de red enviando la plantilla.");
      }
    });
  }
});
