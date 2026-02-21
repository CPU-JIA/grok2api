(() => {
  window.__publicSpa__ = true;
  const ASSET_VERSION = '1.5.37';

  function withVersion(url) {
    if (!url || typeof url !== 'string') return url;
    if (!url.startsWith('/static/')) return url;
    if (url.includes('v=')) return url;
    const sep = url.includes('?') ? '&' : '?';
    return `${url}${sep}v=${ASSET_VERSION}`;
  }

  const ROUTES = {
    '/chat': {
      key: 'chat',
      title: 'Chat 聊天',
      fragment: '/static/public/fragments/chat.html',
      css: ['/static/public/css/chat.css'],
      js: ['/static/public/js/chat.js']
    },
    '/imagine': {
      key: 'imagine',
      title: 'Imagine 瀑布流',
      fragment: '/static/public/fragments/imagine.html',
      css: ['/static/public/css/imagine.css'],
      js: [
        'https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js',
        '/static/public/js/imagine.js'
      ]
    },
    '/video': {
      key: 'video',
      title: 'Video 视频生成',
      fragment: '/static/public/fragments/video.html',
      css: ['/static/public/css/video.css'],
      js: ['/static/public/js/video.js']
    },
    '/voice': {
      key: 'voice',
      title: 'LiveKit 陪聊',
      fragment: '/static/public/fragments/voice.html',
      css: ['/static/public/css/voice.css'],
      js: [
        'https://cdn.jsdelivr.net/npm/livekit-client@2.7.3/dist/livekit-client.umd.min.js',
        '/static/public/js/voice.js'
      ]
    }
  };

  const DEFAULT_ROUTE = '/imagine';
  const views = new Map();
  const fragmentCache = new Map();
  const loadedCss = new Set();
  const loadedJs = new Set();
  let routeRequestSeq = 0;
  let activeViewKey = '';

  window.__publicSpaNavigate = (path) => {
    showRoute(normalizePath(path), { push: true });
  };

  function normalizePath(path) {
    if (!path) return DEFAULT_ROUTE;
    const cleaned = path.split('?')[0].split('#')[0];
    return cleaned.endsWith('/') && cleaned !== '/' ? cleaned.slice(0, -1) : cleaned;
  }

  function resolveRoute(path) {
    if (ROUTES[path]) return ROUTES[path];
    return ROUTES[DEFAULT_ROUTE];
  }

  function setTitle(title) {
    if (title) {
      document.title = `Grok2API - ${title}`;
    }
  }

  function setActiveNav(path) {
    if (typeof window.__publicSetActiveNav === 'function') {
      window.__publicSetActiveNav(path);
      return;
    }
    const links = document.querySelectorAll('a[data-nav]');
    links.forEach((link) => {
      const target = link.getAttribute('data-nav') || '';
      link.classList.toggle('active', target && path.startsWith(target));
    });
  }

  function hideAllViews() {
    const mount = document.getElementById('public-main');
    views.forEach((view) => {
      view.classList.remove('is-active');
      view.classList.add('hidden');
      if (mount && view.parentElement === mount) {
        mount.removeChild(view);
      }
    });
    activeViewKey = '';
  }

  async function loadCss(href) {
    const finalHref = withVersion(href);
    if (!finalHref || loadedCss.has(finalHref)) return;
    loadedCss.add(finalHref);
    const ok = await new Promise((resolve) => {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = finalHref;
      link.onload = () => resolve(true);
      link.onerror = () => resolve(false);
      document.head.appendChild(link);
    });
    if (!ok) {
      loadedCss.delete(finalHref);
    }
  }

  async function loadScript(src) {
    const finalSrc = withVersion(src);
    if (!finalSrc || loadedJs.has(finalSrc)) return;
    loadedJs.add(finalSrc);
    const ok = await new Promise((resolve) => {
      const script = document.createElement('script');
      script.src = finalSrc;
      script.async = false;
      script.onload = () => resolve(true);
      script.onerror = () => resolve(false);
      document.body.appendChild(script);
    });
    if (!ok) {
      loadedJs.delete(finalSrc);
    }
  }

  async function ensureAssets(route, requestSeq) {
    if (!route) return false;
    const cssList = route.css || [];
    for (const href of cssList) {
      if (requestSeq !== routeRequestSeq || window.__publicActivePage !== route.key) {
        return false;
      }
      await loadCss(href);
    }
    const jsList = route.js || [];
    for (const src of jsList) {
      if (requestSeq !== routeRequestSeq || window.__publicActivePage !== route.key) {
        return false;
      }
      await loadScript(src);
    }
    return true;
  }

  async function fetchFragment(route) {
    if (fragmentCache.has(route.key)) {
      return fragmentCache.get(route.key);
    }
    const res = await fetch(withVersion(route.fragment), { credentials: 'same-origin' });
    if (!res.ok) {
      throw new Error(`加载失败: ${res.status}`);
    }
    const html = await res.text();
    fragmentCache.set(route.key, html);
    return html;
  }

  async function ensureView(route) {
    if (views.has(route.key)) {
      return views.get(route.key);
    }
    const html = await fetchFragment(route);
    const wrapper = document.createElement('div');
    wrapper.className = 'public-view hidden';
    wrapper.dataset.route = route.key;
    wrapper.innerHTML = html;
    views.set(route.key, wrapper);
    return wrapper;
  }

  async function showRoute(path, options = {}) {
    const normalizedPath = normalizePath(path);
    const route = resolveRoute(normalizedPath);
    const requestSeq = ++routeRequestSeq;

    if (options.push) {
      history.pushState({}, '', normalizedPath);
    }

    setTitle(route.title);
    setActiveNav(normalizedPath);
    window.__publicActivePage = route.key;

    if (activeViewKey === route.key) {
      return;
    }

    let view;
    try {
      view = await ensureView(route);
    } catch (e) {
      console.warn(e);
      return;
    }

    if (requestSeq !== routeRequestSeq || window.__publicActivePage !== route.key) {
      return;
    }

    const mount = document.getElementById('public-main');
    hideAllViews();
    if (mount && view && view.parentElement !== mount) {
      mount.appendChild(view);
    }
    view.classList.remove('hidden');
    view.classList.remove('is-active');
    requestAnimationFrame(() => {
      if (window.__publicActivePage === route.key) {
        view.classList.add('is-active');
        activeViewKey = route.key;
      }
    });

    ensureAssets(route, requestSeq).catch((e) => console.warn(e));
  }

  function prefetchAll() {
    Object.values(ROUTES).forEach((route) => {
      if (!route.fragment) return;
      fetch(withVersion(route.fragment))
        .then((res) => (res.ok ? res.text() : ''))
        .then((html) => {
          if (html) fragmentCache.set(route.key, html);
        })
        .catch(() => {});

      (route.css || []).forEach((href) => {
        loadCss(href).catch(() => {});
        const finalHref = withVersion(href);
        if (loadedCss.has(finalHref)) return;
        const link = document.createElement('link');
        link.rel = 'prefetch';
        link.href = finalHref;
        document.head.appendChild(link);
      });

      (route.js || []).forEach((src) => {
        const finalSrc = withVersion(src);
        if (loadedJs.has(finalSrc)) return;
        const link = document.createElement('link');
        link.rel = 'prefetch';
        link.as = 'script';
        link.href = finalSrc;
        document.head.appendChild(link);
      });
    });
  }

  window.addEventListener('popstate', () => {
    showRoute(normalizePath(window.location.pathname), { push: false });
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      showRoute(normalizePath(window.location.pathname), { push: false });
      setTimeout(prefetchAll, 120);
    });
  } else {
    showRoute(normalizePath(window.location.pathname), { push: false });
    setTimeout(prefetchAll, 120);
  }
})();
