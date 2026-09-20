"""数据库建表脚本。

默认行为：只创建“缺失的表”（create_all），不会改动或删除任何已有数据。
需要清空重建时，必须显式加 --reset，并再次确认（或用 --yes 跳过询问）。

用法：
    python scripts/init_db.py                  # 幂等建表，安全
    python scripts/init_db.py --reset          # 清空并重建（会丢失数据，需输入 yes 确认）
    python scripts/init_db.py --reset --yes    # 清空并重建，跳过交互确认（仅限脚本化场景）
"""

import argparse
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 PYTHONPATH
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

from app.core.database import engine, Base  # noqa: E402
from app.models import User, Conversation, Message  # noqa: E402,F401  仅用于注册模型元数据
from app.core.logger import get_logger  # noqa: E402

logger = get_logger(service="init_db")


async def init_db(reset: bool = False) -> None:
    """建表。reset=True 时先删除全部表，会清空数据。"""
    async with engine.begin() as conn:
        if reset:
            logger.warning("--reset 已启用：正在删除现有表（数据将全部丢失）")
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="初始化 AssistGen 数据库表结构")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="删除所有表后重建（会清空 users / conversations / messages 全部数据）",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="与 --reset 搭配使用，跳过交互式确认",
    )
    return parser.parse_args()


def confirm_reset() -> bool:
    prompt = (
        "\n[危险] 该操作会删除 users / conversations / messages 的全部数据，且不可恢复。\n"
        "确认请输入 yes（其他任意输入均视为取消）："
    )
    try:
        answer = input(prompt)
    except EOFError:  # 非交互环境
        logger.error("当前环境无法读取确认输入，如确定要清空请改用 --reset --yes")
        return False
    return answer.strip().lower() == "yes"


def main() -> int:
    args = parse_args()

    if args.reset and not args.yes and not confirm_reset():
        logger.info("已取消，数据库未被修改")
        return 0

    try:
        logger.info("Initializing database..." + (" (reset)" if args.reset else ""))
        asyncio.run(init_db(reset=args.reset))
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        return 1

    logger.info("Database initialization completed successfully!")
    return 0


if __name__ == "__main__":
    # 用退出码反映真实结果，避免脚本失败却被上游当成成功
    raise SystemExit(main())
