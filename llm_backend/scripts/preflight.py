"""部署前自检脚本（零依赖，未装任何第三方包也能运行）。

用途：在启动服务之前，一次性确认「这台机器是否具备跑起来的所有条件」，
把「部署后才发现跑不起来」变成「部署前就知道缺什么」。

用法：
    python scripts/preflight.py                 # 全量检查（含外部服务连通性）
    python scripts/preflight.py --skip-services # 只做本机检查，不探外部服务
    python scripts/preflight.py --port 9000     # 指定要检查的端口

退出码：0 = 无阻断项（可能有告警）；1 = 存在阻断项，修复后再启动。

检查项：
  A 运行环境    Python 版本、关键第三方包是否已安装
  B 配置文件    .env 是否存在、必填项、密钥强度、模型服务取值
  C 静态资源    前端构建产物及其引用是否自洽
  D 运行目录    logs / uploads 是否可创建可写
  E GraphRAG    配置与索引产物是否在位
  F 外部服务    MySQL / Redis / Neo4j 端口连通性
  G 端口占用    服务监听端口是否空闲
  H 可移植性    是否有「只在原作者机器上成立」的绝对路径／路径写法
  I PDF 索引    MinerU 服务配置与连通性（不装也不影响其他功能）

关于 H：这类问题在本机永远不报错，只有换台机器才炸，所以必须在部署前拦下。
"""

from __future__ import annotations

import argparse
import os
import re
import socket
import sys
import unicodedata
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
ROOT = BACKEND.parent
ENV_FILE = BACKEND / ".env"
ENV_EXAMPLE = ROOT / ".env.example"
DIST = BACKEND / "static" / "dist"

PASS, WARN, FAIL, SKIP = "PASS", "WARN", "FAIL", "SKIP"
_results: list[tuple[str, str, str]] = []


def record(level: str, item: str, detail: str = "") -> None:
    _results.append((level, item, detail))


def _width(text: str) -> int:
    """中日韩全角字符占 2 列，终端对齐要按显示宽度算。"""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in text)


def _pad(text: str, cols: int) -> str:
    return text + " " * max(0, cols - _width(text))


# ---------------------------------------------------------------- A 运行环境
# graphrag==2.1.0 要求 python>=3.10,<3.13；ipython==9.1.0 要求 >=3.11
PY_MIN, PY_MAX = (3, 11), (3, 13)

REQUIRED_PACKAGES = [
    ("fastapi", "Web 框架"),
    ("uvicorn", "ASGI 服务器"),
    ("pydantic", "数据校验"),
    ("pydantic_settings", "配置加载"),
    ("sqlalchemy", "ORM"),
    ("aiomysql", "MySQL 异步驱动"),
    ("aiosqlite", "SQLite 异步驱动（langgraph checkpoint）"),
    ("loguru", "日志"),
    ("openai", "模型调用"),
    ("httpx", "HTTP 客户端"),
    ("aiohttp", "异步 HTTP"),
    ("requests", "同步 HTTP"),
    ("redis", "缓存"),
    ("jose", "JWT"),
    ("passlib", "口令哈希"),
    ("bcrypt", "bcrypt 后端"),
    ("multipart", "文件上传解析（python-multipart）"),
    ("dotenv", "环境变量加载"),
    ("yaml", "YAML 解析"),
    ("numpy", "数值计算"),
    ("faiss", "向量检索（faiss-cpu）"),
    ("sentence_transformers", "向量模型（会连带安装 torch，体积大）"),
    ("PyPDF2", "PDF 解析"),
    ("langchain", "LangChain 元包"),
    ("langchain_core", "LangChain 核心"),
    ("langchain_community", "LangChain 社区组件"),
    ("langchain_deepseek", "DeepSeek 接入"),
    ("langchain_ollama", "Ollama 接入"),
    ("langchain_neo4j", "Neo4j 接入"),
    ("langgraph", "智能体编排"),
    ("neo4j", "Neo4j 驱动"),
]


def check_python_version() -> bool:
    v = sys.version_info[:2]
    text = "%d.%d.%d" % sys.version_info[:3]
    if PY_MIN <= v < PY_MAX:
        record(PASS, "Python 版本", text)
        return True
    record(
        FAIL,
        "Python 版本",
        "%s 不可用：需 %d.%d ~ %d.%d（graphrag 要求 <3.13，ipython 要求 >=3.11）"
        % (text, PY_MIN[0], PY_MIN[1], PY_MAX[0], PY_MAX[1] - 1),
    )
    return False


def check_packages() -> None:
    """用 find_spec 检测包是否已安装，不真正导入（避免加载 torch 等重型库）。"""
    import importlib.util

    missing = []
    for mod, desc in REQUIRED_PACKAGES:
        try:
            found = importlib.util.find_spec(mod) is not None
        except (ImportError, ValueError):
            found = False
        if not found:
            missing.append("%s (%s)" % (mod, desc))
    if not missing:
        record(PASS, "第三方依赖", "%d 个关键包均已安装" % len(REQUIRED_PACKAGES))
    else:
        record(
            FAIL,
            "第三方依赖",
            "缺少 %d 个：%s\n         → 执行 pip install -r requirements.txt"
            % (len(missing), "、".join(missing[:8]) + ("…" if len(missing) > 8 else "")),
        )


# ---------------------------------------------------------------- B 配置文件
REQUIRED_ENV = [
    "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL",
    "VISION_API_KEY", "VISION_BASE_URL", "VISION_MODEL",
    "OLLAMA_BASE_URL", "OLLAMA_CHAT_MODEL", "OLLAMA_REASON_MODEL",
    "OLLAMA_AGENT_MODEL", "OLLAMA_EMBEDDING_MODEL",
    "SERPAPI_KEY",
    "DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME",
    "REDIS_HOST", "REDIS_PORT",
]
PLACEHOLDER_HINTS = ("sk-xxx", "sk-xxxx", "xxxxx", "your-", "changeme")


def parse_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if not ENV_FILE.is_file():
        return env
    for line in ENV_FILE.read_text("utf-8", errors="ignore").splitlines():
        line = line.split("#")[0] if not line.strip().startswith("#") else ""
        m = re.match(r"^\s*([A-Za-z0-9_]+)\s*=\s*(.*)$", line)
        if m:
            env[m.group(1)] = m.group(2).strip()
    return env


def check_env() -> dict[str, str]:
    if not ENV_FILE.is_file():
        record(
            FAIL,
            "配置文件",
            "缺少 %s → 由 .env.example 复制一份并填入真实值" % ENV_FILE.relative_to(ROOT),
        )
        return {}

    env = parse_env()
    missing = [k for k in REQUIRED_ENV if not env.get(k)]
    if missing:
        record(FAIL, "配置必填项", "缺少 %d 项：%s" % (len(missing), "、".join(missing[:8])))
    else:
        record(PASS, "配置必填项", "%d 项齐全" % len(REQUIRED_ENV))

    secret = env.get("SECRET_KEY", "")
    if not secret or secret in ("your-secret-key", "your-random-secret-key"):
        record(FAIL, "JWT 密钥", "SECRET_KEY 为空或仍是默认值，任何人都能伪造登录令牌")
    elif len(secret) < 32:
        record(WARN, "JWT 密钥", "长度仅 %d，建议至少 32 位随机字符串" % len(secret))
    else:
        record(PASS, "JWT 密钥", "已设置（长度 %d）" % len(secret))

    ph = [
        k for k in ("DEEPSEEK_API_KEY", "VISION_API_KEY", "SERPAPI_KEY")
        if any(h in (env.get(k) or "").lower() for h in PLACEHOLDER_HINTS)
    ]
    if ph:
        record(WARN, "占位 Key", "%s 仍是占位值，对应功能不可用" % "、".join(ph))
    else:
        record(PASS, "占位 Key", "未发现占位值")

    for key in ("CHAT_SERVICE", "REASON_SERVICE", "AGENT_SERVICE"):
        val = (env.get(key) or "").lower()
        if val and val not in ("deepseek", "ollama"):
            record(WARN, "模型服务取值", "%s=%s 非法（应为 deepseek 或 ollama）" % (key, val))
    return env


# ---------------------------------------------------------------- C 静态资源
def check_static() -> None:
    index = DIST / "index.html"
    if not index.is_file():
        record(
            FAIL,
            "前端构建产物",
            "缺少 %s → 执行 cd llm_frontend && npm install && npm run build"
            % index.relative_to(ROOT),
        )
        return
    html = index.read_text("utf-8", errors="ignore")
    missing = []
    for ref in re.findall(r'(?:src|href)="([^"]+)"', html):
        if ref.startswith(("http://", "https://", "data:")):
            continue
        if not (DIST / ref.lstrip("/")).is_file():
            missing.append(ref)
    if missing:
        record(FAIL, "前端构建产物", "index.html 引用的资源缺失：%s（页面会白屏）" % missing)
    else:
        n = sum(len(f) for _, _, f in os.walk(DIST))
        record(PASS, "前端构建产物", "%d 个文件，引用自洽" % n)


# ---------------------------------------------------------------- D 运行目录
def check_runtime_dirs() -> None:
    for name in ("logs", "uploads", "uploads/images"):
        d = BACKEND / name
        try:
            d.mkdir(parents=True, exist_ok=True)
            probe = d / ".preflight_write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except Exception as e:
            record(FAIL, "运行目录", "%s 不可写：%s" % (name, e))
        else:
            record(PASS, "运行目录", "%s 可写" % name)


# ---------------------------------------------------------------- E GraphRAG
def check_graphrag() -> None:
    g = BACKEND / "app" / "graphrag"
    settings = g / "data" / "settings.yaml"
    if not settings.is_file():
        settings = g / "settings.yaml"
    record(PASS if settings.is_file() else WARN, "GraphRAG 配置",
           str(settings.relative_to(ROOT)) if settings.is_file() else "未找到 settings.yaml")
    idx = g / "data" / "output" / "lancedb"
    if idx.is_dir() and any(idx.iterdir()):
        record(PASS, "GraphRAG 索引", "已存在（%d 项），电商问答可直接使用" % len(list(idx.iterdir())))
    else:
        record(WARN, "GraphRAG 索引", "未找到索引产物，图谱问答需先重建索引")


# ---------------------------------------------------------------- F 外部服务
def tcp_probe(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False


def check_services(env: dict[str, str]) -> None:
    targets = [
        ("MySQL", env.get("DB_HOST", "localhost"), env.get("DB_PORT", "3306"), True),
        ("Redis", env.get("REDIS_HOST", "localhost"), env.get("REDIS_PORT", "6379"), False),
    ]
    neo4j_url = env.get("NEO4J_URL", "bolt://localhost:7687")
    m = re.search(r"//([^:/]+):(\d+)", neo4j_url)
    if m:
        targets.append(("Neo4j", m.group(1), m.group(2), False))

    env_importable = _pkg("dotenv")
    if not env_importable:
        record(SKIP, "外部服务", "python-dotenv 未安装，跳过（安装依赖后重跑本项）")
        return

    for name, host, port, required in targets:
        ok = tcp_probe(host, port)
        if ok:
            record(PASS, "%s 连通性" % name, "%s:%s 可达" % (host, port))
        elif required:
            record(FAIL, "%s 连通性" % name, "%s:%s 不可达 → 必须先启动 MySQL 并建库" % (host, port))
        else:
            record(WARN, "%s 连通性" % name,
                   "%s:%s 不可达 → 相关功能不可用，服务本身仍可启动" % (host, port))


def _pkg(mod: str) -> bool:
    import importlib.util
    try:
        return importlib.util.find_spec(mod) is not None
    except (ImportError, ValueError):
        return False


# ---------------------------------------------------------------- G 端口占用
def check_port(port: int) -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("127.0.0.1", port))
    except OSError:
        record(WARN, "监听端口", "%d 已被占用（若服务已在运行可忽略）" % port)
    else:
        record(PASS, "监听端口", "%d 空闲" % port)
    finally:
        s.close()


# ---------------------------------------------------------------- H 可移植性
# 命中这些模式说明代码里写死了某台机器的路径，换机后必然失败。
# 只匹配「用户目录级」的具体路径，避免误伤 /tmp、C:\Windows 这类通用写法。
PORTABILITY_PATTERNS = [
    (re.compile(r"[A-Za-z]:\\+Users\\+[^\\\"'\s]+"), "Windows 用户目录"),
    (re.compile(r"/Users/[A-Za-z][^/\"'\s]*"), "macOS 用户目录"),
    (re.compile(r"/home/(?!\[)[A-Za-z0-9_][^/\"'\s]*"), "Linux 家目录"),
]
SCAN_EXT = {".py", ".yaml", ".yml", ".json", ".toml", ".cfg", ".ini", ".env", ".example"}
# 缓存与索引产物是内容寻址的二进制/半结构化数据，扫描只会产生误报
SCAN_SKIP_DIRS = {"node_modules", "__pycache__", ".git", ".venv", "venv",
                  "static", "dist", "cache", "output", ".workbuddy"}
# 这些 YAML 键是路径，值里出现反斜杠在 Linux 上会被当成文件名的一部分
PATH_LIKE_KEYS = ("db_uri", "base_dir", "local_output_dir", "mineru_output_dir")


def check_portability() -> None:
    """扫描项目自有文件，找出换机后会失效的绝对路径与跨平台路径写法。"""
    abs_hits: list[str] = []
    slash_hits: list[str] = []
    scanned = 0

    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SCAN_SKIP_DIRS]
        for name in files:
            p = Path(root) / name
            suffix = p.suffix.lower()
            if suffix not in SCAN_EXT and name not in (".env", ".env.example"):
                continue
            try:
                text = p.read_text("utf-8", errors="ignore")
            except OSError:
                continue
            scanned += 1
            rel = str(p.relative_to(ROOT))
            for lineno, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                for pat, label in PORTABILITY_PATTERNS:
                    m = pat.search(line)
                    if m:
                        # 注释里的用法示例同样会被使用者照抄，一并提示
                        abs_hits.append("%s:%d [%s] %s" % (rel, lineno, label, m.group(0)[:60]))
                for key in PATH_LIKE_KEYS:
                    if re.match(r"^\s*%s\s*:" % key, line) and "\\" in line:
                        slash_hits.append("%s:%d %s" % (rel, lineno, stripped[:70]))

    if not abs_hits:
        record(PASS, "可移植性", "扫描 %d 个文件，无机器相关绝对路径" % scanned)
    else:
        detail = "发现 %d 处机器相关绝对路径（换机后会失效）：\n         %s" % (
            len(abs_hits), "\n         ".join(abs_hits[:4]))
        if len(abs_hits) > 4:
            detail += "\n         … 另有 %d 处" % (len(abs_hits) - 4)
        record(WARN, "可移植性", detail)

    if slash_hits:
        record(WARN, "路径写法", "路径类配置出现反斜杠，Linux 下会被当成文件名：\n         %s"
               % "\n         ".join(slash_hits[:4]))
    else:
        record(PASS, "路径写法", "路径类配置均使用正斜杠")


# ---------------------------------------------------------------- I PDF 索引
DEFAULT_MINERU = "http://127.0.0.1:8081/"
PRIVATE_NET = re.compile(
    r"^https?://(?:10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.|127\.|localhost)")


def read_mineru_config(env: dict[str, str]) -> str:
    """取当前生效的 MinerU 地址：环境变量优先，其次 settings_pdf.yaml。"""
    url = (env.get("MINERU_API_URL") or "").strip()
    if url:
        return url
    cfg = BACKEND / "app" / "graphrag" / "data" / "settings_pdf.yaml"
    if cfg.is_file():
        m = re.search(r"^\s*mineru_api_url\s*:\s*[\"']?([^\"'\n#]+)", cfg.read_text(
            "utf-8", errors="ignore"), re.M)
        if m:
            return m.group(1).strip()
    return ""


def check_mineru(env: dict[str, str], skip_probe: bool) -> None:
    """PDF 走 GraphRAG 建索引需要外部 MinerU；不装只影响这一条链路。"""
    url = read_mineru_config(env)
    if not url:
        record(WARN, "PDF 索引(MinerU)", "未配置 mineru_api_url → 上传 PDF 建图谱索引不可用")
        return
    m = re.match(r"^https?://([^:/]+):(\d+)", url)
    if not m:
        record(WARN, "PDF 索引(MinerU)", "地址格式无法解析：%s" % url)
        return

    host, port = m.group(1), m.group(2)
    if skip_probe:
        record(SKIP, "PDF 索引(MinerU)", "%s（按 --skip-services 跳过探测）" % url)
        return

    if tcp_probe(host, port, timeout=2.0):
        record(PASS, "PDF 索引(MinerU)", "%s 可达" % url)
        return

    hint = ""
    if PRIVATE_NET.match(url):
        hint = "（当前是回环/内网地址，确认 MinerU 就部署在这台机器上）"
    record(WARN, "PDF 索引(MinerU)",
           "%s 不可达%s → 上传 PDF 建索引会失败；不部署 MinerU 时改用文本/CSV 输入即可" % (url, hint))


# ---------------------------------------------------------------- 主流程
def main() -> int:
    parser = argparse.ArgumentParser(description="AssistGen 部署前自检")
    parser.add_argument("--skip-services", action="store_true", help="跳过外部服务连通性探测")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)),
                        help="要检查的监听端口，默认 8000")
    args = parser.parse_args()

    print("=" * 68)
    print("AssistGen 部署前自检")
    print("项目目录: %s" % ROOT)
    print("=" * 68)

    check_python_version()
    check_packages()
    env = check_env()
    check_static()
    check_runtime_dirs()
    check_graphrag()
    check_portability()
    check_mineru(env, args.skip_services)
    if not args.skip_services:
        check_services(env)
    else:
        record(SKIP, "外部服务", "按 --skip-services 跳过")
    check_port(args.port)

    order = {FAIL: 0, WARN: 1, PASS: 2, SKIP: 3}
    for level, item, detail in sorted(_results, key=lambda r: order[r[0]]):
        print("[%s] %s %s" % (level, _pad(item, 18), detail))

    n_fail = sum(1 for r in _results if r[0] == FAIL)
    n_warn = sum(1 for r in _results if r[0] == WARN)
    print("-" * 68)
    print("结果: %d 项通过, %d 项告警, %d 项阻断" % (
        sum(1 for r in _results if r[0] == PASS), n_warn, n_fail))
    if n_fail:
        print("→ 存在阻断项，请在启动服务前修复。")
    elif n_warn:
        print("→ 无阻断项，可以启动；告警项表示部分功能不可用，按需处理。")
    else:
        print("→ 全部通过，可以直接启动服务：python run.py")
    print("=" * 68)
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
