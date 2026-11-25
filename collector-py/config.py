"""采集侧配置：统一从 .env 读取，没有就退回本机开发默认值。

集中在这里的好处是：后面加平台密钥、改轮询周期只动一处，
适配器里永远不出现硬编码的连接串。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    redis_host: str
    redis_port: int
    redis_db: int
    stream_key: str
    poll_interval: int
    request_timeout: float
    log_level: str
    snapshot_retention_days: int
    data_dir: Path
    log_dir: Path


def load_settings() -> Settings:
    return Settings(
        redis_host=os.getenv("REDIS_HOST", "127.0.0.1"),
        redis_port=int(os.getenv("REDIS_PORT", "6379")),
        redis_db=int(os.getenv("REDIS_DB", "0")),
        stream_key=os.getenv("STREAM_KEY", "cs2:listings"),
        poll_interval=int(os.getenv("POLL_INTERVAL", "60")),
        request_timeout=float(os.getenv("REQUEST_TIMEOUT", "15")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        snapshot_retention_days=int(os.getenv("SNAPSHOT_RETENTION_DAYS", "30")),
        data_dir=BASE_DIR / "data",
        log_dir=BASE_DIR / "logs",
    )


settings = load_settings()
