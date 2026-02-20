async function loadAdminHeader() {
  const container = document.getElementById('app-header');
  if (!container) return;
  try {
    const res = await fetch('/static/common/html/header.html?v=1.5.1');
    if (!res.ok) return;
    container.innerHTML = await res.text();
    const links = container.querySelectorAll('a[data-nav]');

    function setActiveNav(path) {
      links.forEach((link) => {
        const target = link.getAttribute('data-nav') || '';
        link.classList.toggle('active', target && path.startsWith(target));
      });
    }

    window.__adminSetActiveNav = setActiveNav;
    setActiveNav(window.location.pathname);

    links.forEach((link) => {
      link.addEventListener('click', (event) => {
        const target = link.getAttribute('data-nav') || '';
        if (window.__adminSpaNavigate && target) {
          event.preventDefault();
          window.__adminSpaNavigate(target);
        }
      });
    });
    if (typeof updateStorageModeButton === 'function') {
      updateStorageModeButton();
    }
  } catch (e) {
    // Fail silently to avoid breaking page load
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', loadAdminHeader);
} else {
  loadAdminHeader();
}

