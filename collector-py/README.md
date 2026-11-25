# collector-py · CS2 饰品采集侧

跨 BUFF / 悠悠有品 / C5GAME 的只读采集器，把挂单快照推进 Redis Stream，
交给 Java 侧的 app-core 做归一化与规则判断。

## 环境

| 项 | 值 |
| --- | --- |
| 解释器 | `D:\Python\python.exe`（3.12.10） |
| 虚拟环境 | `.venv`（依赖装在这里，不要装到全局） |
| Redis | `127.0.0.1:6379`，Redis 8.10.3 |
| Playwright 内核 | `D:\playwright-browsers`（环境变量 `PLAYWRIGHT_BROWSERS_PATH` 已设） |

## 自检

```powershell
cd D:\cs2-skin-assistant\collector-py
.venv\Scripts\python.exe main.py
```

全部 `[OK]` 即环境就绪。

## 目录

```
collector-py\
├── .venv\               依赖隔离在这里
├── adapters\            各平台采集器，均继承 base.MarketCollector
│   ├── base.py          RawListing 模型 + 抽象接口（已定义）
│   ├── buff.py          待实现
│   ├── youpin.py        待实现
│   └── c5.py            待实现
├── core\                限速、熔断、登录态（待实现）
├── data\                加密登录态、快照缓冲（不入 git）
├── logs\                运行日志
├── config.py            统一配置入口
├── main.py              环境自检
└── requirements.txt     依赖锁定
```

## 下一步

1. 实现 `core/rate_limiter.py`：令牌桶，单平台并发 ≤ 2，请求间隔 200–800ms 抖动。
2. 实现 `adapters/buff.py`：先只做 `fetch_listings` 第一页 + 本地去重。
3. 快照写 Redis Stream：`XADD cs2:listings * platform BUFF payload '<json>'`。

## 红线（写代码前先读一遍）

- 不做签名逆向、不做验证码识别、不做设备指纹伪造、不接代理 IP 池、不多账号轮询。
- 遇 429 / 跳验证页 / 登录态失效：立即熔断该平台 15–30 分钟，**不重试**。
- 登录态只存用户本人扫码得到的 Cookie，加密后放 `data/`，密钥走环境变量。
- 采集快照保留 30 天，聚合后的价格曲线永久保留。
