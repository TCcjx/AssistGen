"""接口契约与工程规范回归测试（不依赖任何第三方包，也无需启动服务）。

覆盖内容：
1. 前端调用的每个接口路径，后端都有对应路由；
2. 前端构建产物存在，且 .env.example 不含真实凭据、已声明 SECRET_KEY；
3. 项目自有代码的 Python 包结构完整（目录内含 .py 就必须有 __init__.py）。

运行方式（二选一）：
    python tests/test_contract.py
    pytest tests/
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "llm_backend"
FRONTEND = ROOT / "llm_frontend"
FRONTEND_SRC = FRONTEND / "src"

# 内嵌的上游完整源码，包结构由上游仓库决定，不在本项目的检查范围内
VENDOR_DIRS = (
    BACKEND / "app" / "graphrag",
    BACKEND / "app" / "lg_agent" / "kg_sub_graph" / "ps_genai_agents",
)

ROUTE_RE = re.compile(
    r"""@\w+\.(get|post|put|delete|patch|websocket)\(\s*["']([^"']+)""",
    re.IGNORECASE,
)
CALL_RE = re.compile(r"""['"`](/(?:api|chat-rag|health)[A-Za-z0-9_\-/${}\.]*)['"`]""")


def _normalize(path: str) -> str:
    """把路径参数统一成通配符：/{id} 与 /${id} 都归一到 /*。"""
    path = re.sub(r"\$\{[^}]*\}", "*", path)
    path = re.sub(r"\{[^}]*\}", "*", path)
    return path.rstrip("/") or "/"


def collect_backend_routes() -> set[str]:
    """扫描后端源码中的路由装饰器，返回归一化后的完整路径集合。

    路由在两层组装：app/api/__init__.py 把 auth 子路由挂到 api_router，
    main.py 再把 api_router 挂到统一前缀（当前为 /api）下。
    """
    main_src = (BACKEND / "main.py").read_text("utf-8")
    api_init_src = (BACKEND / "app" / "api" / "__init__.py").read_text("utf-8")

    routes = {_normalize(p) for _, p in ROUTE_RE.findall(main_src)}

    mount = re.search(
        r"""include_router\(\s*api_router\s*,\s*prefix\s*=\s*["']([^"']*)["']""", main_src
    )
    sub = re.search(
        r"""include_router\(\s*auth_router\s*(?:,\s*prefix\s*=\s*["']([^"']*)["'])?""",
        api_init_src,
    )
    assert mount, "未能在 main.py 中找到 api_router 的挂载前缀，测试需要同步更新"
    prefix = mount.group(1) + ((sub.group(1) or "") if sub else "")

    auth_src = (BACKEND / "app" / "api" / "auth.py").read_text("utf-8")
    routes.update(_normalize(prefix + p) for _, p in ROUTE_RE.findall(auth_src))
    return routes


def collect_frontend_calls() -> set[str]:
    """扫描前端源码中出现的接口路径。"""
    calls: set[str] = set()
    for f in FRONTEND_SRC.rglob("*"):
        if f.suffix in (".ts", ".vue") and f.is_file():
            calls.update(_normalize(p) for p in CALL_RE.findall(f.read_text("utf-8")))
    return calls


def has_missing_route(front_path: str, backend_routes: set[str]) -> bool:
    """前端路径能否被后端某条路由承接。"""
    if front_path in backend_routes:
        return False
    # 前端可能把带参路径拼成前缀，例如 /api/conversations/*/messages
    for route in backend_routes:
        if route.count("*") != front_path.count("*"):
            continue
        if re.fullmatch(route.replace("*", "[^/]+"), front_path):
            return False
    return True


def test_frontend_calls_have_backend_routes() -> None:
    backend = collect_backend_routes()
    assert backend, "未能解析出任何后端路由，检查 ROUTE_RE 是否失效"

    missing = sorted(p for p in collect_frontend_calls() if has_missing_route(p, backend))
    assert not missing, f"以下前端接口在后端找不到实现：{missing}"


def test_frontend_build_artifacts_exist() -> None:
    dist = BACKEND / "static" / "dist"
    assert (dist / "index.html").is_file(), f"缺少前端构建产物：{dist / 'index.html'}"
    assert list((dist / "assets").glob("*.js")), "构建产物缺少 js 资源"


def test_env_example_has_no_real_credentials() -> None:
    text = (ROOT / ".env.example").read_text("utf-8")
    for key in ("DB_PASSWORD", "NEO4J_PASSWORD", "SECRET_KEY", "DEEPSEEK_API_KEY", "SERPAPI_KEY"):
        m = re.search(rf"^\s*{key}\s*=\s*(.*)$", text, re.M)
        assert m, f".env.example 缺少 {key}"
        value = m.group(1).strip()
        assert value, f".env.example 中 {key} 为空，应写占位符"
        looks_like_placeholder = ("your-" in value) or ("xxx" in value.lower())
        assert looks_like_placeholder, (
            f".env.example 中 {key} 疑似真实凭据（{value!r}），模板文件只能写占位符"
        )


def test_own_packages_have_init() -> None:
    """项目自有代码中，目录内有 .py 就必须有 __init__.py。"""
    missing: list[str] = []
    for d in (BACKEND / "app").rglob("*"):
        if not d.is_dir() or "__pycache__" in d.parts:
            continue
        if any(str(d).startswith(str(v)) for v in VENDOR_DIRS):
            continue
        if not any(f.suffix == ".py" for f in d.iterdir() if f.is_file()):
            continue
        if not (d / "__init__.py").is_file():
            missing.append(str(d.relative_to(ROOT)).replace("\\", "/"))
    assert not missing, f"以下包缺少 __init__.py：{sorted(missing)}"


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in tests:
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {fn.__name__}\n      {e}")
        except Exception as e:  # 解析异常等
            failed += 1
            print(f"ERROR {fn.__name__}\n      {type(e).__name__}: {e}")
        else:
            print(f"PASS  {fn.__name__}")
    print(f"\n{len(tests) - failed}/{len(tests)} 项通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run())
