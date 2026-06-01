document.addEventListener("DOMContentLoaded", () => {
    const resetPwModalElement = document.getElementById("resetPwModal");
    const editNameModalElement = document.getElementById("editNameModal");
    const viewUserModalElement = document.getElementById("viewUserModal");
    const deleteUserModalElement = document.getElementById("deleteUserModal");
    
    // Only initialize modals if their corresponding elements exist on the page
    const resetPwModal = resetPwModalElement ? new bootstrap.Modal(resetPwModalElement) : null;
    const editNameModal = editNameModalElement ? new bootstrap.Modal(editNameModalElement) : null;
    const viewUserModal = viewUserModalElement ? new bootstrap.Modal(viewUserModalElement) : null;
    const deleteUserModal = deleteUserModalElement ? new bootstrap.Modal(deleteUserModalElement) : null;

    // Ensure modals/backdrops are fully removed (fix leftover black overlay)
    function ensureModalClosed() {
        try { if (deleteUserModal) deleteUserModal.hide(); } catch (e) { /* ignore */ }
        // Remove any leftover bootstrap modal backdrops
        document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
        // Restore body state
        document.body.classList.remove('modal-open');
        document.body.style.overflow = '';
        document.body.style.paddingRight = '';
    }

    // Fill the reset password modal fields
    document.querySelectorAll(".btn-open-reset").forEach(btn => {
        btn.addEventListener("click", () => {
            document.getElementById("modal_user_id").value = btn.dataset.userId;
            document.getElementById("modal_username").value = btn.dataset.username;
            document.getElementById("modal_nombre").value = btn.dataset.nombre;
            document.getElementById("modal_new_password").value = "";
        });
    });

    // Fill the edit name modal fields
    document.querySelectorAll(".btn-open-edit-name").forEach(btn => {
        btn.addEventListener("click", () => {
            document.getElementById("edit_name_user_id").value = btn.dataset.userId;
            document.getElementById("edit_name_username").value = btn.dataset.username;
            document.getElementById("edit_name_current").value = btn.dataset.nombre;
            document.getElementById("edit_name_new").value = btn.dataset.nombre;
        });
    });

    // Fill the view user modal fields
    document.querySelectorAll(".btn-view-user").forEach(btn => {
        btn.addEventListener("click", () => {
            document.getElementById("view_nombre").textContent = btn.dataset.nombre;
            document.getElementById("view_usuario").textContent = btn.dataset.username;
            document.getElementById("view_rol").textContent = btn.dataset.rol;
            // Empresa (negocio)
            const viewEmpresaEl = document.getElementById("view_empresa");
            if (viewEmpresaEl) viewEmpresaEl.textContent = btn.dataset.negocioName || '-';
        });
    });

    // Fill the delete user modal fields (store both id and username)
    document.querySelectorAll(".btn-open-delete").forEach(btn => {
        btn.addEventListener("click", () => {
            const userId = btn.dataset.userId;
            const username = btn.dataset.username;
            const nombre = btn.dataset.nombre;
            document.getElementById("delete_user_id").value = userId;
            const usernameInput = document.getElementById("delete_user_username");
            if (usernameInput) usernameInput.value = username;
            document.getElementById("delete_nombre").textContent = nombre;
            document.getElementById("delete_usuario").textContent = username;
        });
    });

    // Handle the reset password form submission
    const resetPwForm = document.getElementById("resetPwForm");
    if (resetPwForm) {
        resetPwForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const userId = document.getElementById("modal_user_id").value;
            const newPassword = document.getElementById("modal_new_password").value;
            if (newPassword.length < 6) {
                alert("La contraseña debe tener al menos 6 caracteres.");
                return;
            }
            try {
                const res = await fetch("/usuarios/reset_password", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ user_id: userId, new_password: newPassword })
                });
                const data = await res.json();
                if (data.success) {
                    alert("Contraseña restablecida correctamente.");
                    if (resetPwModal) resetPwModal.hide();
                    
                    // 🔑 LÍNEA AÑADIDA PARA RECARGAR LA PÁGINA 🔑
                    window.location.reload(); 
                    
                } else {
                    alert("Error: " + (data.error || "Ocurrió un error inesperado."));
                }
            } catch (err) {
                alert("Ocurrió un error al conectar con el servidor.");
            }
        });
    }

    // Handle edit name form submission
    const editNameForm = document.getElementById("editNameForm");
    if (editNameForm) {
        editNameForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const userId = document.getElementById("edit_name_user_id").value;
            const newName = (document.getElementById("edit_name_new").value || "").trim();
            if (newName.length < 2) {
                alert("El nombre debe tener al menos 2 caracteres.");
                return;
            }

            try {
                const res = await fetch(`/usuarios/editar/${encodeURIComponent(userId)}`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ nombre: newName })
                });
                const data = await res.json();
                if (!res.ok || !data.success) {
                    alert("Error: " + (data.error || "No se pudo actualizar el nombre."));
                    return;
                }

                const row = document.querySelector(`tr[data-user-row][data-user-id="${userId}"]`);
                if (row && row.children[1]) {
                    row.children[1].textContent = newName;
                }

                document.querySelectorAll(`.btn-open-edit-name[data-user-id="${userId}"]`).forEach((b) => {
                    b.dataset.nombre = newName;
                });
                document.querySelectorAll(`.btn-view-user[data-username]`).forEach((b) => {
                    if (String(b.dataset.username || "") === String(document.getElementById("edit_name_username").value || "")) {
                        b.dataset.nombre = newName;
                    }
                });
                document.querySelectorAll(`.btn-open-reset[data-user-id="${userId}"]`).forEach((b) => {
                    b.dataset.nombre = newName;
                });
                document.querySelectorAll(`.btn-open-delete[data-user-id="${userId}"]`).forEach((b) => {
                    b.dataset.nombre = newName;
                });

                if (editNameModal) editNameModal.hide();
                alert("Nombre actualizado correctamente.");
            } catch (err) {
                alert("Ocurrió un error al conectar con el servidor.");
            }
        });
    }

    // Handle the delete button confirmation (prefer username, fallback to numeric id)
    const confirmDeleteBtn = document.getElementById("confirmDeleteBtn");
    if (confirmDeleteBtn) {
        confirmDeleteBtn.addEventListener("click", async () => {
            const userId = document.getElementById("delete_user_id").value;
            const username = (document.getElementById("delete_user_username") && document.getElementById("delete_user_username").value) || '';
            // Hide modal/backdrop first
            try { if (deleteUserModal) deleteUserModal.hide(); } catch (e) { /* ignore */ }

            // Choose endpoint: by username if provided, otherwise by numeric id
            let endpoint = '';
            if (username && username.trim()) {
                endpoint = `/usuarios/eliminar/usuario/${encodeURIComponent(username.trim())}`;
            } else {
                endpoint = `/usuarios/eliminar/${userId}`;
            }

            try {
                const res = await fetch(endpoint, { method: 'DELETE' });
                let data = {};
                try { data = await res.json(); } catch (e) { /* not JSON */ }

                if (res.ok && data.success) {
                    alert('Usuario eliminado correctamente.');
                    window.location.reload();
                    return;
                }

                // If deletion blocked by FK constraints, server returns 409 with message
                if (res.status === 409) {
                    const rawError = (data && data.error) ? data.error : '';
                    // Parse technical details and produce a user-friendly short summary
                    let friendlyMsg = 'El usuario tiene referencias que impiden su eliminación.';
                    try {
                        const m = rawError.match(/\(([^)]+)\)/);
                        if (m && m[1]) {
                            const parts = m[1].split(/\s*,\s*/);
                            const mapped = parts.map(p => {
                                const mm = p.match(/(\d+)\s+en\s+(.+)/);
                                if (mm) {
                                    const num = mm[1];
                                    const tech = mm[2].trim();
                                    let label = '';
                                    if (/asignad/i.test(tech)) label = 'asignados';
                                    else if (/seguim/i.test(tech) || /seguimiento/i.test(tech)) label = 'en seguimiento';
                                    else {
                                        const col = tech.split('.').slice(-1)[0].replace(/_id$/i, '').replace(/_/g, ' ');
                                        label = col;
                                    }
                                    if (label === 'en seguimiento') return num + ' en seguimiento';
                                    return num + ' ' + label;
                                }
                                return p;
                            });
                            if (mapped.length === 1) friendlyMsg = mapped[0];
                            else if (mapped.length === 2) friendlyMsg = mapped.join(' y ');
                            else friendlyMsg = mapped.slice(0, -1).join(', ') + ' y ' + mapped.slice(-1);
                        } else if (rawError) {
                            friendlyMsg = rawError.replace(/\b[A-Za-z0-9_]+\.[A-Za-z0-9_]+\b/g, '').replace(/\s+\(|\)/g, '').trim();
                        }
                    } catch (e) {
                        friendlyMsg = rawError || friendlyMsg;
                    }

                    // Ensure any leftover bootstrap backdrop is removed before showing Swal
                    try { ensureModalClosed(); } catch (e) { /* ignore */ }

                    // Offer reassign option with friendly text
                    if (typeof Swal !== 'undefined') {
                        try {
                            const targetsRes = await fetch('/usuarios/api_reassign_targets');
                            const targets = await targetsRes.json();
                                    let html = '<div class= "eliminar mb-2">' + friendlyMsg + '</div>';
                            html += '<div class="mb-2">¿Deseas reasignar esos registros a otro usuario?</div>';
                            // center the select and constrain width to avoid horizontal scroll
                            html += '<div style="display:flex;justify-content:center;padding-top:6px">';
                            html += '<select id="swal-reassign-target" class="swal2-select form-select" style="min-width:280px;max-width:420px;width:100%;">';
                            html += '<option value="">-- Seleccione usuario destino --</option>';
                            targets.forEach(t => {
                                html += '<option value="' + t.id + '">' + (t.nombre || t.usuario) + ' (' + t.usuario + ')</option>';
                            });
                            html += '</select></div>';

                            const { value: targetId } = await Swal.fire({
                                title: 'No se pudo eliminar el usuario',
                                html: html,
                                showCancelButton: true,
                                confirmButtonText: 'Reasignar y eliminar',
                                cancelButtonText: 'Cancelar',
                                focusConfirm: false,
                                preConfirm: () => {
                                    const el = document.getElementById('swal-reassign-target');
                                    return el ? el.value : null;
                                }
                            });

                            // Cleanup any leftover modal/backdrop state
                            try { ensureModalClosed(); } catch (e) { /* ignore */ }

                            if (targetId) {
                                const payload = {
                                    from_user_id: userId || null,
                                    from_username: (username || null),
                                    to_user_id: parseInt(targetId, 10),
                                    delete_after_reassign: true
                                };
                                const r = await fetch('/usuarios/reasignar', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify(payload)
                                });
                                const jr = await r.json();
                                if (r.ok && jr.success) {
                                    const upd = (jr.updated || []).map(x => x.updated + ' en ' + x.table + '.' + x.column).join('\n');
                                    Swal.fire({ icon: 'success', title: 'Reasignado y eliminado', html: '<pre style="text-align:left">' + upd + '</pre>' });
                                    try { ensureModalClosed(); } catch (e) { /* ignore */ }
                                    window.location.reload();
                                } else {
                                    Swal.fire({ icon: 'error', title: 'No se pudo reasignar', text: (jr.error || 'Error al reasignar') });
                                    try { ensureModalClosed(); } catch (e) { /* ignore */ }
                                }
                            }
                        } catch (err) {
                            console.error('Error fetching targets or reassigning:', err);
                            try { Swal.fire({ icon: 'error', title: 'Error', text: 'No fue posible obtener la lista de usuarios destino.' }); } catch (e) { alert('No fue posible obtener la lista de usuarios destino.'); }
                            try { ensureModalClosed(); } catch (e) { /* ignore */ }
                        }
                    } else {
                        // Fallback: ask for target username via prompt
                        const target = prompt(friendlyMsg + '\nIngrese username destino para reasignar (o cancele):');
                        if (target) {
                            try {
                                const payload = { from_user_id: userId || null, from_username: username || null, to_username: target, delete_after_reassign: true };
                                const r = await fetch('/usuarios/reasignar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
                                const jr = await r.json();
                                if (r.ok && jr.success) {
                                    alert('Reasignado y eliminado correctamente.');
                                    try { ensureModalClosed(); } catch (e) { /* ignore */ }
                                    window.location.reload();
                                } else {
                                    alert('Error reasignando: ' + (jr.error || 'Error desconocido'));
                                    try { ensureModalClosed(); } catch (e) { /* ignore */ }
                                }
                            } catch (err) {
                                console.error(err);
                                alert('Error al conectar con el servidor.');
                                try { ensureModalClosed(); } catch (e) { /* ignore */ }
                            }
                        } else {
                            try { ensureModalClosed(); } catch (e) { /* ignore */ }
                        }
                    }
                    return;
                }

                // Other errors
                alert('Error: ' + (data.error || 'Ocurrió un error inesperado.'));
            } catch (err) {
                console.error('Delete request error', err);
                alert('Ocurrió un error al conectar con el servidor.');
            }
        });
    }

    // Sorting controls: client-side sort for usuarios table (including clickable headers)
    (function() {
        const usuariosTable = document.querySelector('table.table');
        const usuariosTbody = usuariosTable ? usuariosTable.querySelector('tbody') : null;
        const sortColumnSelect = document.getElementById('usuarios-sort-column');
        const sortAscBtn = document.getElementById('usuarios-sort-asc');
        const sortDescBtn = document.getElementById('usuarios-sort-desc');
        const headerCells = usuariosTable ? Array.from(usuariosTable.querySelectorAll('th.sortable')) : [];

        let currentSortKey = sortColumnSelect ? sortColumnSelect.value : 'nombre';
        let currentSortDir = 'asc';

        function getColumnIndexByKey(key) {
            if (key === 'nombre') return 1;
            if (key === 'usuario') return 2;
            if (key === 'rol') return 3;
            return 1;
        }

        function updateHeaderIndicators(key, dir) {
            headerCells.forEach(h => {
                const ind = h.querySelector('.sort-indicator');
                if (!ind) return;
                ind.innerHTML = '';
                if (h.dataset.key === key) {
                    if (dir === 'asc') ind.innerHTML = '<i class="bi bi-sort-alpha-down"></i>';
                    else ind.innerHTML = '<i class="bi bi-sort-alpha-down-alt"></i>';
                }
            });
        }

        function sortUsuariosTable(key, dir) {
            if (!usuariosTbody) return;
            currentSortKey = key;
            currentSortDir = dir;
            const rows = Array.from(usuariosTbody.querySelectorAll('tr'));
            const idx = getColumnIndexByKey(key);
            rows.sort((a, b) => {
                const aText = (a.children[idx] && a.children[idx].textContent || '').trim().toLowerCase();
                const bText = (b.children[idx] && b.children[idx].textContent || '').trim().toLowerCase();
                if (key === 'rol') {
                    const ai = parseInt(aText) || 0;
                    const bi = parseInt(bText) || 0;
                    return ai - bi;
                }
                if (aText === bText) return 0;
                return aText.localeCompare(bText);
            });
            if (dir === 'desc') rows.reverse();
            rows.forEach((r) => usuariosTbody.appendChild(r));
            // update numbering
            rows.forEach((r, i) => {
                const badge = r.querySelector('td:first-child span.badge');
                if (badge) badge.textContent = i + 1;
                else if (r.children[0]) r.children[0].textContent = i + 1;
            });
            if (sortAscBtn && sortDescBtn) {
                if (dir === 'asc') { sortAscBtn.classList.add('active'); sortDescBtn.classList.remove('active'); }
                else { sortDescBtn.classList.add('active'); sortAscBtn.classList.remove('active'); }
            }
            if (sortColumnSelect) sortColumnSelect.value = key;
            updateHeaderIndicators(key, dir);
        }

        // Wire up select/buttons
        if (sortColumnSelect && sortAscBtn && sortDescBtn) {
            sortColumnSelect.addEventListener('change', () => {
                const dir = sortAscBtn.classList.contains('active') ? 'asc' : 'desc';
                sortUsuariosTable(sortColumnSelect.value, dir);
            });
            sortAscBtn.addEventListener('click', () => sortUsuariosTable(sortColumnSelect.value, 'asc'));
            sortDescBtn.addEventListener('click', () => sortUsuariosTable(sortColumnSelect.value, 'desc'));
            // default state: asc
            sortAscBtn.classList.add('active');
            sortUsuariosTable(sortColumnSelect.value, 'asc');
        }

        // Make header cells clickable to sort
        if (headerCells && headerCells.length) {
            headerCells.forEach(h => {
                h.addEventListener('click', () => {
                    const key = h.dataset.key;
                    let dir = 'asc';
                    if (key === currentSortKey) dir = currentSortDir === 'asc' ? 'desc' : 'asc';
                    sortUsuariosTable(key, dir);
                });
            });
        }
    })();
});