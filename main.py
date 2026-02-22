"""
Grok2API 应用入口

FastAPI 应用初始化和路由注册
"""

from contextlib import asynccontextmanager
import os
import platform
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
APP_DIR = BASE_DIR / "app"

# Ensure the project root is on sys.path (helps when Vercel sets a different CWD)
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

env_file = BASE_DIR / ".env"
if env_file.exists():
    load_dotenv(env_file)

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi import Depends  # noqa: E402

from app.core.auth import verify_api_key  # noqa: E402
from app.core.config import get_config  # noqa: E402
from app.core.logger import logger, setup_logging  # noqa: E402
from app.core.exceptions import register_exception_handlers  # noqa: E402
from app.core.response_middleware import ResponseLoggerMiddleware  # noqa: E402
from app.api.v1.chat import router as chat_router  # noqa: E402
from app.api.v1.image import router as image_router  # noqa: E402
from app.api.v1.files import router as files_router  # noqa: E402
from app.api.v1.models import router as models_router  # noqa: E402
from app.services.token import get_scheduler  # noqa: E402
from app.services.mcp import create_mcp_http_app  # noqa: E402
from app.api.v1.admin_api import router as admin_router  # noqa: E402
from app.api.v1.public_api import router as public_router  # noqa: E402
from app.api.pages import router as pages_router  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

# 初始化日志
setup_logging(
    level=os.getenv("LOG_LEVEL", "INFO"), json_console=False, file_logging=True
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 1. 注册服务默认配置
    from app.core.config import config, register_defaults
    from app.services.grok.defaults import get_grok_defaults

    register_defaults(get_grok_defaults())

    # 2. 加载配置
    await config.load()

    # 2.1 安全检查：强制修改默认密钥
    app_key = get_config("app.app_key", "")
    if app_key == "grok2api":
        logger.error("=" * 80)
        logger.error("CRITICAL SECURITY ERROR: Default app_key detected!")
        logger.error("The default app_key 'grok2api' is insecure and MUST be changed.")
        logger.error(
            "Please set a strong app_key in your config.toml or environment variables."
        )
        logger.error("=" * 80)
        sys.exit(1)

    # 2.2 安全检查：session_secret 必须配置
    session_secret = get_config("app.session_secret", "")
    if not session_secret:
        logger.error("=" * 80)
        logger.error("CRITICAL SECURITY ERROR: session_secret not configured!")
        logger.error("Please set a strong session_secret in your config.toml.")
        logger.error("=" * 80)
        sys.exit(1)

    # 3. 启动服务显示
    logger.info("Starting Grok2API...")
    logger.info(f"Platform: {platform.system()} {platform.release()}")
    logger.info(f"Python: {sys.version.split()[0]}")

    # 3.1 初始化管理服务
    from app.services.api_keys import api_key_manager
    from app.services.request_stats import request_stats
    from app.services.request_logger import request_logger
    from app.services.conversation_manager import conversation_manager
    from app.services.proxy_pool import proxy_pool

    await api_key_manager.init()
    await request_stats.init()
    await request_logger.init()
    await conversation_manager.init()
    await proxy_pool.start()

    # 3.2 初始化 MCP 子应用生命周期
    mcp_lifespan_ctx = None
    mcp_http_app = getattr(app.state, "mcp_http_app", None)
    if mcp_http_app is not None and hasattr(mcp_http_app, "lifespan"):
        try:
            mcp_lifespan_ctx = mcp_http_app.lifespan(app)
            await mcp_lifespan_ctx.__aenter__()
            app.state.mcp_lifespan_ctx = mcp_lifespan_ctx
            logger.info("MCP streamable-http initialized")
        except Exception as e:
            logger.warning(f"MCP lifespan startup skipped: {e}")

    # 4. 启动 Token 刷新调度器
    refresh_enabled = get_config("token.auto_refresh", True)
    if refresh_enabled:
        basic_interval = get_config("token.refresh_interval_hours", 8)
        super_interval = get_config("token.super_refresh_interval_hours", 2)
        interval = min(basic_interval, super_interval)
        scheduler = get_scheduler(interval)
        scheduler.start()

    logger.info("Application startup complete.")
    yield

    # 关闭
    logger.info("Shutting down Grok2API...")

    from app.core.storage import StorageFactory
    from app.services.api_keys import api_key_manager
    from app.services.request_stats import request_stats
    from app.services.request_logger import request_logger
    from app.services.conversation_manager import conversation_manager
    from app.services.proxy_pool import proxy_pool

    try:
        await api_key_manager.flush()
        await request_stats.flush()
        await request_logger.flush()
        await conversation_manager.shutdown()
        await proxy_pool.stop()
    except Exception:
        pass

    mcp_lifespan_ctx = getattr(app.state, "mcp_lifespan_ctx", None)
    if mcp_lifespan_ctx is not None:
        try:
            await mcp_lifespan_ctx.__aexit__(None, None, None)
        except Exception:
            pass

    if StorageFactory._instance:
        await StorageFactory._instance.close()

    if refresh_enabled:
        scheduler = get_scheduler()
        scheduler.stop()


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="Grok2API",
        lifespan=lifespan,
    )

    # CORS 配置
    allowed_origins = get_config("app.allowed_origins", [])
    if not allowed_origins:
        logger.warning(
            "SECURITY WARNING: No allowed_origins configured. "
            "Using permissive defaults for development. "
            "Please configure allowed_origins in production!"
        )
        # 开发环境默认值
        allowed_origins = [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # 请求日志和 ID 中间件
    app.add_middleware(ResponseLoggerMiddleware)

    # 注册异常处理器
    register_exception_handlers(app)

    # 注册路由
    app.include_router(
        chat_router, prefix="/v1", dependencies=[Depends(verify_api_key)]
    )
    app.include_router(
        image_router, prefix="/v1", dependencies=[Depends(verify_api_key)]
    )
    app.include_router(
        models_router, prefix="/v1", dependencies=[Depends(verify_api_key)]
    )
    app.include_router(files_router, prefix="/v1/files")

    # 静态文件服务
    static_dir = APP_DIR / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # 注册管理与公共路由
    app.include_router(admin_router, prefix="/v1/admin")
    app.include_router(public_router, prefix="/v1/public")
    app.include_router(pages_router)

    mcp_http_app = create_mcp_http_app()
    app.state.mcp_http_app = mcp_http_app
    app.state.mcp_lifespan_ctx = None
    if mcp_http_app is not None:
        mount_path = str(get_config("mcp.mount_path", "/mcp") or "/mcp").strip()
        if not mount_path.startswith("/"):
            mount_path = f"/{mount_path}"
        app.mount(mount_path, mcp_http_app, name="mcp")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8000"))
    workers = int(os.getenv("SERVER_WORKERS", "1"))

    # 平台检查
    is_windows = platform.system() == "Windows"

    # 自动降级
    if is_windows and workers > 1:
        logger.warning(
            f"Windows platform detected. Multiple workers ({workers}) is not supported. "
            "Using single worker instead."
        )
        workers = 1

    ws_impl = os.getenv("SERVER_WS_IMPL", "wsproto").strip().lower() or "wsproto"
    if ws_impl not in {"wsproto", "websockets", "websockets-sansio", "none"}:
        logger.warning(f"Invalid SERVER_WS_IMPL={ws_impl}, fallback to wsproto")
        ws_impl = "wsproto"

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=workers,
        log_level=os.getenv("LOG_LEVEL", "INFO").lower(),
        ws=ws_impl,
    )
