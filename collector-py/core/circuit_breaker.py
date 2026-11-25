"""平台级熔断器：三态 + 指数退避。

CLOSED     正常，请求放行
OPEN       熔断中，一律拒绝；冷却期内零重试（重试只会加重风控判定）
HALF_OPEN  冷却到期后的试探窗口：只放一个请求，成功回 CLOSED，失败冷却翻倍

触发条件（任一命中立即 OPEN）：
    429 限流 / 跳验证页 / 登录态失效 / 连续失败达到 failure_threshold
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from enum import Enum


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


FATAL_STATUS_CODES = frozenset({401, 403, 429})


def is_fatal_status(status_code: int) -> bool:
    """401 登录失效、403 被拦、429 被限流，一律按致命处理，不做任何重试。"""
    return status_code in FATAL_STATUS_CODES


class CircuitOpenError(RuntimeError):
    """熔断期内的请求被本地拒绝，不会真的发出去。"""

    def __init__(self, platform: str, retry_after_sec: float, reason: str) -> None:
        self.platform = platform
        self.retry_after_sec = max(0.0, retry_after_sec)
        self.reason = reason
        super().__init__(
            f"[{platform}] 暂不放行，{self.retry_after_sec:.0f}s 后再来；原因：{reason or '冷却/退避中'}"
        )


@dataclass
class CircuitBreaker:
    """一个平台一个实例。纯状态机：不碰网络、不打日志、可单测。"""

    platform: str
    cooldown_sec: float = 900.0          # 首次熔断冷却 15 分钟
    fatal_cooldown_sec: float = 1800.0   # 429/验证页/登录失效：30 分钟
    max_cooldown_sec: float = 3600.0     # 反复失败最长 1 小时
    failure_threshold: int = 5           # 连续失败几次直接熔断
    backoff_sec: tuple[float, ...] = (10.0, 30.0, 120.0)

    def __post_init__(self) -> None:
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._trip_count = 0
        self._cooldown = self.cooldown_sec
        self._open_until = 0.0
        self._next_allowed_at = 0.0
        self._probe_in_flight = False
        self._last_reason = ""
        self._lock = asyncio.Lock()

    # ---- 调用方只用这三个方法 ----

    async def before_request(self) -> None:
        """每个请求发出前必须调用；不允许时抛 CircuitOpenError。"""
        async with self._lock:
            now = time.monotonic()

            if self._state is CircuitState.OPEN:
                if now < self._open_until:
                    raise CircuitOpenError(
                        self.platform, self._open_until - now, self._last_reason
                    )
                # 冷却到期 → 开一个试探窗口
                self._state = CircuitState.HALF_OPEN
                self._probe_in_flight = False

            if self._state is CircuitState.HALF_OPEN:
                if self._probe_in_flight:
                    raise CircuitOpenError(self.platform, 0.0, "试探请求尚未返回")
                self._probe_in_flight = True
                return

            if now < self._next_allowed_at:
                raise CircuitOpenError(
                    self.platform, self._next_allowed_at - now, self._last_reason
                )

    async def record_success(self) -> None:
        """请求成功：恢复健康，冷却时间回到初始值。"""
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failures = 0
            self._trip_count = 0
            self._cooldown = self.cooldown_sec
            self._open_until = 0.0
            self._next_allowed_at = 0.0
            self._probe_in_flight = False
            self._last_reason = ""

    async def record_failure(self, reason: str, *, fatal: bool = False) -> None:
        """请求失败：非致命按 10/30/120s 退避；致命或连续到阈值直接熔断。"""
        async with self._lock:
            self._last_reason = reason
            self._probe_in_flight = False

            if fatal or self._state is CircuitState.HALF_OPEN:
                self._trip(fatal=fatal)
                return

            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._trip(fatal=False)
                return
            delay = self.backoff_sec[min(self._failures - 1, len(self.backoff_sec) - 1)]
            self._next_allowed_at = time.monotonic() + delay

    def _trip(self, *, fatal: bool) -> None:
        """进入 OPEN：首次按配置取冷却，之后每次翻倍，封顶 max_cooldown_sec。"""
        self._state = CircuitState.OPEN
        self._probe_in_flight = False
        self._failures = 0
        self._trip_count += 1
        if self._trip_count == 1:
            self._cooldown = self.fatal_cooldown_sec if fatal else self.cooldown_sec
        else:
            self._cooldown = min(self._cooldown * 2, self.max_cooldown_sec)
        self._open_until = time.monotonic() + self._cooldown
        self._next_allowed_at = 0.0

    @property
    def state(self) -> CircuitState:
        return self._state

    def snapshot(self) -> dict[str, object]:
        """给健康度看板 / 日志用，不改状态。"""
        return {
            "platform": self.platform,
            "state": self._state.value,
            "consecutive_failures": self._failures,
            "trip_count": self._trip_count,
            "cooldown_sec": round(self._cooldown, 1),
            "retry_after_sec": round(max(0.0, self._open_until - time.monotonic()), 1),
            "last_reason": self._last_reason,
        }


if __name__ == "__main__":
    async def _demo() -> None:
        b = CircuitBreaker(
            platform="BUFF",
            cooldown_sec=1.0,
            fatal_cooldown_sec=1.0,
            max_cooldown_sec=4.0,
            failure_threshold=3,
            backoff_sec=(0.0, 0.0, 0.0),
        )

        # 1) 429 致命失败：立即熔断
        await b.record_failure("http 429", fatal=True)
        try:
            await b.before_request()
        except CircuitOpenError as exc:
            print(f"[1] 已熔断：{exc}")
        assert b.state is CircuitState.OPEN

        # 2) 冷却到期 → 试探成功 → 恢复
        await asyncio.sleep(1.1)
        await b.before_request()          # 进入 HALF_OPEN
        assert b.state is CircuitState.HALF_OPEN
        await b.record_success()
        assert b.state is CircuitState.CLOSED
        print("[2] 试探成功，已恢复 CLOSED")

        # 3) 连续非致命失败到阈值 → 熔断
        for i in range(3):
            await b.record_failure(f"timeout #{i + 1}")
        assert b.state is CircuitState.OPEN
        print(f"[3] 连续失败触发熔断：{b.snapshot()}")

        # 4) 试探再失败 → 冷却翻倍
        await asyncio.sleep(1.1)
        await b.before_request()
        await b.record_failure("probe timeout")
        assert b.state is CircuitState.OPEN
        assert b.snapshot()["cooldown_sec"] == 2.0
        print("[4] 试探失败，冷却翻倍到 2s")

    asyncio.run(_demo())
    print("[OK] circuit_breaker 自检通过")
