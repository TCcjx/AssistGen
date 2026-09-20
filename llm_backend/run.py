"""服务启动入口。

开发与生产共用本文件，通过环境变量切换行为，无需改代码：

    APP_ENV=dev   python run.py      # 开发：热重载开启、访问日志开启
    python run.py                    # 生产：默认值，热重载关闭

可覆盖的环境变量：
    APP_ENV     dev | prod       默认 prod
    HOST        监听地址          默认 0.0.0.0
    PORT        监听端口          默认 8000
    RELOAD      1/0 强制指定热重载 默认：dev 开，prod 关
    LOG_LEVEL   uvicorn 日志级别   默认：dev=info，prod=error
    WORKERS     进程数            默认 1（原因见下）

关于 WORKERS：智能体用 LangGraph 的 MemorySaver 保存对话断点，断点只存在于
进程内存中，多进程会导致 `/api/langgraph/resume` 找不到断点而失败，因此默认固定为 1。
若确实需要多进程，请把 checkpointer 换成持久化实现
（requirements 里已经带了 langgraph-checkpoint-sqlite）。

建议启动前先跑一次自检：
    python scripts/preflight.py
"""

import os
import sys
from pathlib import Path

# 必须在导入 app.* 之前切好工作目录：配置读取 .env、日志写入 logs/、
# 上传目录、前端静态资源都按「当前工作目录」定位。
os.chdir(Path(__file__).parent)
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn  # noqa: E402

from app.core.logger import get_logger  # noqa: E402

logger = get_logger(service="server")

APP_ENV = os.environ.get("APP_ENV", "prod").strip().lower()
IS_DEV = APP_ENV == "dev"

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "info" if IS_DEV else "error")

_reload_env = os.environ.get("RELOAD")
RELOAD = IS_DEV if _reload_env is None else _reload_env.strip() not in ("0", "false", "False", "")

WORKERS = int(os.environ.get("WORKERS", "1"))
if RELOAD and WORKERS != 1:
    logger.warning("reload 模式与多进程不兼容，已将 WORKERS 强制为 1")
    WORKERS = 1
if WORKERS != 1:
    logger.warning(
        "WORKERS=%d：LangGraph 断点保存在进程内存，多进程会导致 "
        "/api/langgraph/resume 失效；如需多进程请改用持久化 checkpointer。", WORKERS
    )


def start_server() -> None:
    logger.info("Starting server... env=%s host=%s port=%s reload=%s workers=%s",
                APP_ENV, HOST, PORT, RELOAD, WORKERS)
    logger.info("Working directory: %s", os.getcwd())
    if not RELOAD:
        logger.info("热重载已关闭（开发调试可设置 APP_ENV=dev）")

    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        access_log=IS_DEV,
        log_level=LOG_LEVEL,
        reload=RELOAD,
        workers=1 if RELOAD else WORKERS,
    )


if __name__ == "__main__":
    start_server()
