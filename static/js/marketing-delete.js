(function () {
  'use strict';

  function createToastContainer() {
    let container = document.getElementById('mk-mini-toast-container');
    if (container) return container;
    container = document.createElement('div');
    container.id = 'mk-mini-toast-container';
    container.style.position = 'fixed';
    container.style.top = '1rem';
    container.style.right = '1rem';
    container.style.zIndex = '1200';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '0.5rem';
    document.body.appendChild(container);
    return container;
  }

  function showToast(message, level) {
    const container = createToastContainer();
    const toast = document.createElement('div');
    toast.textContent = message;
    toast.style.padding = '0.6rem 0.9rem';
    toast.style.borderRadius = '6px';
    toast.style.color = '#fff';
    toast.style.boxShadow = '0 8px 20px rgba(0,0,0,0.18)';
    toast.style.minWidth = '220px';
    toast.style.fontSize = '0.95rem';
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(-6px)';
    toast.style.transition = 'opacity 0.18s ease, transform 0.18s ease';

    const palette = {
      success: { bg: '#198754' },
      danger: { bg: '#dc3545' },
      warning: { bg: '#fd7e14' },
      info: { bg: '#0d6efd' },
    };
    const p = palette[level] || palette.info;
    toast.style.background = p.bg;

    container.appendChild(toast);
    requestAnimationFrame(() => {
      toast.style.opacity = '1';
      toast.style.transform = 'translateY(0)';
    });

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(-6px)';
      setTimeout(() => toast.remove(), 220);
    }, 2800);
  }

  function createModal() {
    if (document.getElementById('mk-delete-modal')) return document.getElementById('mk-delete-modal');

    const html = `
      <div id="mk-delete-modal" style="display:none; position:fixed; inset:0; z-index:1100; align-items:center; justify-content:center;">
        <div id="mk-delete-backdrop" style="position:fixed; inset:0; background:rgba(0,0,0,0.45);"></div>
        <div id="mk-delete-dialog" style="background:#fff; padding:1.25rem; border-radius:8px; width:420px; max-width:95%; z-index:1101; box-shadow: 0 10px 30px rgba(0,0,0,0.25);">
          <h5 id="mk-delete-title" style="margin:0 0 0.5rem 0;">Confirmar eliminación</h5>
          <div id="mk-delete-desc" style="margin-bottom:0.75rem;color:#374151;font-size:0.95rem;">Esta acción es irreversible. Para confirmar, escribe el nombre exacto y tu contraseña.</div>

          <div style="margin-bottom:0.5rem;font-size:0.9rem;"><strong>Nombre esperado:</strong> <span id="mk-delete-expected-name" style="font-weight:600;color:#111827"></span></div>
          <div style="margin-bottom:0.75rem;"><input id="mk-delete-name-input" class="form-control" placeholder="Escribe el nombre exacto para confirmar"></div>
          <div style="margin-bottom:0.75rem;"><input id="mk-delete-password-input" type="password" class="form-control" placeholder="Tu contraseña"></div>

          <div id="mk-delete-force-row" style="display:none;margin-bottom:0.75rem;">
            <div class="form-check">
              <input class="form-check-input" type="checkbox" value="" id="mk-delete-force-checkbox">
              <label class="form-check-label" for="mk-delete-force-checkbox">Forzar eliminación (eliminar vínculos o desvincular leads)</label>
            </div>
          </div>

          <div id="mk-delete-error" style="display:none;color:#b91c1c;margin-bottom:0.75rem;font-size:0.9rem;"></div>

          <div style="display:flex;justify-content:flex-end;gap:0.5rem;">
            <button id="mk-delete-cancel" class="btn btn-secondary btn-sm">Cancelar</button>
            <button id="mk-delete-confirm" class="btn btn-danger btn-sm">Eliminar</button>
          </div>
        </div>
      </div>
    `;

    const wrapper = document.createElement('div');
    wrapper.innerHTML = html;
    document.body.appendChild(wrapper.firstElementChild);

    const modal = document.getElementById('mk-delete-modal');
    modal.querySelector('#mk-delete-cancel').addEventListener('click', hideModal);
    modal.querySelector('#mk-delete-backdrop').addEventListener('click', hideModal);

    return modal;
  }

  function showModal() {
    const modal = createModal();
    modal.style.display = 'flex';
    // small animation
    requestAnimationFrame(() => {
      const dlg = modal.querySelector('#mk-delete-dialog');
      dlg.style.transform = 'translateY(-6px)';
      dlg.style.opacity = '0';
      dlg.style.transition = 'opacity 0.18s ease, transform 0.18s ease';
      requestAnimationFrame(() => {
        dlg.style.transform = 'translateY(0)';
        dlg.style.opacity = '1';
      });
    });
  }

  function hideModal() {
    const modal = document.getElementById('mk-delete-modal');
    if (!modal) return;
    const dlg = modal.querySelector('#mk-delete-dialog');
    dlg.style.opacity = '0';
    dlg.style.transform = 'translateY(-6px)';
    setTimeout(() => {
      modal.style.display = 'none';
      // cleanup fields
      const err = modal.querySelector('#mk-delete-error'); if (err) { err.style.display='none'; err.textContent=''; }
      const nameInput = modal.querySelector('#mk-delete-name-input'); if (nameInput) nameInput.value = '';
      const passInput = modal.querySelector('#mk-delete-password-input'); if (passInput) passInput.value = '';
      const forceRow = modal.querySelector('#mk-delete-force-row'); if (forceRow) forceRow.style.display = 'none';
      modal.__context = null;
    }, 190);
  }

  async function doInit(initUrl, contextEl) {
    try {
      const resp = await fetch(initUrl, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        },
        credentials: 'same-origin'
      });
      const payload = await resp.json().catch(() => ({}));
      if (!resp.ok || !payload.ok) {
        showToast(payload.message || 'No se pudo iniciar eliminación', 'danger');
        return null;
      }
      return payload;
    } catch (err) {
      showToast('Error de red al iniciar eliminación', 'danger');
      return null;
    }
  }

  async function doConfirm(confirmUrl, body) {
    try {
      const resp = await fetch(confirmUrl, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        },
        credentials: 'same-origin',
        body: JSON.stringify(body)
      });
      const payload = await resp.json().catch(() => ({}));
      return { resp, payload };
    } catch (err) {
      return { error: err };
    }
  }

  function bindDeleteButtons(selector, type) {
    const buttons = Array.from(document.querySelectorAll(selector));
    buttons.forEach(btn => {
      btn.addEventListener('click', async function (e) {
        e.preventDefault();
        const initUrl = btn.dataset.initUrl;
        const confirmUrl = btn.dataset.confirmUrl;
        const expectedName = btn.dataset.deleteName || '';
        const id = btn.dataset.deleteId || '';
        const row = btn.closest('tr');

        if (!initUrl || !confirmUrl) {
          showToast('URL de eliminación no disponible', 'danger');
          return;
        }

        const payload = await doInit(initUrl, btn);
        if (!payload) return;

        const modal = createModal();
        modal.__context = { confirmUrl, token: payload.token, expectedName, id, row };
        modal.querySelector('#mk-delete-expected-name').textContent = payload.confirm_name || expectedName || '';
        modal.querySelector('#mk-delete-name-input').value = '';
        modal.querySelector('#mk-delete-password-input').value = '';
        const forceRow = modal.querySelector('#mk-delete-force-row');
        if (payload.linked_leads && Number(payload.linked_leads) > 0) {
          forceRow.style.display = 'block';
          forceRow.querySelector('label').textContent = `Forzar eliminación (existen ${payload.linked_leads} leads vinculados)`;
        } else {
          forceRow.style.display = 'none';
        }
        modal.querySelector('#mk-delete-error').style.display = 'none';

        showModal();

        const confirmBtn = modal.querySelector('#mk-delete-confirm');
        const cancelBtn = modal.querySelector('#mk-delete-cancel');

        async function onConfirm() {
          confirmBtn.disabled = true;
          confirmBtn.textContent = 'Procesando...';
          const typed = modal.querySelector('#mk-delete-name-input').value.trim();
          const password = modal.querySelector('#mk-delete-password-input').value || '';
          const force = !!modal.querySelector('#mk-delete-force-checkbox').checked;

          if (!typed) {
            const errEl = modal.querySelector('#mk-delete-error');
            errEl.style.display = 'block';
            errEl.textContent = 'Escribe el nombre exacto para confirmar.';
            confirmBtn.disabled = false;
            confirmBtn.textContent = 'Eliminar';
            return;
          }

          const ctx = modal.__context || {};
          const body = { token: ctx.token, confirm_name: typed, password: password, force: force };
          const { resp, payload } = await doConfirm(ctx.confirmUrl, body);

          if (payload && payload.ok) {
            hideModal();
            showToast(payload.message || 'Eliminado correctamente', 'success');
            // remove row if available
            if (ctx.row && ctx.row.parentNode) {
              ctx.row.remove();
            } else {
              // fallback: reload
              try { window.location.reload(); } catch (e) { }
            }
          } else {
            const errEl = modal.querySelector('#mk-delete-error');
            errEl.style.display = 'block';
            if (payload && payload.message) {
              errEl.textContent = payload.message;
            } else if (payload && payload.requires_force) {
              errEl.textContent = payload.message || 'Existen vínculos. Marca "Forzar" para proceder.';
            } else {
              errEl.textContent = 'Error al eliminar. Intenta nuevamente.';
            }
            // if server insists on force, show the force checkbox
            if (payload && payload.requires_force && modal.querySelector('#mk-delete-force-row')) {
              modal.querySelector('#mk-delete-force-row').style.display = 'block';
            }
          }

          confirmBtn.disabled = false;
          confirmBtn.textContent = 'Eliminar';
        }

        confirmBtn.removeEventListener('click', onConfirm);
        confirmBtn.addEventListener('click', onConfirm, { once: false });
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    bindDeleteButtons('.js-delete-campaign', 'campaign');
    bindDeleteButtons('.js-delete-feria', 'feria');
  });
})();
