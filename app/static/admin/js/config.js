(() => {
let apiKey = '';
let currentConfig = {};
let activeTab = 'global';
const byId = (id) => document.getElementById(id);
const TAB_STORAGE_KEY = 'admin_config_active_tab';
const CONFIG_TABS = [
  {
    id: 'global',
    label: '全局配置',
    icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h6"></path><path d="M14 6h6"></path><circle cx="12" cy="6" r="2"></circle><path d="M4 12h10"></path><path d="M18 12h2"></path><circle cx="16" cy="12" r="2"></circle><path d="M4 18h2"></path><path d="M10 18h10"></path><circle cx="8" cy="18" r="2"></circle></svg>',
    sections: ['app', 'cache']
  },
  {
    id: 'grok',
    label: 'Grok 配置',
    icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 4 7v10l8 4 8-4V7z"></path><path d="m4 7 8 4 8-4"></path><path d="m12 11 0 10"></path></svg>',
    sections: ['proxy', 'retry', 'chat', 'image', 'video', 'voice', 'asset', 'nsfw', 'usage']
  },
  {
    id: 'token',
    label: 'Token 与会话',
    icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 3 7.5 12 12l9-4.5L12 3z"></path><path d="m3 12 9 4.5 9-4.5"></path><path d="M7 18h6"></path><path d="m9 21 2-3 2 3"></path></svg>',
    sections: ['token', 'conversation']
  },
  {
    id: 'monitor',
    label: '监控与扩展',
    icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3v18h18"></path><path d="m7 14 4-4 3 3 5-6"></path></svg>',
    sections: ['api_keys', 'stats', 'logs', 'mcp']
  }
];
const TAB_MAP = new Map(CONFIG_TABS.map((tab) => [tab.id, tab]));
const TAB_COVERED_SECTIONS = new Set(CONFIG_TABS.flatMap((tab) => tab.sections));
const NUMERIC_FIELDS = new Set([
  'timeout',
  'max_retry',
  'retry_backoff_base',
  'retry_backoff_factor',
  'retry_backoff_max',
  'retry_budget',
  'refresh_interval_hours',
  'super_refresh_interval_hours',
  'fail_threshold',
  'limit_mb',
  'save_delay_ms',
  'usage_flush_interval_sec',
  'upload_concurrent',
  'upload_timeout',
  'download_concurrent',
  'download_timeout',
  'list_concurrent',
  'list_timeout',
  'list_batch_size',
  'delete_concurrent',
  'delete_timeout',
  'delete_batch_size',
  'reload_interval_sec',
  'stream_timeout',
  'stream_first_timeout',
  'stream_total_timeout',
  'pool_refresh_sec',
  'pool_403_max',
  'cooldown_error_requests',
  'cooldown_429_quota_sec',
  'cooldown_429_empty_sec',
  'final_timeout',
  'final_min_bytes',
  'medium_min_bytes',
  'concurrent',
  'batch_size',
  'ttl_seconds',
  'max_per_token',
  'cleanup_interval_sec',
  'hourly_keep',
  'daily_keep',
  'max_len'
]);

const LOCALE_MAP = {
  "app": {
    "label": "应用设置",
    "api_key": { title: "API 密钥", desc: "调用 Grok2API 服务的 Token（可选）。" },
    "app_key": { title: "后台密码", desc: "登录 Grok2API 管理后台的密码（必填）。" },
    "public_enabled": { title: "启用功能玩法", desc: "是否启用功能玩法入口（关闭则功能玩法页面不可访问）。" },
    "public_key": { title: "Public 密码", desc: "功能玩法页面的访问密码（可选）。" },
    "app_url": { title: "应用地址", desc: "当前 Grok2API 服务的外部访问 URL，用于文件链接访问。" },
    "image_format": { title: "图片格式", desc: "默认生成的图片格式（url 或 base64）。" },
    "video_format": { title: "视频格式", desc: "默认生成的视频格式（html 或 url，url 为处理后的链接）。" },
    "temporary": { title: "临时对话", desc: "是否默认启用临时对话模式。" },
    "disable_memory": { title: "禁用记忆", desc: "是否默认禁用 Grok 记忆功能。" },
    "stream": { title: "流式响应", desc: "是否默认启用流式输出。" },
    "thinking": { title: "思维链", desc: "是否默认启用思维链输出。" },
    "dynamic_statsig": { title: "动态指纹", desc: "是否默认启用动态生成 Statsig 指纹。" },
    "filter_tags": { title: "过滤标签", desc: "设置自动过滤 Grok 响应中的特殊标签。" }
  },


  "proxy": {
    "label": "代理配置",
    "base_proxy_url": { title: "基础代理 URL", desc: "代理请求到 Grok 官网的基础服务地址。" },
    "asset_proxy_url": { title: "资源代理 URL", desc: "代理请求到 Grok 官网的静态资源（图片/视频）地址。" },
    "pool_url": { title: "代理池 URL", desc: "动态代理池地址，返回可用代理 URL。" },
    "pool_refresh_sec": { title: "代理池刷新间隔", desc: "动态代理池刷新周期（秒）。" },
    "pool_403_max": { title: "403 换 IP 重试", desc: "遇到 403 时最多换代理重试次数。" },
    "cf_clearance": { title: "CF Clearance", desc: "Cloudflare Clearance Cookie，用于绕过反爬虫验证。" },
    "browser": { title: "浏览器指纹", desc: "curl_cffi 浏览器指纹标识（如 chrome136）。" },
    "user_agent": { title: "User-Agent", desc: "HTTP 请求的 User-Agent 字符串，需与浏览器指纹匹配。" }
  },


  "retry": {
    "label": "重试策略",
    "max_retry": { title: "最大重试次数", desc: "请求 Grok 服务失败时的最大重试次数。" },
    "retry_status_codes": { title: "重试状态码", desc: "触发重试的 HTTP 状态码列表。" },
    "retry_backoff_base": { title: "退避基数", desc: "重试退避的基础延迟（秒）。" },
    "retry_backoff_factor": { title: "退避倍率", desc: "重试退避的指数放大系数。" },
    "retry_backoff_max": { title: "退避上限", desc: "单次重试等待的最大延迟（秒）。" },
    "retry_budget": { title: "退避预算", desc: "单次请求的最大重试总耗时（秒）。" }
  },


  "chat": {
    "label": "对话配置",
    "concurrent": { title: "并发上限", desc: "Reverse 接口并发上限。" },
    "timeout": { title: "请求超时", desc: "Reverse 接口超时时间（秒）。" },
    "stream_first_timeout": { title: "首次响应超时", desc: "首个流式 chunk 的最大等待时间（秒）。" },
    "stream_timeout": { title: "块间空闲超时", desc: "流式 chunk 间最大空闲时间（秒）。" },
    "stream_total_timeout": { title: "总流式超时", desc: "单次流式请求总超时（秒）。" }
  },


  "video": {
    "label": "视频配置",
    "concurrent": { title: "并发上限", desc: "Reverse 接口并发上限。" },
    "timeout": { title: "请求超时", desc: "Reverse 接口超时时间（秒）。" },
    "stream_first_timeout": { title: "首次响应超时", desc: "首个流式 chunk 的最大等待时间（秒）。" },
    "stream_timeout": { title: "块间空闲超时", desc: "流式 chunk 间最大空闲时间（秒）。" },
    "stream_total_timeout": { title: "总流式超时", desc: "单次流式请求总超时（秒）。" }
  },


  "image": {
    "label": "图像配置",
    "timeout": { title: "请求超时", desc: "WebSocket 请求超时时间（秒）。" },
    "stream_first_timeout": { title: "首次响应超时", desc: "首个流式 chunk 的最大等待时间（秒）。" },
    "stream_timeout": { title: "块间空闲超时", desc: "WebSocket 流式 chunk 间最大空闲时间（秒）。" },
    "stream_total_timeout": { title: "总流式超时", desc: "单次流式请求总超时（秒）。" },
    "final_timeout": { title: "最终图超时", desc: "收到中等图后等待最终图的超时秒数。" },
    "nsfw": { title: "NSFW 模式", desc: "WebSocket 请求是否启用 NSFW。" },
    "medium_min_bytes": { title: "中等图最小字节", desc: "判定中等质量图的最小字节数。" },
    "final_min_bytes": { title: "最终图最小字节", desc: "判定最终图的最小字节数（通常 JPG > 100KB）。" }
  },


  "asset": {
    "label": "资产配置",
    "upload_concurrent": { title: "上传并发", desc: "上传接口的最大并发数。推荐 30。" },
    "upload_timeout": { title: "上传超时", desc: "上传接口超时时间（秒）。推荐 60。" },
    "download_concurrent": { title: "下载并发", desc: "下载接口的最大并发数。推荐 30。" },
    "download_timeout": { title: "下载超时", desc: "下载接口超时时间（秒）。推荐 60。" },
    "list_concurrent": { title: "查询并发", desc: "资产查询接口的最大并发数。推荐 10。" },
    "list_timeout": { title: "查询超时", desc: "资产查询接口超时时间（秒）。推荐 60。" },
    "list_batch_size": { title: "查询批次大小", desc: "单次查询可处理的 Token 数量。推荐 10。" },
    "delete_concurrent": { title: "删除并发", desc: "资产删除接口的最大并发数。推荐 10。" },
    "delete_timeout": { title: "删除超时", desc: "资产删除接口超时时间（秒）。推荐 60。" },
    "delete_batch_size": { title: "删除批次大小", desc: "单次删除可处理的 Token 数量。推荐 10。" }
  },


  "voice": {
    "label": "语音配置",
    "timeout": { title: "请求超时", desc: "Voice 请求超时时间（秒）。" }
  },


  "token": {
    "label": "Token 池管理",
    "auto_refresh": { title: "自动刷新", desc: "是否开启 Token 自动刷新机制。" },
    "refresh_interval_hours": { title: "刷新间隔", desc: "普通 Token 刷新的时间间隔（小时）。" },
    "super_refresh_interval_hours": { title: "Super 刷新间隔", desc: "Super Token 刷新的时间间隔（小时）。" },
    "fail_threshold": { title: "失败阈值", desc: "单个 Token 连续失败多少次后被标记为不可用。" },
    "cooldown_error_requests": { title: "错误次数冷却", desc: "普通错误后，Token 需要跳过的请求次数。" },
    "cooldown_429_quota_sec": { title: "429 有额度冷却", desc: "429 且仍有额度时冷却秒数。" },
    "cooldown_429_empty_sec": { title: "429 无额度冷却", desc: "429 且无额度时冷却秒数。" },
    "save_delay_ms": { title: "保存延迟", desc: "Token 变更合并写入的延迟（毫秒）。" },
    "usage_flush_interval_sec": { title: "用量落库间隔", desc: "用量类字段写入数据库的最小间隔（秒）。" },
    "reload_interval_sec": { title: "同步间隔", desc: "多 worker 场景下 Token 状态刷新间隔（秒）。" }
  },


  "cache": {
    "label": "缓存管理",
    "enable_auto_clean": { title: "自动清理", desc: "是否启用缓存自动清理，开启后按上限自动回收。" },
    "limit_mb": { title: "清理阈值", desc: "缓存大小阈值（MB），超过阈值会触发清理。" }
  },


  "nsfw": {
    "label": "NSFW 配置",
    "concurrent": { title: "并发上限", desc: "批量开启 NSFW 模式时的并发请求上限。推荐 10。" },
    "batch_size": { title: "批次大小", desc: "批量开启 NSFW 模式的单批处理数量。推荐 50。" },
    "timeout": { title: "请求超时", desc: "NSFW 开启相关请求的超时时间（秒）。推荐 60。" }
  },


  "usage": {
    "label": "Usage 配置",
    "concurrent": { title: "并发上限", desc: "批量刷新用量时的并发请求上限。推荐 10。" },
    "batch_size": { title: "批次大小", desc: "批量刷新用量的单批处理数量。推荐 50。" },
    "timeout": { title: "请求超时", desc: "用量查询接口的超时时间（秒）。推荐 60。" }
  },


  "conversation": {
    "label": "会话管理",
    "ttl_seconds": { title: "会话 TTL", desc: "会话过期时间（秒），过期自动清理。" },
    "max_per_token": { title: "单 Token 上限", desc: "每个 Token 最多保留会话数量。" },
    "cleanup_interval_sec": { title: "清理间隔", desc: "会话自动清理的轮询间隔（秒）。" },
    "save_delay_ms": { title: "写入延迟", desc: "会话写盘合并延迟（毫秒）。" }
  },


  "stats": {
    "label": "统计配置",
    "hourly_keep": { title: "小时统计保留", desc: "保留最近多少条小时统计数据。" },
    "daily_keep": { title: "天统计保留", desc: "保留最近多少条天统计数据。" },
    "save_delay_ms": { title: "写入延迟", desc: "统计写入合并延迟（毫秒）。" }
  },


  "logs": {
    "label": "日志配置",
    "max_len": { title: "日志保留条数", desc: "最多保留的请求日志数量。" },
    "save_delay_ms": { title: "写入延迟", desc: "日志写入合并延迟（毫秒）。" }
  },


  "api_keys": {
    "label": "API Key 配置",
    "save_delay_ms": { title: "写入延迟", desc: "API Key 保存合并延迟（毫秒）。" }
  },


  "mcp": {
    "label": "MCP 配置",
    "enabled": { title: "启用 MCP", desc: "是否启用 MCP streamable-http 服务。" },
    "mount_path": { title: "挂载路径", desc: "MCP HTTP 子应用挂载路径。" },
    "api_key": { title: "MCP 访问密钥", desc: "MCP 独立访问令牌，留空则回退 app.api_key。" }
  }
};

// 配置部分说明（可选）
const SECTION_DESCRIPTIONS = {
  "proxy": "配置不正确将导致 403 错误。服务首次请求 Grok 时的 IP 必须与获取 CF Clearance 时的 IP 一致，后续服务器请求 IP 变化不会导致 403。"
};

const SECTION_ORDER = new Map(Object.keys(LOCALE_MAP).map((key, index) => [key, index]));


const SECTION_GROUPS = {
  app: [
    { title: '系统设置', keys: ['api_key', 'app_key', 'public_enabled', 'public_key'] },
    { title: '媒体设置', keys: ['app_url', 'image_format', 'video_format'] },
    { title: '会话与指纹', keys: ['temporary', 'disable_memory', 'stream', 'thinking', 'dynamic_statsig', 'filter_tags'] }
  ],
  proxy: [
    { title: '基础代理', keys: ['base_proxy_url', 'asset_proxy_url', 'cf_clearance', 'browser', 'user_agent'] },
    { title: '动态代理池', keys: ['pool_url', 'pool_refresh_sec', 'pool_403_max'] }
  ],
  chat: [
    { title: '并发控制', keys: ['concurrent'] },
    { title: '流式超时', keys: ['timeout', 'stream_first_timeout', 'stream_timeout', 'stream_total_timeout'] }
  ],
  image: [
    { title: '生成参数', keys: ['timeout', 'nsfw', 'medium_min_bytes', 'final_min_bytes', 'final_timeout'] },
    { title: '流式超时', keys: ['stream_first_timeout', 'stream_timeout', 'stream_total_timeout'] }
  ],
  video: [
    { title: '并发控制', keys: ['concurrent'] },
    { title: '流式超时', keys: ['timeout', 'stream_first_timeout', 'stream_timeout', 'stream_total_timeout'] }
  ],
  voice: [
    { title: '语音连接', keys: ['timeout'] }
  ],
  asset: [
    { title: '上传下载', keys: ['upload_concurrent', 'upload_timeout', 'download_concurrent', 'download_timeout'] },
    { title: '资产查询', keys: ['list_concurrent', 'list_timeout', 'list_batch_size'] },
    { title: '资产删除', keys: ['delete_concurrent', 'delete_timeout', 'delete_batch_size'] }
  ],
  nsfw: [
    { title: '批量任务', keys: ['concurrent', 'batch_size', 'timeout'] }
  ],
  usage: [
    { title: '批量任务', keys: ['concurrent', 'batch_size', 'timeout'] }
  ],
  token: [
    { title: '刷新策略', keys: ['auto_refresh', 'refresh_interval_hours', 'super_refresh_interval_hours', 'fail_threshold', 'reload_interval_sec'] },
    { title: '冷却策略', keys: ['cooldown_error_requests', 'cooldown_429_quota_sec', 'cooldown_429_empty_sec'] },
    { title: '保存策略', keys: ['save_delay_ms'] }
  ],
  cache: [
    { title: '缓存阈值', keys: ['enable_auto_clean', 'limit_mb'] }
  ],
  retry: [
    { title: '重试控制', keys: ['max_retry', 'retry_status_codes', 'reset_session_status_codes'] },
    { title: '退避参数', keys: ['retry_backoff_base', 'retry_backoff_factor', 'retry_backoff_max', 'retry_budget'] }
  ],
  conversation: [
    { title: '会话生命周期', keys: ['ttl_seconds', 'max_per_token', 'cleanup_interval_sec'] },
    { title: '持久化策略', keys: ['save_delay_ms'] }
  ],
  stats: [
    { title: '统计留存', keys: ['hourly_keep', 'daily_keep', 'save_delay_ms'] }
  ],
  logs: [
    { title: '日志留存', keys: ['max_len', 'save_delay_ms'] }
  ],
  api_keys: [
    { title: 'API Key 落盘', keys: ['save_delay_ms'] }
  ],
  mcp: [
    { title: 'MCP 服务', keys: ['enabled', 'mount_path', 'api_key'] }
  ]
};

function normalizeTab(tabId) {
  if (typeof tabId !== 'string') return CONFIG_TABS[0].id;
  return TAB_MAP.has(tabId) ? tabId : CONFIG_TABS[0].id;
}

function getSectionsForTab(tabId, sections) {
  const tab = TAB_MAP.get(normalizeTab(tabId));
  if (!tab) return sections;

  const allowed = new Set(tab.sections);
  const filtered = sections.filter((section) => allowed.has(section));

  if (tab.id === 'global') {
    sections.forEach((section) => {
      if (!TAB_COVERED_SECTIONS.has(section) && !filtered.includes(section)) {
        filtered.push(section);
      }
    });
  }

  return filtered;
}

function persistActiveTab() {
  try {
    localStorage.setItem(TAB_STORAGE_KEY, activeTab);
  } catch (_) {
    // ignore storage write errors
  }
}

function applyInputsToConfig(targetConfig) {
  const inputs = document.querySelectorAll('input[data-section], textarea[data-section], select[data-section]');

  inputs.forEach((input) => {
    const section = input.dataset.section;
    const key = input.dataset.key;
    if (!section || !key) return;

    let value = input.value;

    if (input.type === 'checkbox') {
      value = input.checked;
    } else if (input.dataset.type === 'json') {
      try {
        value = JSON.parse(value);
      } catch (_) {
        throw new Error(`无效的 JSON: ${getText(section, key).title}`);
      }
    } else if (key === 'app_key' && value.trim() === '') {
      throw new Error('app_key 不能为空（后台密码）');
    } else if (NUMERIC_FIELDS.has(key)) {
      const trimmed = value.trim();
      if (trimmed !== '') {
        const numeric = Number(trimmed);
        if (!Number.isNaN(numeric)) {
          value = numeric;
        }
      }
    }

    if (!targetConfig[section]) targetConfig[section] = {};
    targetConfig[section][key] = value;
  });

  return targetConfig;
}

function renderTabs(allSections) {
  const tabsContainer = byId('config-tabs');
  if (!tabsContainer) return;

  const available = new Set(allSections);
  tabsContainer.replaceChildren();

  CONFIG_TABS.forEach((tab) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'config-tab-btn';
    button.dataset.tab = tab.id;
    button.setAttribute('role', 'tab');

    const icon = document.createElement('span');
    icon.className = 'config-tab-icon';
    icon.setAttribute('aria-hidden', 'true');
    icon.innerHTML = tab.icon || '';

    const label = document.createElement('span');
    label.className = 'config-tab-label';
    label.textContent = tab.label;

    button.appendChild(icon);
    button.appendChild(label);

    let hasSection = tab.sections.some((section) => available.has(section));
    if (!hasSection && tab.id === 'global') {
      hasSection = allSections.some((section) => !TAB_COVERED_SECTIONS.has(section));
    }

    if (!hasSection) {
      button.disabled = true;
      button.classList.add('disabled');
      button.setAttribute('aria-disabled', 'true');
    }

    const selected = tab.id === activeTab;
    if (selected) {
      button.classList.add('active');
    }
    button.setAttribute('aria-selected', selected ? 'true' : 'false');

    button.addEventListener('click', () => {
      if (button.disabled || tab.id === activeTab) return;

      try {
        applyInputsToConfig(currentConfig);
      } catch (error) {
        showToast(error.message, 'warning');
        return;
      }

      activeTab = tab.id;
      persistActiveTab();
      renderConfig(currentConfig);
    });

    tabsContainer.appendChild(button);
  });
}

function getText(section, key) {
  if (LOCALE_MAP[section] && LOCALE_MAP[section][key]) {
    return LOCALE_MAP[section][key];
  }
  return {
    title: key.replace(/_/g, ' '),
    desc: '暂无说明，请参考配置文档。'
  };
}

function getSectionLabel(section) {
  return (LOCALE_MAP[section] && LOCALE_MAP[section].label) || `${section} 设置`;
}

function sortByOrder(keys, orderMap) {
  if (!orderMap) return keys;
  return keys.sort((a, b) => {
    const ia = orderMap.get(a);
    const ib = orderMap.get(b);
    if (ia !== undefined && ib !== undefined) return ia - ib;
    if (ia !== undefined) return -1;
    if (ib !== undefined) return 1;
    return 0;
  });
}

function buildSectionGroups(section, allKeys) {
  const groups = [];
  const defs = SECTION_GROUPS[section] || [];
  const keySet = new Set(allKeys);
  const used = new Set();

  defs.forEach(def => {
    const keys = (def.keys || []).filter(key => keySet.has(key));
    if (!keys.length) return;
    keys.forEach(key => used.add(key));
    groups.push({ title: def.title || getSectionLabel(section), keys, desc: def.desc || '' });
  });

  const rest = allKeys.filter(key => !used.has(key));
  if (rest.length) {
    const chunkSize = 4;
    for (let i = 0; i < rest.length; i += chunkSize) {
      const chunk = rest.slice(i, i + chunkSize);
      const suffix = rest.length > chunkSize ? ` ${Math.floor(i / chunkSize) + 1}` : '';
      groups.push({ title: `更多设置${suffix}`, keys: chunk, desc: '' });
    }
  }

  if (!groups.length) {
    groups.push({ title: getSectionLabel(section), keys: allKeys, desc: '' });
  }

  return groups;
}

function setInputMeta(input, section, key) {
  input.dataset.section = section;
  input.dataset.key = key;
}

function createOption(value, text, selectedValue) {
  const option = document.createElement('option');
  option.value = value;
  option.text = text;
  if (selectedValue !== undefined && selectedValue === value) option.selected = true;
  return option;
}

function buildBooleanInput(section, key, val) {
  const label = document.createElement('label');
  label.className = 'relative inline-flex items-center cursor-pointer';

  const input = document.createElement('input');
  input.type = 'checkbox';
  input.checked = val;
  input.className = 'sr-only peer';
  setInputMeta(input, section, key);

  const slider = document.createElement('div');
  slider.className = "w-9 h-5 bg-[var(--accents-2)] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-black";

  label.appendChild(input);
  label.appendChild(slider);

  return { input, node: label };
}

function buildSelectInput(section, key, val, options) {
  const input = document.createElement('select');
  input.className = 'geist-input h-[34px]';
  setInputMeta(input, section, key);
  options.forEach(opt => {
    input.appendChild(createOption(opt.val, opt.text, val));
  });
  return { input, node: input };
}

function buildJsonInput(section, key, val) {
  const input = document.createElement('textarea');
  input.className = 'geist-input font-mono text-xs';
  input.rows = 4;
  input.value = JSON.stringify(val, null, 2);
  setInputMeta(input, section, key);
  input.dataset.type = 'json';
  return { input, node: input };
}

function buildTextInput(section, key, val) {
  const input = document.createElement('input');
  input.type = 'text';
  input.className = 'geist-input';
  input.value = val;
  setInputMeta(input, section, key);
  return { input, node: input };
}

function buildSecretInput(section, key, val) {
  const input = document.createElement('input');
  input.type = 'text';
  input.className = 'geist-input flex-1 h-[34px]';
  input.value = val;
  setInputMeta(input, section, key);

  const wrapper = document.createElement('div');
  wrapper.className = 'flex items-center gap-2';

  const genBtn = document.createElement('button');
  genBtn.className = 'config-icon-btn flex-none w-[32px] h-[32px] flex items-center justify-center rounded-md transition-colors';
  genBtn.type = 'button';
  genBtn.title = '生成';
  genBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-3-6.7"/><polyline points="21 3 21 9 15 9"/></svg>`;
  genBtn.onclick = () => {
    input.value = randomKey(16);
  };

  const copyBtn = document.createElement('button');
  copyBtn.className = 'config-icon-btn flex-none w-[32px] h-[32px] flex items-center justify-center rounded-md transition-colors';
  copyBtn.type = 'button';
  copyBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>`;
  copyBtn.onclick = () => copyToClipboard(input.value, copyBtn);

  wrapper.appendChild(input);
  wrapper.appendChild(genBtn);
  wrapper.appendChild(copyBtn);

  return { input, node: wrapper };
}

function randomKey(len) {
  const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  const out = [];
  if (window.crypto && window.crypto.getRandomValues) {
    const buf = new Uint8Array(len);
    window.crypto.getRandomValues(buf);
    for (let i = 0; i < len; i++) {
      out.push(chars[buf[i] % chars.length]);
    }
    return out.join('');
  }
  for (let i = 0; i < len; i++) {
    out.push(chars[Math.floor(Math.random() * chars.length)]);
  }
  return out.join('');
}

async function init() {
  apiKey = await ensureAdminKey();
  if (apiKey === null) return false;

  try {
    activeTab = normalizeTab(localStorage.getItem(TAB_STORAGE_KEY));
  } catch (_) {
    activeTab = CONFIG_TABS[0].id;
  }

  await loadData();
  return true;
}

async function loadData() {
  try {
    const res = await fetch('/v1/admin/config', {
      headers: buildAuthHeaders(apiKey)
    });
    if (res.ok) {
      currentConfig = await res.json();
      renderConfig(currentConfig);
      return true;
    }
    if (res.status === 401) {
      logout();
    }
  } catch (e) {
    showToast('连接失败', 'error');
  }
  return false;
}

function renderConfig(data) {
  const container = byId('config-container');
  if (!container) return;
  container.replaceChildren();

  const allSections = sortByOrder(Object.keys(data), SECTION_ORDER);
  renderTabs(allSections);

  const preferredSections = getSectionsForTab(activeTab, allSections);
  const sections = preferredSections.length ? preferredSections : allSections;
  if (!sections.length) {
    container.innerHTML = '<div class="text-center py-12 text-[var(--accents-4)]">暂无配置项</div>';
    return;
  }

  const fragment = document.createDocumentFragment();
  sections.forEach(section => {
    const items = data[section];
    const localeSection = LOCALE_MAP[section];
    const keyOrder = localeSection ? new Map(Object.keys(localeSection).map((k, i) => [k, i])) : null;
    const allKeys = sortByOrder(Object.keys(items), keyOrder);

    if (!allKeys.length) return;

    const block = document.createElement('section');
    block.className = 'config-block';

    const blockHeader = document.createElement('div');
    blockHeader.className = 'config-block-head';
    blockHeader.innerHTML = `<div class="config-block-title">${getSectionLabel(section)}</div>`;

    if (SECTION_DESCRIPTIONS[section]) {
      const descP = document.createElement('p');
      descP.className = 'config-block-desc';
      descP.textContent = SECTION_DESCRIPTIONS[section];
      blockHeader.appendChild(descP);
    }

    block.appendChild(blockHeader);

    const groups = buildSectionGroups(section, allKeys);
    const grid = document.createElement('div');
    grid.className = 'config-grid';

    groups.forEach(group => {
      const card = document.createElement('div');
      card.className = 'config-section';

      const title = document.createElement('div');
      title.className = 'config-section-title';
      title.textContent = group.title;
      card.appendChild(title);

      if (group.desc) {
        const groupDesc = document.createElement('p');
        groupDesc.className = 'config-section-desc';
        groupDesc.textContent = group.desc;
        card.appendChild(groupDesc);
      }

      const fields = document.createElement('div');
      fields.className = 'config-fields';
      group.keys.forEach(key => {
        fields.appendChild(buildFieldCard(section, key, items[key]));
      });

      if (fields.children.length > 0) {
        card.appendChild(fields);
        grid.appendChild(card);
      }
    });

    if (grid.children.length > 0) {
      block.appendChild(grid);
      fragment.appendChild(block);
    }
  });

  container.appendChild(fragment);
}

function buildFieldCard(section, key, val) {
  const text = getText(section, key);

  const fieldCard = document.createElement('div');
  fieldCard.className = 'config-field';

  // Title
  const titleEl = document.createElement('div');
  titleEl.className = 'config-field-title';
  titleEl.textContent = text.title;
  fieldCard.appendChild(titleEl);

  // Description (Muted) - 只在有描述时显示
  if (text.desc) {
    const descEl = document.createElement('p');
    descEl.className = 'config-field-desc';
    descEl.textContent = text.desc;
    fieldCard.appendChild(descEl);
  }

  // Input Wrapper
  const inputWrapper = document.createElement('div');
  inputWrapper.className = 'config-field-input';

  // Input Logic
  let built;
  if (typeof val === 'boolean') {
    built = buildBooleanInput(section, key, val);
  }
  else if (key === 'image_format') {
    built = buildSelectInput(section, key, val, [
      { val: 'url', text: 'URL' },
      { val: 'base64', text: 'Base64' }
    ]);
  }
  else if (key === 'video_format') {
    built = buildSelectInput(section, key, val, [
      { val: 'html', text: 'HTML' },
      { val: 'url', text: 'URL' }
    ]);
  }
  else if (Array.isArray(val) || typeof val === 'object') {
    built = buildJsonInput(section, key, val);
  }
  else {
    if (key === 'api_key' || key === 'app_key' || key === 'public_key') {
      built = buildSecretInput(section, key, val);
    } else {
      built = buildTextInput(section, key, val);
    }
  }

  if (built) {
    inputWrapper.appendChild(built.node);
  }
  fieldCard.appendChild(inputWrapper);

  if (section === 'app' && key === 'public_enabled') {
    fieldCard.classList.add('has-action');
    const link = document.createElement('a');
    link.href = '/login';
    link.className = 'config-field-action config-icon-btn flex-none w-[32px] h-[32px] flex items-center justify-center rounded-md transition-colors';
    link.title = '功能玩法';
    link.setAttribute('aria-label', '功能玩法');
    link.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17L17 7"/><path d="M7 7h10v10"/></svg>`;
    link.style.display = val ? 'inline-flex' : 'none';
    fieldCard.appendChild(link);
    if (built && built.input) {
      built.input.addEventListener('change', () => {
        link.style.display = built.input.checked ? 'inline-flex' : 'none';
      });
    }
  }

  return fieldCard;
}

async function saveConfig() {
  const btn = byId('save-btn');
  const originalText = btn.innerText;
  btn.disabled = true;
  btn.innerText = '保存中...';

  try {
    const newConfig = typeof structuredClone === 'function'
      ? structuredClone(currentConfig)
      : JSON.parse(JSON.stringify(currentConfig));
    applyInputsToConfig(newConfig);

    const res = await fetch('/v1/admin/config', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...buildAuthHeaders(apiKey)
      },
      body: JSON.stringify(newConfig)
    });

    if (res.ok) {
      currentConfig = newConfig;
      btn.innerText = '成功';
      showToast('配置已保存', 'success');
      setTimeout(() => {
        btn.innerText = originalText;
        btn.style.backgroundColor = '';
      }, 2000);
    } else {
      showToast('保存失败', 'error');
    }
  } catch (e) {
    showToast('错误: ' + e.message, 'error');
  } finally {
    if (btn.innerText === '保存中...') {
      btn.disabled = false;
      btn.innerText = originalText;
    } else {
      btn.disabled = false;
    }
  }
}

async function copyToClipboard(text, btn) {
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);

    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
    btn.style.backgroundColor = '#10b981';
    btn.style.borderColor = '#10b981';
    btn.style.color = '#fff';

    setTimeout(() => {
      btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>`;
      btn.style.backgroundColor = '';
      btn.style.borderColor = '';
      btn.style.color = '';
    }, 2000);
  } catch (err) {
    console.error('Failed to copy', err);
  }
}

window.__adminConfig = {
  saveConfig
};

let configInitStarted = false;
async function initConfigPage() {
  if (configInitStarted) return;
  configInitStarted = true;
  try {
    const ok = await init();
    if (ok === false) {
      configInitStarted = false;
    }
  } catch (e) {
    configInitStarted = false;
    throw e;
  }
}

if (window.__registerAdminPage) {
  window.__registerAdminPage('config', initConfigPage);
} else if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initConfigPage);
} else {
  initConfigPage();
}
})();
