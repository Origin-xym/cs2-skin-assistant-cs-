"""采集器启动入口：组装依赖，跑单轮或常驻。

用法：
    # 单轮联调（W1 第一步，验证登录态与解析）
    .venv\\Scripts\\python.exe run_collector.py --once

    # 常驻，默认 60s 一轮
    .venv\\Scripts\\python.exe run_collector.py

Ctrl+C 退出，连接会正常关闭。
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from loguru import logger
from redis.asyncio import Redis

from adapters.base import MarketCollector
from adapters.buff import BUFF_BASE, BuffCollector
from adapters.youpin import YOUPIN_BASE, YoupinCollector
from config import settings
from core.credentials import CredentialError, CredentialStore
from core.http_client import PlatformClient
from core.scheduler import CollectorScheduler
from core.snapshot_writer import SnapshotWriter
from core.watchlist import WatchList, WatchListError


def setup_logging() -> None:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level=settings.log_level)
    logger.add(
        settings.log_dir / "collector_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="7 days",
        encoding="utf-8",
        level=settings.log_level,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CS2 饰品采集器")
    parser.add_argument("--once", action="store_true", help="只跑一轮就退出（联调用）")
    parser.add_argument("--interval", type=int, help="覆盖轮询周期（秒），不低于 30")
    return parser.parse_args(argv)

async def main(args: argparse.Namespace) -> int:
    setup_logging()
    logger.info("=== CS2 饰品采集器启动 ===")

    if args.interval is not None and args.interval < 30:
        logger.error("轮询周期不能低于 30 秒")
        return 2

    try:
        watchlist = WatchList()
        store = CredentialStore()
    except WatchListError as exc:
        logger.error(f"监控清单不可用：{exc}")
        return 2
    except CredentialError as exc:
        logger.error(f"登录态存储不可用：{exc}")
        return 2

    try:
        buff_cred = store.load("BUFF")
    except CredentialError as exc:
        logger.error(f"BUFF 登录态解不开，请重新保存：{exc}")
        return 2
    if buff_cred is None:
        logger.error("没有 BUFF 登录态。先运行：save_cookie.py --platform BUFF --cookie '...'")
        return 2
    
    youpin_cred = None
    if watchlist.for_platform("YOUPIN"):
        try:
            youpin_cred = store.load("YOUPIN")
        except CredentialError as exc:
            logger.error(f"YOUPIN 登录态解不开，本轮跳过：{exc}")
        if youpin_cred is None:
            logger.warning("清单有 YOUPIN 标的，但没有可用登录态，本轮跳过该平台")


    logger.info(f"清单 {len(watchlist)} 项（启用 {len(watchlist.enabled_items())} 项）")
    for platform in ("C5"):
        pending = len(watchlist.for_platform(platform))
        if pending:
            logger.warning(f"{platform} 有 {pending} 个标的，但适配器尚未接入，本轮跳过")

    clients: list[PlatformClient] = []
    writer: SnapshotWriter | None = None
    lock_client: Redis | None = None
    try:
        buff_client = PlatformClient(
            platform="BUFF",
            base_url=BUFF_BASE,
            headers={"Referer": "https://buff.163.com/market/csgo"},
            credential=buff_cred,
        )
        clients.append(buff_client)
        collectors: dict[str, MarketCollector] = {"BUFF": BuffCollector(buff_client)}

        if youpin_cred is not None:
            youpin_client = PlatformClient(
                platform="YOUPIN",
                base_url=YOUPIN_BASE,
                credential=youpin_cred,
            )
            clients.append(youpin_client)
            collectors["YOUPIN"] = YoupinCollector(youpin_client)

        logger.info(f"已启用平台：{', '.join(collectors)}")


        writer = SnapshotWriter()

        lock_client = Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )
        await lock_client.ping()
        logger.info(f"Redis {settings.redis_host}:{settings.redis_port} PING=PONG")

        scheduler = CollectorScheduler(
            watchlist,
            collectors,
            writer,
            poll_interval=args.interval,
            lock_client=lock_client,
        )

        if args.once:
            stats = await scheduler.run_once()
            total = {
                key: sum(stat[key] for stat in stats)
                for key in ("written", "skipped", "errors")
            }
            logger.info(
                f"单轮结束：新写 {total['written']}，"
                f"去重 {total['skipped']}，错误 {total['errors']}"
            )
            if total["written"] == 0 and total["errors"] == 0:
                logger.warning("本轮没写入任何快照：检查清单 goods_id、登录态和接口字段")
            return 0

        logger.info(f"常驻模式启动，周期 {args.interval or settings.poll_interval}s")
        await scheduler.run()
        return 0
    finally:
        for client in clients:
            await client.aclose()
        if writer is not None:
            await writer.aclose()
        if lock_client is not None:
            await lock_client.aclose()


def cli() -> int:
    args = parse_args()
    try:
        return asyncio.run(main(args))
    except KeyboardInterrupt:
        print("\n已停止")
        return 0


if __name__ == "__main__":
    raise SystemExit(cli())
