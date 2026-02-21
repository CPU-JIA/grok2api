async function loadPublicHeader() {
  const container = document.getElementById('app-header');
  if (!container) return;
  try {
    const res = await fetch('/static/common/html/public-header.html?v=1.5.18');
    if (!res.ok) return;
    container.innerHTML = await res.text();
    const logoutBtn = container.querySelector('#public-logout-btn');
    if (logoutBtn) {
      logoutBtn.classList.remove('hidden');
    }
    const links = container.querySelectorAll('a[data-nav]');

    function setActiveNav(path) {
      links.forEach((link) => {
        const target = link.getAttribute('data-nav') || '';
        link.classList.toggle('active', !!target && path.startsWith(target));
      });
    }

    window.__publicSetActiveNav = setActiveNav;
    setActiveNav(window.location.pathname);

    links.forEach((link) => {
      link.addEventListener('click', (event) => {
        const target = link.getAttribute('data-nav') || '';
        if (window.__publicSpaNavigate && target) {
          event.preventDefault();
          window.__publicSpaNavigate(target);
        }
      });
    });
  } catch (e) {
    // Fail silently to avoid breaking page load
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', loadPublicHeader);
} else {
  loadPublicHeader();
}

