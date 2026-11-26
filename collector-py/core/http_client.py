"""统一 HTTP 客户端：限速 → 熔断 → 登录态，一个入口。

设计约束（对应设计文档 5.2 / 5.3）：
- 所有请求必须经过 RateLimiter，单平台在途 ≤ 2；
- 429 / 401 / 403 立即熔断，本层不重试；
- Cookie 只在构造和 reload 时从加密文件读，不落日志。

重试策略：失败记到 CircuitBreaker，由调度器下一轮再来。
"""
from __future__ import annotations

from typing import Any

import httpx

from config import settings
from core.circuit_breaker import (
    CircuitState,
    CircuitBreaker,
    CircuitOpenError,
    is_fatal_status,
)
from core.credentials import Credential, CredentialStore
from core.rate_limiter import RateLimiter

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
DEFAULT_VERIFY_MARKERS = ("安全验证", "验证码", "captcha", "verify")



class HttpClientError(RuntimeError):
    """HTTP 层统一异常基类。"""


class HttpRequestError(HttpClientError):
    """网络层失败：超时、连接被重置、DNS 失败等。"""

    def __init__(self, platform: str, detail: str) -> None:
        self.platform = platform
        self.detail = detail
        super().__init__(f"[{platform}] {detail}")


class HttpStatusError(HttpClientError):
    """非致命 HTTP 错误（5xx / 404 等），交给适配器判断。"""

    def __init__(self, platform: str, status_code: int, url: str) -> None:
        self.platform = platform
        self.status_code = status_code
        self.url = url
        super().__init__(f"[{platform}] HTTP {status_code}：{url}")


class PlatformBlockedError(HttpClientError):
    """401/403/429：平台在卡人，已触发熔断。"""

    def __init__(self, platform: str, status_code: int) -> None:
        self.platform = platform
        self.status_code = status_code
        hint = "登录态失效，请重新扫码" if status_code in (401, 403) else "被限流，已熔断"
        super().__init__(f"[{platform}] HTTP {status_code}，{hint}")


def looks_like_verification(
    resp: httpx.Response, markers: tuple[str, ...] = DEFAULT_VERIFY_MARKERS
) -> bool:
    """平台常把验证页用 200 返回，状态码看不出来，只能看内容。"""
    if resp.status_code != 200:
        return False
    if "html" not in resp.headers.get("content-type", "").lower():
        return False
    body = resp.text[:5000].lower()
    return any(m.lower() in body for m in markers)


class PlatformClient:
    """一个平台一个实例，生命周期跟着采集进程走。"""

    def __init__(
        self,
        platform: str,
        base_url: str,
        *,
        user_agent: str = DEFAULT_UA,
        headers: dict[str, str] | None = None,
        limiter: RateLimiter | None = None,
        breaker: CircuitBreaker | None = None,
        credential: Credential | None = None,
        credential_store: CredentialStore | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.platform = platform
        self.limiter = limiter or RateLimiter()
        self.breaker = breaker or CircuitBreaker(platform=platform)
        self._store = credential_store
        self._credential = credential
        if self._credential is None and credential_store is not None:
            self._credential = credential_store.load(platform)

        self._static_headers = {
            "User-Agent": user_agent,
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        if headers:
            self._static_headers.update(headers)

        initial_headers = dict(self._static_headers)
        if self._credential and self._credential.headers:
            initial_headers.update(self._credential.headers)


        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(settings.request_timeout, connect=5.0),
            headers=initial_headers,
            cookies=self._credential.cookies if self._credential else None,
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=1),
            transport=transport,
            follow_redirects=True,
        )

    # ---- 请求入口 ----

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        await self.breaker.before_request()
        async with self.limiter:
            try:
                resp = await self._client.request(method, url, **kwargs)
            except httpx.TimeoutException as exc:
                await self.breaker.record_failure(f"timeout: {type(exc).__name__}")
                raise HttpRequestError(self.platform, f"请求超时：{url}") from exc
            except httpx.HTTPError as exc:
                await self.breaker.record_failure(f"network: {type(exc).__name__}")
                raise HttpRequestError(self.platform, f"网络错误：{type(exc).__name__} {url}") from exc

        if is_fatal_status(resp.status_code):
            await self.breaker.record_failure(f"http {resp.status_code}", fatal=True)
            raise PlatformBlockedError(self.platform, resp.status_code)

        if resp.status_code >= 500:
            await self.breaker.record_failure(f"http {resp.status_code}")
            raise HttpStatusError(self.platform, resp.status_code, str(resp.request.url))

        if resp.status_code >= 400:
            raise HttpStatusError(self.platform, resp.status_code, str(resp.request.url))

        await self.breaker.record_success()
        return resp

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", url, **kwargs)

    async def report_fatal(self, reason: str) -> None:
        """适配器发现验证页 / 明显异常结构时调用，立即熔断。"""
        await self.breaker.record_failure(reason, fatal=True)

    def reload_credential(self) -> Credential | None:
        if self._store is None:
            return self._credential
        
        self._credential = self._store.load(self.platform)
        self._client.cookies.clear()
        if self._credential:
            self._client.cookies.update(self._credential.cookies)

        self._client.headers.clear()
        self._client.headers.update(self._static_headers)
        if self._credential and self._credential.headers:
            self._client.headers.update(self._credential.headers)
        return self._credential

    @property
    def health(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            **self.breaker.snapshot(),
            "limiter": self.limiter.stats,
        }

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "PlatformClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

if __name__ == "__main__":
    import asyncio

    async def _demo() -> None:
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.url.path)
            if request.url.path == "/ok":
                return httpx.Response(200, text="ok", request=request)
            if request.url.path == "/limited":
                return httpx.Response(429, text="slow down", request=request)
            if request.url.path == "/verify":
                return httpx.Response(
                    200,
                    text="<html><body>请完成安全验证</body></html>",
                    headers={"content-type": "text/html; charset=utf-8"},
                    request=request,
                )
            raise httpx.ConnectError("boom", request=request)

        def build() -> PlatformClient:
            return PlatformClient(
                platform="TEST",
                base_url="https://example.test",
                limiter=RateLimiter(rate_per_sec=20.0, burst=2, jitter_ms=(0, 0)),
                breaker=CircuitBreaker(
                    platform="TEST", cooldown_sec=1.0, fatal_cooldown_sec=1.0
                ),
                credential=Credential(platform="TEST", cookies={"sid": "x"}),
                transport=httpx.MockTransport(handler),
            )

        client = build()
        resp = await client.get("/ok")
        assert resp.status_code == 200
        assert client.breaker.state is CircuitState.CLOSED
        print("[1] 正常请求放行，熔断器 CLOSED")

        try:
            await client.get("/limited")
        except PlatformBlockedError as exc:
            print(f"[2] 429 触发熔断：{exc}")
        assert client.breaker.state is CircuitState.OPEN

        try:
            await client.get("/ok")
        except CircuitOpenError as exc:
            print(f"[3] 熔断期内本地拒绝，没出网：{exc}")
        assert calls == ["/ok", "/limited"], calls

        verify_client = build()
        verify = await verify_client.get("/verify")
        assert looks_like_verification(verify)
        await verify_client.report_fatal("verification page")
        assert verify_client.breaker.state is CircuitState.OPEN
        print("[4] 200 验证页识别成功，并升级为致命失败")
        await verify_client.aclose()

        net = build()
        try:
            await net.get("/boom")
        except HttpRequestError as exc:
            print(f"[5] 网络错误归类：{exc}")
        assert net.breaker.snapshot()["consecutive_failures"] == 1
        await net.aclose()

        await client.aclose()

    asyncio.run(_demo())
    print("[OK] http_client 自检通过")
