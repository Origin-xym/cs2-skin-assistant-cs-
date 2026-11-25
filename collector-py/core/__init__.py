"""采集侧基础设施。

    rate_limiter.py     令牌桶限速，单平台在途请求 ≤ 2
    circuit_breaker.py  熔断器，遇 429 / 验证页 / 登录态失效立即暂停
    credentials.py      登录态加解密（AES-GCM）

原则：宁可少采一轮，也不要把账号拖进风控。
"""
