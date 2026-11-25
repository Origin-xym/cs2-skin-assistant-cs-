"""环境自检：解释器、依赖、Redis、目录，一次全过一遍。

用法：
    cd D:\\cs2-skin-assistant\\collector-py
    .venv\\Scripts\\python.exe main.py

全绿说明环境就绪，可以开始写 adapters/buff.py。
"""
from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version

from config import settings

REQUIRED = (
    "httpx",
    "pydantic",
    "tenacity",
    "loguru",
    "orjson",
    "redis",
    "playwright",
    "python-dotenv",
)


def check_python() -> None:
    if sys.version_info < (3, 11):
        raise SystemExit(f"[FAIL] Python 版本过低：{sys.version.split()[0]}，需要 3.11+")
    print(f"[OK]   解释器 {sys.version.split()[0]}   {sys.executable}")


def check_packages() -> None:
    for pkg in REQUIRED:
        try:
            print(f"[OK]   {pkg:<14} {version(pkg)}")
        except PackageNotFoundError:
            raise SystemExit(f"[FAIL] 缺少依赖 {pkg}，先执行 pip install -r requirements.txt")


def check_redis() -> None:
    import redis

    client = redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        socket_connect_timeout=3,
    )
    client.ping()
    print(f"[OK]   Redis {settings.redis_host}:{settings.redis_port}  PING=PONG")


def check_dirs() -> None:
    for path in (settings.data_dir, settings.log_dir):
        path.mkdir(parents=True, exist_ok=True)
        print(f"[OK]   目录 {path}")


def main() -> int:
    print("=== CS2 饰品助手 · 采集侧环境自检 ===\n")
    check_python()
    check_packages()
    check_redis()
    check_dirs()
    print("\n环境就绪。下一步：实现 adapters/base.py 的第一个子类。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
