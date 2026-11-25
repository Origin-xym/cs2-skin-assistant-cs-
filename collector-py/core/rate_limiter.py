"""令牌桶限速器 + 并发闸。

对应设计文档 5.2 第 6 条：单平台在途请求 ≤ 2，请求间隔 200–800ms 随机抖动。
用法：
    limiter = RateLimiter()
    async with limiter:
        resp = await client.get(url)

任何绕开 limiter 的裸请求都算违规。
"""
from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass



@dataclass
class RateLimiter:
    """一个平台一个实例，不要跨平台复用。"""

    rate_per_sec: float = 2.0                 # 令牌补充速率（个/秒）
    burst: int = 2                            # 桶容量，允许的瞬时突发
    max_concurrency: int = 2                  # 在途请求上限
    jitter_ms: tuple[int, int] = (200, 800)   # 相邻请求的随机间隔区间

    def __post_init__(self) -> None:
        self._tokens = float(self.burst)
        self._updated_at = time.monotonic()
        self._last_request_at = 0.0
        self._in_flight = 0
        self._lock = asyncio.Lock()
        self._sem = asyncio.Semaphore(self.max_concurrency)

    async def _take_token(self) -> None:
        """取不到令牌就睡到够为止，绝不跳过。"""
        while True:
            async with self._lock:
                now = time.monotonic()
                self._tokens = min(
                    float(self.burst),
                    self._tokens + (now - self._updated_at) * self.rate_per_sec,
                )
                self._updated_at = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait_sec = (1.0 - self._tokens) / self.rate_per_sec
            await asyncio.sleep(wait_sec)

    async def _sleep_jitter(self) -> None:
        """让相邻请求的间隔落在 jitter_ms 区间内。"""
        gap = random.uniform(*self.jitter_ms) / 1000.0
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < gap:
            await asyncio.sleep(gap - elapsed)
        self._last_request_at = time.monotonic()

    async def __aenter__(self) -> "RateLimiter":
        await self._sem.acquire()
        try:
            await self._take_token()
            await self._sleep_jitter()
        except BaseException:
            self._sem.release()          # 中途被取消也要还名额
            raise
        self._in_flight += 1
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self._in_flight -= 1
        self._sem.release()

    @property
    def stats(self) -> dict[str, float]:
        return {
            "rate_per_sec": self.rate_per_sec,
            "tokens": round(self._tokens, 2),
            "in_flight": self._in_flight,
        }


if __name__ == "__main__":
    async def _demo() -> None:
        limiter = RateLimiter(rate_per_sec=2.0, max_concurrency=2, jitter_ms=(100, 300))
        peak = 0

        async def one(i: int) -> int:
            nonlocal peak
            async with limiter:
                peak = max(peak, limiter._in_flight)
                await asyncio.sleep(0.1)      # 模拟一次网络往返
                return i

        started = time.monotonic()
        await asyncio.gather(*(one(i) for i in range(10)))
        cost = time.monotonic() - started
        print(f"10 次请求耗时 {cost:.2f}s，峰值并发 {peak}")
        assert peak <= 2, f"并发超限：{peak}"
        assert 4.0 <= cost <= 7.0, f"限速异常：{cost:.2f}s"

    asyncio.run(_demo())
    print("[OK] rate_limiter 自检通过")
