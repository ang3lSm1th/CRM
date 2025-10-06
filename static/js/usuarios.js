document.addEventListener("DOMContentLoaded", () => {
    const resetPwModalElement = document.getElementById("resetPwModal");
    const viewUserModalElement = document.getElementById("viewUserModal");
    const deleteUserModalElement = document.getElementById("deleteUserModal");
    
    // Only initialize modals if their corresponding elements exist on the page
    const resetPwModal = resetPwModalElement ? new bootstrap.Modal(resetPwModalElement) : null;
    const viewUserModal = viewUserModalElement ? new bootstrap.Modal(viewUserModalElement) : null;
    const deleteUserModal = deleteUserModalElement ? new bootstrap.Modal(deleteUserModalElement) : null;

    // Fill the reset password modal fields
    document.querySelectorAll(".btn-open-reset").forEach(btn => {
        btn.addEventListener("click", () => {
            document.getElementById("modal_user_id").value = btn.dataset.userId;
            document.getElementById("modal_username").value = btn.dataset.username;
            document.getElementById("modal_nombre").value = btn.dataset.nombre;
            document.getElementById("modal_new_password").value = "";
        });
    });

    // Fill the view user modal fields
    document.querySelectorAll(".btn-view-user").forEach(btn => {
        btn.addEventListener("click", () => {
            document.getElementById("view_nombre").textContent = btn.dataset.nombre;
            document.getElementById("view_usuario").textContent = btn.dataset.username;
            document.getElementById("view_rol").textContent = btn.dataset.rol;
        });
    });

    // Fill the delete user modal fields
    document.querySelectorAll(".btn-open-delete").forEach(btn => {
        btn.addEventListener("click", () => {
            const userId = btn.dataset.userId;
            const username = btn.dataset.username;
            const nombre = btn.dataset.nombre;
            document.getElementById("delete_user_id").value = userId;
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
                } else {
                    alert("Error: " + (data.error || "Ocurrió un error inesperado."));
                }
            } catch (err) {
                alert("Ocurrió un error al conectar con el servidor.");
            }
        });
    }

    // Handle the delete button confirmation
    const confirmDeleteBtn = document.getElementById("confirmDeleteBtn");
    if (confirmDeleteBtn) {
        confirmDeleteBtn.addEventListener("click", async () => {
            const userId = document.getElementById("delete_user_id").value;
            try {
                const res = await fetch(`/usuarios/eliminar/${userId}`, {
                    method: "DELETE"
                });
                const data = await res.json();
                if (res.ok && data.success) {
                    alert("Usuario eliminado correctamente.");
                    window.location.reload();
                } else {
                    alert("Error: " + (data.error || "Ocurrió un error inesperado."));
                }
            } catch (err) {
                alert("Ocurrió un error al conectar con el servidor.");
            } finally {
                if (deleteUserModal) deleteUserModal.hide();
            }
        });
    }
});