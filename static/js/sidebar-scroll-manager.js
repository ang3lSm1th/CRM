/**
 * Sidebar Scroll Position Manager
 * Mantiene la posición de scroll del sidebar al navegar entre páginas
 */

(function() {
    'use strict';

    const STORAGE_KEY = 'sidebarScrollPosition';

    document.addEventListener('DOMContentLoaded', function() {
        // El scroll está en .sidebar-nav, no en #sidebar
        const sidebarNav = document.querySelector('.sidebar-nav');
        
        if (!sidebarNav) return;

        // Restaurar la posición del scroll al cargar la página
        restoreScrollPosition(sidebarNav);

        // Guardar la posición del scroll cuando el usuario se desplaza
        sidebarNav.addEventListener('scroll', function() {
            saveScrollPosition(sidebarNav.scrollTop);
        });

        // Guardar la posición antes de navegar a otra página
        const sidebarLinks = document.querySelectorAll('.sidebar-nav a');
        sidebarLinks.forEach(link => {
            link.addEventListener('click', function(e) {
                saveScrollPosition(sidebarNav.scrollTop);
            });
        });

        // También guardar cuando se hace clic en cualquier parte antes de salir
        window.addEventListener('beforeunload', function() {
            saveScrollPosition(sidebarNav.scrollTop);
        });

        // Limpiar la posición guardada al cerrar sesión
        const logoutLink = document.querySelector('.nav-section-logout a');
        if (logoutLink) {
            logoutLink.addEventListener('click', function() {
                clearScrollPosition();
            });
        }
    });

    function saveScrollPosition(position) {
        try {
            localStorage.setItem(STORAGE_KEY, position.toString());
            console.log('Posición guardada:', position);
        } catch (e) {
            console.warn('No se pudo guardar la posición del sidebar:', e);
        }
    }

    function restoreScrollPosition(sidebarNav) {
        try {
            const savedPosition = localStorage.getItem(STORAGE_KEY);
            if (savedPosition !== null) {
                const position = parseInt(savedPosition, 10);
                console.log('Restaurando posición:', position);
                // Usar setTimeout para asegurar que el DOM esté completamente cargado
                setTimeout(() => {
                    sidebarNav.scrollTop = position;
                }, 50);
            }
        } catch (e) {
            console.warn('No se pudo restaurar la posición del sidebar:', e);
        }
    }

    function clearScrollPosition() {
        try {
            localStorage.removeItem(STORAGE_KEY);
            console.log('Posición del sidebar limpiada');
        } catch (e) {
            console.warn('No se pudo limpiar la posición del sidebar:', e);
        }
    }
})();
