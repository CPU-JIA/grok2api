(() => {
  window.__adminSpa__ = true;
  const ASSET_VERSION = '1.5.42';

  function withVersion(url) {
    if (!url || typeof url !== 'string') return url;
    if (!url.startsWith('/static/')) return url;
    if (url.includes('v=')) return url;
    const sep = url.includes('?') ? '&' : '?';
    return `${url}${sep}v=${ASSET_VERSION}`;
  }

  const ROUTES = {
    '/admin/token': {
      key: 'token',
      title: 'Token 管理',
      fragment: '/static/admin/fragments/token.html',
      css: ['/static/admin/css/token.css'],
      js: [
        '/static/common/js/batch-sse.js',
        '/static/common/js/draggable.js',
        '/static/admin/js/token.js'
      ]
    },
    '/admin/imagine': {
      key: 'imagine',
      title: 'Imagine',
      fragment: '/static/admin/fragments/imagine.html',
      css: ['/static/public/css/imagine.css', '/static/admin/css/imagine-admin.css'],
      js: [
        'https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js',
        '/static/public/js/imagine.js'
      ]
    },
    '/admin/voice': {
      key: 'voice',
      title: 'Voice',
      fragment: '/static/admin/fragments/voice.html',
      css: ['/static/public/css/voice.css'],
      js: [
        'https://cdn.jsdelivr.net/npm/livekit-client@2.7.3/dist/livekit-client.umd.min.js',
        '/static/public/js/voice.js'
      ]
    },
    '/admin/keys': {
      key: 'keys',
      title: 'Key 管理',
      fragment: '/static/admin/fragments/keys.html',
      css: ['/static/admin/css/keys.css'],
      js: ['/static/admin/js/keys.js']
    },
    '/admin/sessions': {
      key: 'sessions',
      title: '会话管理',
      fragment: '/static/admin/fragments/sessions.html',
      css: ['/static/admin/css/sessions.css'],
      js: ['/static/admin/js/sessions.js']
    },
    '/admin/stats': {
      key: 'stats',
      title: '统计监控',
      fragment: '/static/admin/fragments/stats.html',
      css: ['/static/admin/css/stats.css'],
      js: [
        'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js',
        '/static/admin/js/stats.js'
      ]
    },
    '/admin/cache': {
      key: 'cache',
      title: '缓存预览',
      fragment: '/static/admin/fragments/cache.html',
      css: ['/static/admin/css/cache.css'],
      js: [
        '/static/common/js/batch-sse.js',
        '/static/common/js/draggable.js',
        '/static/admin/js/cache.js'
      ]
    },
    '/admin/config': {
      key: 'config',
      title: '配置管理',
      fragment: '/static/admin/fragments/config.html',
      css: ['/static/admin/css/config.css'],
      js: ['/static/admin/js/config.js']
    }
  };

  const DEFAULT_ROUTE = '/admin/token';
  const views = new Map();
  const loadedCss = new Set();
  const loadedJs = new Set();
  const initRegistry = new Map();
  const initDone = new Set();
  const initRunning = new Set();
  let routeRequestSeq = 0;

  window.__registerAdminPage = (key, initFn) => {
    if (!key || typeof initFn !== 'function') return;
    initRegistry.set(key, initFn);
    if (window.__adminActivePage === key && !initDone.has(key) && !initRunning.has(key)) {
      initRunning.add(key);
      Promise.resolve()
        .then(() => initFn())
        .then((result) => {
          if (result !== false) initDone.add(key);
        })
        .catch((e) => console.warn(e))
        .finally(() => initRunning.delete(key));
    }
  };

  window.__adminSpaNavigate = (path) => {
    showRoute(normalizePath(path), { push: true });
  };

  function normalizePath(path) {
    if (!path) return DEFAULT_ROUTE;
    const cleaned = path.split('?')[0].split('#')[0];
    return cleaned.endsWith('/') && cleaned !== '/admin/' ? cleaned.slice(0, -1) : cleaned;
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
    if (typeof window.__adminSetActiveNav === 'function') {
      window.__adminSetActiveNav(path);
      return;
    }
    const links = document.querySelectorAll('a[data-nav]');
    links.forEach((link) => {
      const target = link.getAttribute('data-nav') || '';
      link.classList.toggle('active', path.startsWith(target));
    });
  }

  function hideAllViews() {
    const mount = document.getElementById('app-main');
    views.forEach((view) => {
      view.classList.add('hidden');
      if (mount && view.parentElement === mount) {
        mount.removeChild(view);
      }
    });
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
      if (requestSeq !== routeRequestSeq || window.__adminActivePage !== route.key) {
        return false;
      }
      await loadCss(href);
    }
    const jsList = route.js || [];
    for (const src of jsList) {
      if (requestSeq !== routeRequestSeq || window.__adminActivePage !== route.key) {
        return false;
      }
      await loadScript(src);
    }
    return true;
  }

  async function fetchFragment(route) {
    const res = await fetch(withVersion(route.fragment), { credentials: 'same-origin' });
    if (!res.ok) {
      throw new Error(`加载失败: ${res.status}`);
    }
    return res.text();
  }

  async function ensureView(route) {
    if (views.has(route.key)) {
      return views.get(route.key);
    }
    const html = await fetchFragment(route);
    const wrapper = document.createElement('div');
    wrapper.className = 'admin-view hidden';
    wrapper.dataset.route = route.key;
    wrapper.innerHTML = html;
    views.set(route.key, wrapper);
    return wrapper;
  }

  async function runInit(route) {
    if (!route || !route.key) return;
    if (window.__adminActivePage !== route.key) return;
    if (initDone.has(route.key) || initRunning.has(route.key)) return;
    const initFn = initRegistry.get(route.key);
    if (!initFn) return;
    initRunning.add(route.key);
    try {
      const result = await initFn();
      if (result !== false) {
        initDone.add(route.key);
      }
    } catch (e) {
      console.warn(e);
    } finally {
      initRunning.delete(route.key);
    }
  }

  async function showRoute(path, options = {}) {
    const route = resolveRoute(path);
    const requestSeq = ++routeRequestSeq;
    if (options.push) {
      history.pushState({}, '', path);
    }
    setTitle(route.title);
    setActiveNav(path);
    window.__adminActivePage = route.key;

    let view;
    try {
      view = await ensureView(route);
    } catch (e) {
      console.warn(e);
      return;
    }

    if (requestSeq !== routeRequestSeq || window.__adminActivePage !== route.key) {
      return;
    }

    const mount = document.getElementById('app-main');
    hideAllViews();
    if (mount && view && view.parentElement !== mount) {
      mount.appendChild(view);
    }
    view.classList.remove('hidden');

    ensureAssets(route, requestSeq).then((ready) => {
      if (!ready) return;
      if (requestSeq !== routeRequestSeq || window.__adminActivePage !== route.key) return;
      scheduleInit(route, 0, requestSeq);
    });
  }

  function scheduleInit(route, attempt = 0, requestSeq = routeRequestSeq) {
    if (!route || !route.key) return;
    if (requestSeq !== routeRequestSeq || window.__adminActivePage !== route.key) return;
    runInit(route);
    if (initDone.has(route.key)) return;
    if (attempt >= 3) return;
    setTimeout(() => {
      if (requestSeq !== routeRequestSeq || window.__adminActivePage !== route.key) return;
      if (!initDone.has(route.key)) {
        scheduleInit(route, attempt + 1, requestSeq);
      }
    }, 120);
  }

  function prefetchAll() {
    Object.values(ROUTES).forEach((route) => {
      if (!route.fragment) return;
      fetch(withVersion(route.fragment)).then(() => {}).catch(() => {});
      (route.css || []).forEach((href) => {
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
    showRoute(normalizePath(window.location.pathname));
  });

  const initialPath = normalizePath(window.location.pathname);
  showRoute(initialPath || DEFAULT_ROUTE);

  if ('requestIdleCallback' in window) {
    window.requestIdleCallback(prefetchAll);
  } else {
    setTimeout(prefetchAll, 500);
  }
})();



