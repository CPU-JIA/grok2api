# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Grok2API is a FastAPI-based reverse proxy service that provides OpenAI-compatible API endpoints for Grok AI services (chat, image generation/editing, video generation, voice mode). It features token pool management with automatic load balancing, multi-backend storage support, and a comprehensive admin dashboard.

**Tech Stack**: Python 3.13+, FastAPI, curl-cffi, SQLAlchemy, Redis, asyncio

## Development Commands

### Local Development
```bash
# Install dependencies and run
uv sync
uv run main.py

# Run with specific log level
LOG_LEVEL=DEBUG uv run main.py

# Run with custom data directory
DATA_DIR=/custom/path uv run main.py
```

### Docker
```bash
# Build and run with Docker Compose
docker compose up -d

# View logs
docker compose logs -f

# Rebuild after changes
docker compose up -d --build
```

### Code Quality
```bash
# Lint with ruff
uv run ruff check .

# Format with ruff
uv run ruff format .

# Type checking (no mypy configured yet)
```

### Testing
**Note**: No test suite exists yet. Tests should be added using pytest.

## Architecture Overview

### Core Components

**API Layer** (`app/api/v1/`)
- `chat.py` - OpenAI-compatible chat completions endpoint
- `image.py` - Image generation endpoint
- `video.py` - Video generation endpoint (not yet implemented)
- `models.py` - Model listing endpoint
- `files.py` - Media file serving
- `admin_api/` - Admin endpoints (token, config, cache, stats management)
- `public_api/` - Public endpoints (imagine, video, voice)

**Core Services** (`app/core/`)
- `auth.py` - Multi-layer authentication (API keys, app key, sessions)
- `config.py` - Hierarchical configuration with automatic migration
- `storage.py` - Unified storage abstraction (Local/Redis/MySQL/PostgreSQL)
- `logger.py` - Structured JSON logging with loguru
- `exceptions.py` - OpenAI-compatible error responses
- `batch.py` - Batch processing utilities
- `response_middleware.py` - Request/response logging

**Token Management** (`app/services/token/`)
- `manager.py` - Token lifecycle management (40KB, complex state machine)
- `pool.py` - High-performance O(1) token pool with quota-based bucketing
- `scheduler.py` - Automatic token refresh scheduling
- Dual pool system: Basic (80 quota/20h) vs Super (140 quota/2h)
- Effort-based consumption: LOW=1, HIGH=4
- Automatic cooldown management (time-based + request-based)

**Grok Services** (`app/services/grok/`)
- `services/` - Chat, image, image_edit, video, voice, model orchestration
- `batch_services/` - Batch operations (usage sync, NSFW, assets)
- `utils/` - Retry logic, streaming, caching, download/upload utilities

**Reverse Proxy Layer** (`app/services/reverse/`)
- 20 service files implementing Grok API endpoints
- WebSocket support for image generation
- LiveKit integration for voice mode
- Session management, headers, retry logic, gRPC, Statsig fingerprinting

**Frontend** (`app/static/`)
- `admin/` - Admin dashboard SPA (token, config, cache, stats management)
- `public/` - Public interfaces (chat, imagine, video, voice)
- `common/` - Shared components (auth, batch SSE, header/footer)
- Vanilla JavaScript (no framework), Chart.js for visualization

### Key Architectural Patterns

**Storage Abstraction**
- Unified interface for Local/Redis/MySQL/PostgreSQL backends
- Atomic operations with distributed locking
- Incremental token updates to minimize write amplification
- Delayed saves with configurable intervals (default 500ms)

**Token Pool Design**
- O(1) add/remove/random selection using hash index + bucket structure
- Quota-based bucketing for efficient token selection
- Lazy index rebuilding on structural changes
- Multi-worker synchronization via periodic reloads

**Error Handling**
- OpenAI-compatible error format for API compatibility
- Retry logic with exponential backoff (configurable via `[retry]` section)
- Circuit breaker pattern NOT implemented (potential improvement)
- Upstream errors wrapped in `UpstreamException` with 502 status

**Concurrency Control**
- Semaphores for rate limiting per service (chat, video, image, usage, NSFW)
- Configurable concurrent limits in `config.defaults.toml`
- Batch processing with configurable batch sizes

**Streaming**
- Async generators for memory efficiency
- Three-tier timeout management: first response, idle, total
- SSE format for browser compatibility
- WebSocket support for image generation

## Configuration Management

**Config File**: `data/config.toml` (auto-created from `config.defaults.toml`)

**Important**: In production or behind reverse proxy, set `app.app_url` to the publicly accessible URL, otherwise file links will be incorrect or return 403.

**Key Configuration Sections**:
- `[app]` - Application settings (URLs, keys, formats, feature flags)
- `[proxy]` - Proxy configuration (base URL, asset URL, cf_clearance, browser fingerprint)
- `[retry]` - Retry strategy (max retries, backoff, status codes)
- `[token]` - Token management (refresh intervals, thresholds, cooldowns)
- `[chat/image/video/voice]` - Service-specific timeouts and concurrency
- `[cache]` - Cache management (auto-clean, size limits)
- `[asset]` - Asset operations (upload/download concurrency)
- `[nsfw/usage]` - Batch operation settings

**Configuration Migration**: v2.0 introduced new config structure. Old `[grok]` configs are automatically migrated on startup.

## Storage Backends

**Supported Types** (set via `SERVER_STORAGE_TYPE` env var):
- `local` - TOML/JSON files with fcntl locking (default)
- `redis` - Redis with distributed locks
- `mysql` - MySQL/MariaDB with SQLAlchemy
- `pgsql` - PostgreSQL with SQLAlchemy

**Connection String** (`SERVER_STORAGE_URL`):
- MySQL: `mysql+aiomysql://user:password@host:3306/db`
- PostgreSQL: `postgresql+asyncpg://user:password@host:5432/db`
- Redis: `redis://host:6379/0` or `redis://:password@host:6379/0`

**Data Files** (local storage):
- `data/config.toml` - Runtime configuration
- `data/token.json` - Token pool data
- `data/api_keys.json` - API key registry
- `data/stats.json` - Request statistics
- `data/logs.json` - Audit logs
- `data/conversations.json` - Conversation contexts

## API Endpoints

**OpenAI-Compatible**:
- `POST /v1/chat/completions` - Chat, image gen/edit, video gen (unified endpoint)
- `POST /v1/images/generations` - Image generation
- `POST /v1/images/edits` - Image editing (multipart/form-data)
- `GET /v1/models` - Model listing

**Admin** (requires `app_key` authentication):
- `/v1/admin/tokens` - Token CRUD
- `/v1/admin/config` - Configuration management
- `/v1/admin/cache` - Cache management
- `/v1/admin/stats` - Statistics
- `/v1/admin/keys` - API key management

**Public** (optional authentication):
- `/v1/public/imagine` - Image generation
- `/v1/public/video` - Video generation
- `/v1/public/voice` - Voice mode

**Pages**:
- `/admin` - Admin dashboard (default password: `grok2api`)
- `/` - Public chat interface

## Authentication

**Multi-Layer Auth**:
1. **API Key** - Bearer token in `Authorization` header (optional, set via `app.api_key`)
2. **App Key** - Admin password (default: `grok2api`, **MUST CHANGE IN PRODUCTION**)
3. **Session Cookies** - HMAC-signed tokens with configurable TTL
4. **Public Mode** - Optional unauthenticated access (set `app.public_enabled=true`)

**Security Notes**:
- Default `app_key` is `grok2api` - change immediately in production
- Session secret defaults to `app_key` if not set - use strong random value
- CORS is permissive (`allow_origins=["*"]`) - restrict in production
- No per-IP rate limiting - only per-token

## Models & Quotas

**Available Models**:
- Chat: `grok-3`, `grok-3-mini`, `grok-3-thinking`, `grok-4`, `grok-4-mini`, `grok-4-thinking`, `grok-4-heavy`, `grok-4.1-mini`, `grok-4.1-fast`, `grok-4.1-expert`, `grok-4.1-thinking`, `grok-4.20-beta`
- Image: `grok-imagine-1.0`, `grok-imagine-1.0-edit`
- Video: `grok-imagine-1.0-video`

**Quota Consumption**:
- Most models: 1 quota per request
- Heavy models (`grok-4-heavy`, `grok-4.1-expert`, `grok-4.1-thinking`): 4 quota per request
- Basic accounts: 80 quota / 20 hours
- Super accounts: 140 quota / 2 hours

## Common Development Tasks

### Adding a New API Endpoint
1. Create route handler in `app/api/v1/` or `app/api/v1/admin_api/`
2. Add authentication decorator if needed (`@require_api_key` or `@require_app_key`)
3. Use `TokenManager` to acquire tokens via `manager.acquire_token(effort=...)`
4. Call reverse proxy service in `app/services/reverse/`
5. Handle errors with `AppException` subclasses for OpenAI compatibility
6. Add logging with `logger.info/error` (includes automatic traceID)

### Modifying Token Management Logic
- **Token pool**: `app/services/token/pool.py` (O(1) operations, quota bucketing)
- **Token lifecycle**: `app/services/token/manager.py` (acquire, release, refresh, cooldown)
- **Token models**: `app/services/token/models.py` (status, quota, effort types)
- **Auto-refresh**: `app/services/token/scheduler.py` (background task)

### Adding a New Storage Backend
1. Implement `BaseStorage` interface in `app/core/storage.py`
2. Add connection logic in `get_storage()` factory
3. Implement atomic operations with appropriate locking mechanism
4. Test with multi-worker scenario (`SERVER_WORKERS > 1`)

### Modifying Configuration
1. Update `config.defaults.toml` with new fields
2. Add migration logic in `app/core/config.py` if changing structure
3. Update `ConfigManager.get()` calls in code
4. Document in README.md configuration table

### Adding Frontend Features
- Admin pages: `app/static/admin/pages/` + `app/static/admin/fragments/`
- Public pages: `app/static/public/pages/` + `app/static/public/fragments/`
- Shared components: `app/static/common/js/`
- Use `batch-sse.js` for long-running operations with progress tracking
- Use `admin-auth.js` for session management

## Important Conventions

**Code Style**:
- Use async/await throughout (FastAPI is async-first)
- Type hints with Pydantic models for validation
- Structured logging with loguru (JSON format in production)
- OpenAI-compatible error responses via `AppException` subclasses

**Error Handling**:
- Wrap upstream errors in `UpstreamException` with original status/message
- Use `ValidationException` for 400 errors
- Use `AuthenticationException` for 401 errors
- Always include `traceID` in error responses (auto-added by middleware)

**Concurrency**:
- Use semaphores for rate limiting (see `app/services/grok/services/`)
- Acquire tokens before making requests (`manager.acquire_token()`)
- Always release tokens in `finally` block
- Use `asyncio.gather()` for parallel operations

**Storage Operations**:
- Use `storage.read()` / `storage.write()` for all persistence
- Incremental updates via `storage.update_token_incremental()` for performance
- Delayed saves via `_schedule_save()` pattern to batch writes
- Always use distributed locks for multi-worker scenarios

**Frontend**:
- Vanilla JavaScript (no build step)
- Use `fetch()` with proper error handling
- SSE for streaming responses and batch operations
- Toast notifications for user feedback

## Known Issues & Technical Debt

**Missing Features**:
- No test suite (pytest recommended)
- No health check endpoint (`/health`)
- No Prometheus metrics export
- No database migration system for SQL backends
- No circuit breaker pattern for upstream failures
- No webhook support for async notifications

**Security Concerns**:
- Default `app_key` is weak - enforce change on first run
- CORS is permissive - should restrict in production
- No per-IP rate limiting
- Session secret fallback to `app_key` is weak
- No request signing (HMAC)

**Performance Opportunities**:
- Token selection could use LRU caching for hot tokens
- Delayed saves could lose data on crash - consider WAL
- Batch operations are sequential - could parallelize within batches
- No distributed cache layer (Redis caching not implemented)
- WebSocket connections not pooled

**Code Quality**:
- Some retry logic duplicated across services - extract to utility
- Magic numbers in code - centralize constants
- Incomplete type hints in some files
- Minimal docstrings - add comprehensive API docs
- No configuration hot-reload - requires restart

## Deployment Notes

**Environment Variables**:
- `LOG_LEVEL` - Logging level (DEBUG/INFO/WARNING/ERROR)
- `LOG_FILE_ENABLED` - Enable file logging (default: true)
- `DATA_DIR` - Data directory (default: ./data)
- `SERVER_HOST` - Bind address (default: 0.0.0.0)
- `SERVER_PORT` - Server port (default: 8000)
- `SERVER_WORKERS` - Uvicorn worker count (default: 1)
- `SERVER_STORAGE_TYPE` - Storage backend (local/redis/mysql/pgsql)
- `SERVER_STORAGE_URL` - Storage connection string

**Vercel Deployment**:
- Set `DATA_DIR=/tmp/data` (ephemeral)
- Set `LOG_FILE_ENABLED=false` (no persistent filesystem)
- Use Redis/MySQL/PostgreSQL for persistence

**Render Deployment**:
- Free tier sleeps after 15 minutes
- Restart/redeploy loses data
- Use Redis/MySQL/PostgreSQL for persistence

**Docker**:
- Multi-stage Alpine build for minimal image size
- Uses `uv` for fast dependency installation
- Entrypoint script handles configuration

**Multi-Worker Considerations**:
- Token pool syncs every 30 seconds (configurable via `token.reload_interval_sec`)
- Use Redis/MySQL/PostgreSQL storage for shared state
- Local storage with multiple workers can cause race conditions
- Distributed locks required for consistency

## Troubleshooting

**Token Issues**:
- Check token status in admin dashboard (`/admin/token`)
- Verify token quota and cooldown status
- Check `data/token.json` for token state
- Review logs for token acquisition failures

**Storage Issues**:
- Verify `SERVER_STORAGE_TYPE` and `SERVER_STORAGE_URL`
- Check database connectivity for SQL backends
- Verify Redis connectivity for Redis backend
- Check file permissions for local storage

**Proxy Issues**:
- Set `proxy.base_proxy_url` if behind firewall
- Set `proxy.cf_clearance` if Cloudflare blocks requests
- Adjust `proxy.browser` fingerprint if detection occurs
- Use `proxy.pool_url` for rotating proxies

**Performance Issues**:
- Increase concurrency limits in config (`chat.concurrent`, etc.)
- Increase worker count (`SERVER_WORKERS`)
- Use Redis/PostgreSQL instead of local storage
- Enable cache auto-clean (`cache.enable_auto_clean=true`)

**Authentication Issues**:
- Verify `app.app_key` for admin access
- Verify `app.api_key` for API access
- Check session cookie expiration (`admin_session_ttl_hours`)
- Verify `app.app_url` matches actual deployment URL
