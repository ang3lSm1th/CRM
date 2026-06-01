document.addEventListener('DOMContentLoaded', function() {
    const rucDniInput = document.getElementById('ruc_dni');
    const telefonoInput = document.getElementById('telefono');

    // --- Limita RUC/DNI a solo números y máximo 11 caracteres ---
    if (rucDniInput) {
        rucDniInput.addEventListener('input', function(e) {
            this.value = this.value.replace(/\D/g, '').slice(0, 11);
        });
        
        rucDniInput.addEventListener('keypress', function(e) {
            // Permite solo números
            const char = String.fromCharCode(e.which);
            if (!/[0-9]/.test(char)) {
                e.preventDefault();
                return false;
            }
            // Previene si ya tiene 11 caracteres
            if (this.value.length >= 11) {
                e.preventDefault();
                return false;
            }
        });
    }

    // --- Limita Teléfono a solo números y máximo 9 caracteres ---
    if (telefonoInput) {
        telefonoInput.addEventListener('input', function(e) {
            this.value = this.value.replace(/\D/g, '').slice(0, 9);
        });
        
        telefonoInput.addEventListener('keypress', function(e) {
            // Permite solo números
            const char = String.fromCharCode(e.which);
            if (!/[0-9]/.test(char)) {
                e.preventDefault();
                return false;
            }
            // Previene si ya tiene 9 caracteres
            if (this.value.length >= 9) {
                e.preventDefault();
                return false;
            }
        });
    }

    console.log('✓ Validación de campos RUC/DNI y Teléfono cargada correctamente');

    // --- Autofill desde DB cuando se ingresa DNI/RUC ---
    if (rucDniInput) {
        // debounce helper
        const debounce = (fn, delay) => {
            let timer = null;
            return function(...args) {
                clearTimeout(timer);
                timer = setTimeout(() => fn.apply(this, args), delay);
            };
        };

        const runClienteLookup = (val) => {
            if (!val) return;
            const btn = document.getElementById('btnValidateClient');
            if (btn) { btn.disabled = true; btn.innerText = 'Validando...'; }
            const url = (window.CLIENTE_API || '/leads/api/cliente') + '/' + encodeURIComponent(val);
            console.debug('Cliente lookup URL:', url);

            fetch(url, { credentials: 'same-origin' })
                .then(res => {
                    console.debug('api_get_cliente status:', res.status, 'content-type:', res.headers.get('content-type'));
                    if (res.status === 200) {
                        const ct = (res.headers.get('content-type') || '').toLowerCase();
                        if (ct.indexOf('application/json') !== -1) {
                            return res.json();
                        }
                        // If response is not JSON (e.g. redirected to login html), log text for debugging
                        return res.text().then(t => { throw new Error('Non-JSON response: ' + t.slice(0, 500)); });
                    }
                    // 401 / 302 (redirect to login) / 404 -> return null but log
                    return res.text().then(t => { console.warn('api_get_cliente returned', res.status, t.slice(0,200)); return null; });
                })
                .then(cliente => {
                    if (!cliente) return;
                    // Autocompletar desde cliente
                    const setIf = (id, v) => { const el = document.getElementById(id); if (el && (v !== undefined && v !== null)) el.value = v; };
                    setIf('nombre', cliente.nombre || '');
                    setIf('telefono', cliente.telefono || '');
                    setIf('contacto', cliente.contacto || '');
                    setIf('email', cliente.email || '');
                    setIf('direccion', cliente.direccion || '');
                    try {
                        if (cliente.departamento) {
                            const dep = document.getElementById('departamento');
                            if (dep) { dep.value = String(cliente.departamento); dep.dispatchEvent(new Event('change')); }
                        }
                        if (cliente.provincia) {
                            const prov = document.getElementById('provincia');
                            setTimeout(() => { if (prov) { prov.value = String(cliente.provincia); prov.dispatchEvent(new Event('change')); } }, 300);
                        }
                        if (cliente.distrito) {
                            setTimeout(() => { const dis = document.getElementById('distrito'); if (dis) dis.value = String(cliente.distrito); }, 600);
                        }
                    } catch (err) { console.warn('Error seteando ubigeo desde cliente', err); }

                    console.info('Autofill aplicado desde cliente:', cliente.ruc_dni || val);
                })
                .catch(err => {
                    console.error('Error buscando cliente:', err);
                    // Mostrar un pequeño mensaje visual junto al campo para ayudar a debug
                    try {
                        let msg = document.getElementById('clienteLookupMsg');
                        if (!msg) {
                            msg = document.createElement('div');
                            msg.id = 'clienteLookupMsg';
                            msg.style.color = '#b00';
                            msg.style.fontSize = '0.9em';
                            msg.style.marginTop = '6px';
                            const parent = document.getElementById('ruc_dni').parentNode;
                            parent.appendChild(msg);
                        }
                        msg.innerText = 'Error al cargar cliente (ver consola Network).';
                        setTimeout(() => { if (msg) msg.remove(); }, 4000);
                    } catch (e) {}
                })
                .finally(() => { if (btn) { btn.disabled = false; btn.innerText = 'Validar'; } });
        };

        // Debounced lookup while typing (user asked "al momento de llenar")
        rucDniInput.addEventListener('input', debounce(function() {
            const val = (this.value || '').trim();
            if (val.length >= 6) runClienteLookup(val); // start searching after a few chars
        }, 700));

        // Also trigger on blur and paste (fallbacks)
        rucDniInput.addEventListener('blur', function() { runClienteLookup((this.value || '').trim()); });
        rucDniInput.addEventListener('paste', function() { setTimeout(() => runClienteLookup((this.value || '').trim()), 200); });
    }
});