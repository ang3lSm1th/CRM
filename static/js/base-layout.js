(function () {
  function normalizePath(path) {
    if (!path) return "/";
    const normalized = path.replace(/\/+$/, "");
    return normalized || "/";
  }

  function showFlashPopup() {
    const flashNode = document.getElementById("flash-data");
    if (!flashNode || typeof Swal === "undefined") return;

    let flashes = [];
    const raw = flashNode.getAttribute("data-flashes") || "[]";
    try {
      flashes = JSON.parse(raw);
    } catch (_) {
      flashes = [];
    }

    if (!Array.isArray(flashes) || !flashes.length) return;

    const first = flashes[0];
    const cat = String((first && first[0]) || "").toLowerCase();
    const msg = (first && first[1]) || "";

    let icon = "info";
    if (cat.includes("success") || cat === "lead_created") icon = "success";
    else if (cat.includes("warn") || cat.includes("warning")) icon = "warning";
    else if (cat.includes("danger") || cat.includes("error")) icon = "error";

    Swal.fire({ icon: icon, title: msg, showConfirmButton: false, timer: 3500 });
  }

  function markActiveSidebarLink() {
    const currentPath = normalizePath(window.location.pathname);
    const sidebarLinks = Array.from(document.querySelectorAll(".sidebar-nav a[href]"));
    let bestMatch = null;

    sidebarLinks.forEach((link) => {
      const href = link.getAttribute("href") || "";
      if (!href || href.startsWith("#") || href.startsWith("javascript:")) return;

      const url = new URL(href, window.location.origin);
      const targetPath = normalizePath(url.pathname);
      const isExact = currentPath === targetPath;
      const isSubroute = targetPath !== "/" && currentPath.startsWith(targetPath + "/");

      if (isExact || isSubroute) {
        if (!bestMatch || targetPath.length > bestMatch.path.length) {
          bestMatch = { link: link, path: targetPath };
        }
      }
    });

    if (!bestMatch && /^\/leads\/(create|edit|seguimiento)/.test(currentPath)) {
      const fallbackPath = normalizePath(document.body.dataset.leadsFallbackPath || "/leads/list");
      const leadsLink = document.querySelector('.sidebar-nav a[href="' + fallbackPath + '"]');
      if (leadsLink) bestMatch = { link: leadsLink, path: fallbackPath };
    }

    if (bestMatch && bestMatch.link) {
      bestMatch.link.classList.add("active");
    }
  }

  function setupSidebarToggle() {
    const sidebar = document.getElementById("sidebar");
    const toggleButton = document.getElementById("toggle-sidebar");
    if (!sidebar || !toggleButton) return;

    toggleButton.addEventListener("click", function () {
      const isHidden = sidebar.classList.toggle("hidden");
      const icon = toggleButton.querySelector("i");
      if (!icon) return;
      icon.classList.toggle("bi-chevron-left", !isHidden);
      icon.classList.toggle("bi-chevron-right", isHidden);
    });
  }

  function bootstrapGlobalUserVars() {
    const userName = document.querySelector('meta[name="logged-user-name"]')?.content || "Usuario";
    const username = document.querySelector('meta[name="logged-user-username"]')?.content || "sin_usuario";
    const viewName = document.querySelector("#leads-view-name")?.dataset.viewName || "";
    window.loggedUserName = userName;
    window.loggedUserUsername = username;
    if (viewName) window.leadsViewName = viewName;
  }

  document.addEventListener("DOMContentLoaded", function () {
    bootstrapGlobalUserVars();
    markActiveSidebarLink();
    setupSidebarToggle();
    showFlashPopup();
  });
})();
