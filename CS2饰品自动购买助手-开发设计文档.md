# CS2 饰品自动购买助手 · 开发设计文档

| 项目 | 说明 |
| --- | --- |
| 文档版本 | v1.0 |
| 编写日期 | 2026-11-25 |
| 文档状态 | 设计评审稿 |
| 目标读者 | 后端开发 / 前端开发 / 运维 |
| 覆盖平台 | 网易 BUFF、悠悠有品、C5GAME |
| 文档范围 | 系统设计、数据模型、接口、测试、迭代与风险 |

---

## 0. 先划边界：这套系统做什么、不做什么

这份文档描述的是一套「**盯价自动化 + 下单人工确认**」的饰品助手。之所以不做"脚本自动点支付"，不是技术做不到，而是做完之后必然踩三条线：

**第一条是平台规则线。** 悠悠有品《用户协议》第七条明确写了，用户不得"开发、支持或使用软件、设备、脚本、程序"干扰平台正常运营，也不得违反 Robots 协议或突破反爬虫措施获取平台信息；BUFF 的用户协议把"脚本（robots）、插件、按键精灵、模拟用户操作"直接归入 Cheats 一类；网易体系的服务协议同样禁止使用机器人程序或第三方软件模拟登录、干扰服务。也就是说，一旦做全自动抢购，账号本身就处在可被处置的状态。

**第二条是资产安全线。** 饰品是真金白银的资产。账号被判违规冻结的时候，锁住的不只是账号，还有库存里的刀和手套。用一个随时可能被封的自动化去博几十块的差价，风险收益比是负的。

**第三条是维护成本线。** 平台侧的签名参数、设备指纹、行为风控一直在变，逆向方案的生命周期通常以周计。为了省一次点击去维护一套注定被淘汰的对抗代码，工程上不划算。

所以本文档的取舍是：**把"看"和"算"自动化，把"买"留给人**。系统负责 7×24 盯价、跨平台归一、剔除假低价、推送到手机；用户收到卡片后点深链，在平台 App 里按正常流程下单。这个形态下，效率提升主要来自"不错过 + 不误判"，而不是来自几百毫秒的抢跑。

| 能力 | 是否纳入 | 说明 |
| --- | --- | --- |
| 多平台商品监控、比价 | ✅ 纳入 | 项目核心价值 |
| 目标价触发、降价推送 | ✅ 纳入 | 规则引擎 |
| 磨损 / 印花 / 改名等条件过滤 | ✅ 纳入 | 决定"是不是真便宜" |
| 一键深链跳转、订单只读对账 | ✅ 纳入 | 执行闭环 |
| 秒级高频轮询 | ❌ 不做 | 默认 60s 级，遇风控立即熔断 |
| 逆向平台签名 / 破解加密参数 | ❌ 不做 | 属技术保护措施，不解析不复现 |
| 验证码识别、设备指纹伪造 | ❌ 不做 | 绕过身份校验 |
| 代理 IP 池、多账号养号 | ❌ 不做 | 规避风控，且违反"本人账号"条款 |
| 自动提交订单 / 自动支付 | ❌ 不做 | 违反平台自动化条款，且资金风险不可控 |

---

## 1. 项目目标与范围

### 1.1 一句话定义

一个跨 BUFF / 悠悠有品 / C5GAME 的饰品价格监控与决策系统：把三个平台的同款饰品对齐到同一口径，算出"实际到手成本"，在出现真实机会时推送到用户手机。

### 1.2 核心场景

1. **蹲低价**：用户想收一把「AWP | 二西莫夫（久经沙场）」，心理价位 780 元。系统持续监控三平台在售最低价，当出现低于近 7 日成交中位数 8% 的挂单时推送。
2. **跨平台比价**：同一件饰品，用户想知道此刻在三个平台各自的"标价—手续费—到手净得"是多少，差价有多大，值不值得跨平台搬。
3. **成色筛选**：同款同磨损，float 0.16 和 float 0.36 是两个价。系统按磨损分桶 + float 区间过滤，避免"便宜是因为磨损差"的误报。

### 1.3 非目标

- 不做代购、代抢、代拍服务。
- 不做饰品价格预测、投资建议。
- 不做账号托管、代登录。

### 1.4 成功指标

| 指标 | 目标值 | 口径 |
| --- | --- | --- |
| 采集成功率 | ≥ 98% | 单轮采集成功任务 / 总任务，不含熔断期 |
| 端到端延迟 | P95 ≤ 90s | 商品上架 → 用户收到推送 |
| 误报率 | ≤ 5% | 推送后被用户标记"不感兴趣"的比例 |
| 漏报率 | ≤ 3% | 符合条件的挂单未推送的比例（抽样核对） |
| 单机承载 | ≥ 3000 个监控标的 | 4C8G 单机，60s 轮询周期 |

---

## 2. 需求分析

### 2.1 功能需求

| 编号 | 功能 | 优先级 | 验收要点 |
| --- | --- | --- | --- |
| FR-01 | 平台商品采集（三平台） | P0 | 能取到在售列表、价格、磨损、卖家、上架时间 |
| FR-02 | 跨平台商品归一 | P0 | 同款饰品在三平台能 join 到同一条记录 |
| FR-03 | 监控清单管理 | P0 | 增删改查，支持批量导入 |
| FR-04 | 规则引擎（目标价 / 折扣阈值） | P0 | 规则命中即生成事件，支持冷却与日限额 |
| FR-05 | 多通道通知 | P0 | 飞书卡片 / 邮件，含深链 |
| FR-06 | 比价面板 | P1 | 单件饰品三平台横向对比，含费率折算 |
| FR-07 | 历史价格曲线 | P1 | 近 30 天最低价 / 中位数 / 在售量 |
| FR-08 | 订单对账 | P1 | 只读拉取本人订单，回写状态到状态机 |
| FR-09 | 采集健康度看板 | P1 | 成功率、延迟、熔断次数 |
| FR-10 | 数据导出 | P2 | CSV / Excel，用于复盘 |

### 2.2 非功能需求

| 维度 | 要求 |
| --- | --- |
| 采集频率 | 默认 60s/标的，可配 30s–10min；同一平台全局并发 ≤ 2 |
| 可用性 | 采集侧单平台故障不影响其余平台；核心服务 99% |
| 数据准确性 | 金额统一用"分"存整型，禁止浮点；费率可配置且留生效时间 |
| 安全 | 登录态加密存储，单账号单会话，日志脱敏（Cookie / Token 不入日志） |
| 可观测 | 关键链路打点，异常 5 分钟内告警到人 |
| 可维护 | 新增平台只需实现一个 Collector 适配器，不改核心链路 |

---

## 3. 总体架构

### 3.1 架构图

```
┌─────────────────── 采集层 (Python) ────────────────────┐
│  buff_collector   youpin_collector   c5_collector      │
│  限速器 · 熔断器 · 响应缓存(ETag) · 本人单账号登录态     │
└────────────────────────┬───────────────────────────────┘
                         │ 原始快照 JSON（Redis Stream）
┌────────────────────────▼───────────────────────────────┐
│ 归一化 Normalizer（Java）                              │
│  market_hash_name 对齐 · 磨损分桶 · 印花/改名识别 · 费率折算 │
└────────────────────────┬───────────────────────────────┘
┌────────────────────────▼───────────────────────────────┐
│ 规则引擎 Rule Engine（Java）                            │
│  目标价 · 折扣阈值 · 过滤条件 · 冷却 · 日限额            │
└────────────────────────┬───────────────────────────────┘
┌────────────────────────▼───────────────────────────────┐
│ 通知 Notifier                                          │
│  飞书卡片（含深链）· 邮件 · 站内消息                     │
└────────────────────────┬───────────────────────────────┘
┌────────────────────────▼───────────────────────────────┐
│ 人工确认 & 对账                                          │
│  用户点深链 → 平台 App 下单 → 系统只读拉订单回写状态      │
└────────────────────────────────────────────────────────┘
```

### 3.2 模块职责

| 模块 | 职责 | 边界 |
| --- | --- | --- |
| Collector | 按平台抓取在售列表与详情，输出统一结构的原始快照 | 不解析平台签名参数，不做验证码处理 |
| Normalizer | 命名归一、磨损分桶、附加价值识别、费率折算 | 不做业务判断 |
| Rule Engine | 规则匹配、估值对比、阈值判定、冷却控制 | 不直接下单 |
| Notifier | 渲染卡片、多通道投递、失败重试 | 不持有业务状态 |
| Reconciler | 只读拉取本人订单，驱动状态机流转 | 不做任何写操作 |

### 3.3 技术选型

| 层次 | 选型 | 理由 |
| --- | --- | --- |
| 核心服务 | Spring Boot 3.x + MyBatis-Plus | 与现有技术栈一致，生态成熟 |
| 采集 | Python 3.11 + httpx + Playwright | 页面级解析灵活，Playwright 只在必要时兜底 |
| 存储 | MySQL 8（明细）+ Redis 7（去重 / 缓存 / 队列） | 快照量大，MySQL 分区 + Redis 去重 |
| 调度 | Spring Scheduler + Redis 分布式锁 | 单机够用，不引入 XXL-Job 增加部署复杂度 |
| 前端 | Vue 3 + Element Plus + ECharts | 比价面板与价格曲线 |
| 通知 | 飞书自定义机器人 Webhook | 卡片交互体验好，零成本 |
| 监控 | Micrometer + Prometheus + Grafana | 采集成功率 / 延迟 / 熔断一目了然 |
| 部署 | Docker Compose（core + collector + mysql + redis） | 单机一键起，后续可拆 |

> 采集用 Python、核心用 Java 是有意为之：解析页面是 Python 的主场，业务编排是 Java 的主场。两者用 Redis Stream 解耦，互不阻塞。

### 3.4 部署拓扑

单机 Docker Compose 起步，四个容器：`app-core`（Java）、`collector`（Python）、`mysql`、`redis`。采集容器挂 `Asia/Shanghai` 时区，Playwright 镜像预装中文字体。日后再拆时，Collector 天然可水平扩展（按平台分片）。

---

## 4. 数据模型

### 4.1 跨平台归一化（本项目最难的一块）

三个平台对同一件饰品的命名、编号、字段口径都不一样。归一化做不好，后面全是脏数据。

**主键选择**：以 Steam 的 `market_hash_name` 作为跨平台业务主键，例如 `AWP | Asiimov (Field-Tested)`。平台自有的 `goods_id` / `templateId` 只在本平台内唯一，必须落一张映射表。

**三级对齐策略**：

1. 一级：`market_hash_name` 完全相等，直接命中。
2. 二级：去除前后缀噪声（`★`、`StatTrak™`、`Souvenir`、`（★）`）后模糊匹配，人工确认后写入映射。
3. 三级：图片指纹 + 名称相似度兜底，进入待人工审核队列。

**磨损口径**：磨损值（float）保留 8 位小数，按 Steam 标准分桶——崭新出厂 0.00–0.07、略有磨损 0.07–0.15、久经沙场 0.15–0.38、破损不堪 0.38–0.45、战痕累累 0.45–1.00。比价必须"同款 + 同磨损桶 + float 落在同一区间"才可比，否则价差没有意义。

**附加价值识别**：同款同磨损，带稀有印花、低位图案模板（paint seed）、未改名，价格可以差出一截。归一化阶段要打三个标记：`has_sticker`、`renamed`、`paint_seed`，规则引擎据此上调或下调可接受价。

### 4.2 核心表设计

```sql
-- 1. 商品映射（跨平台归一的结果）
CREATE TABLE item_mapping (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  market_hash_name VARCHAR(255) NOT NULL COMMENT 'Steam 市场名，业务主键',
  platform        VARCHAR(16)  NOT NULL COMMENT 'BUFF / YOUPIN / C5',
  platform_item_id VARCHAR(64) NOT NULL,
  raw_name        VARCHAR(255) COMMENT '平台原始名称',
  wear_bucket     TINYINT COMMENT '1崭新 2略磨 3久经 4破损 5战痕',
  stat_trak       TINYINT(1) DEFAULT 0,
  souvenir        TINYINT(1) DEFAULT 0,
  match_level     TINYINT COMMENT '1精确 2模糊 3人工',
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_platform_item (platform, platform_item_id),
  KEY idx_mhn (market_hash_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. 在售快照（按天分区，保留 90 天）
CREATE TABLE listing_snapshot (
  id               BIGINT AUTO_INCREMENT,
  platform         VARCHAR(16) NOT NULL,
  platform_item_id VARCHAR(64) NOT NULL,
  market_hash_name VARCHAR(255) NOT NULL,
  wear_bucket      TINYINT,
  float_value      DECIMAL(10,8),
  paint_seed       INT,
  has_sticker      TINYINT(1) DEFAULT 0,
  renamed          TINYINT(1) DEFAULT 0,
  price_amount     BIGINT COMMENT '标价，单位：分',
  net_cost         BIGINT COMMENT '到手成本，单位：分（已含费率折算）',
  currency         CHAR(3) DEFAULT 'CNY',
  seller_hash      CHAR(32) COMMENT '卖家标识哈希，脱敏',
  listed_at        DATETIME,
  snapshot_at      DATETIME NOT NULL,
  PRIMARY KEY (id, snapshot_at),
  KEY idx_mhn_time (market_hash_name, snapshot_at),
  KEY idx_platform_time (platform, snapshot_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  PARTITION BY RANGE (TO_DAYS(snapshot_at)) (PARTITION p_init VALUES LESS THAN MAXVALUE);

-- 3. 监控规则
CREATE TABLE watch_rule (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  rule_name     VARCHAR(128) NOT NULL,
  market_hash_name VARCHAR(255) NOT NULL,
  wear_bucket   TINYINT,
  float_min     DECIMAL(10,8),
  float_max     DECIMAL(10,8),
  max_price     BIGINT COMMENT '心理价位，单位：分',
  discount_pct  DECIMAL(5,2) COMMENT '低于近7日基准的折扣阈值',
  filter_json   JSON COMMENT '排除条件：关键词、印花、改名等',
  cooldown_sec  INT DEFAULT 600,
  daily_limit   INT DEFAULT 20,
  enabled       TINYINT(1) DEFAULT 1,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. 触发事件
CREATE TABLE alert_event (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  rule_id       BIGINT NOT NULL,
  platform      VARCHAR(16) NOT NULL,
  platform_item_id VARCHAR(64) NOT NULL,
  market_hash_name VARCHAR(255),
  price_amount  BIGINT,
  baseline_price BIGINT COMMENT '近7日基准价',
  discount_pct  DECIMAL(5,2),
  deeplink      VARCHAR(512),
  status        VARCHAR(16) DEFAULT 'PENDING' COMMENT 'PENDING/SENT/ACK/IGNORED',
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_rule_time (rule_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. 费率配置（口径统一的关键）
CREATE TABLE fee_config (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  platform      VARCHAR(16) NOT NULL,
  side          VARCHAR(8) NOT NULL COMMENT 'BUY / SELL',
  fee_rate      DECIMAL(6,4) NOT NULL COMMENT '如 0.0250 表示 2.5%',
  fixed_fee     BIGINT DEFAULT 0 COMMENT '固定费，单位：分',
  effective_from DATETIME NOT NULL,
  remark        VARCHAR(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 4.3 价格口径（最容易做错的地方）

比价不能比"标价"，要比"到手成本"和"到手净得"。定义两个派生字段：

- **到手成本** `net_cost = 标价 + 平台附加费用`（买家侧，含会员折扣、充值损耗的折算）
- **到手净得** `net_proceeds = 标价 − 卖家手续费 − 提现费`

费率一律从 `fee_config` 读，按 `effective_from` 取生效版本，禁止硬编码数字。各平台费率随会员等级、活动、品类变动，必须以平台当时公示为准，配置化之后改一次配置就能全量生效。

---

## 5. 采集层设计

### 5.1 适配器抽象

每个平台一个适配器，对外只暴露三个方法，核心链路不感知平台差异。

```java
public interface MarketCollector {

    Platform platform();

    /** 拉取在售列表，按平台内部游标翻页 */
    List<RawListing> fetchListings(CollectorContext ctx, PageQuery query);

    /** 拉取单品详情（磨损、印花、卖家信息） */
    Optional<RawListing> fetchDetail(CollectorContext ctx, String platformItemId);

    /** 健康度：最近一次成功时间、连续失败次数、是否熔断 */
    HealthStatus health();
}
```

`CollectorContext` 携带三样东西：登录态引用（不落明文）、限速器、熔断器。适配器内部所有请求都必须经过 `ctx.rateLimiter.acquire()`，这是硬约束，避免某个适配器写飞了把整个平台账号拖下水。

### 5.2 采集策略（合规前提下把效率榨干）

1. **频率分层**：监控中的标的 60s，未监控的只做每日一次的全量快照（用来算基准价）。绝不对全站高频扫。
2. **增量优先**：优先命中平台的列表接口/页面默认排序（按上架时间倒序），只拉首页前 N 条，靠 `listing_id` 去重判断是否有新货。比"翻全量"省两个数量级的请求。
3. **缓存**：静态字段（饰品名、图片、模板 ID）缓存 24 小时；动态字段（价格、卖家、数量）不缓存。
4. **指数退避**：失败 1 次退 10s，2 次退 30s，3 次退 120s，5 次进入熔断。
5. **熔断规则**：收到 429、跳转验证页、返回风控提示、登录态失效，任一命中立即熔断该平台 15–30 分钟，并推一条告警。熔断期间不做任何重试——重试只会加重判定。
6. **全局并发**：单平台任何时刻在途请求 ≤ 2，请求间隔加 200–800ms 随机抖动。

### 5.3 登录态管理

- 只支持**用户本人**扫码登录，Cookie / Token 用 AES-GCM 加密存 `secure_credential` 表，密钥来自环境变量或系统凭据库，不入代码库。
- 单账号单会话，同一平台不允许并存多个会话——这是"本人账号"条款的底线。
- 登录态失效时只做一件事：推送"请重新扫码"，不尝试任何自动续期或绕过。

### 5.4 明确不做的对抗手段

不解析平台的签名/加密参数、不做设备指纹与 UA 轮换、不接代理 IP 池、不识别验证码、不多账号轮询。这些手段短期能把采集成功率推到 99%，长期换来的是账号被处置和一套永远在打补丁的代码。本项目的定位是"个人助手"，不是"抢购工具"，没有理由付这个代价。

### 5.5 调度

```
Redis 分布式锁  collector:lock:{platform}
  └─ 每 60s 触发一次 → 取监控清单 → 分批（每批 20 个标的）→ 投递到 Redis Stream
Consumer Group（2 个消费者）→ 调适配器 → 原始 JSON 落 stream → Normalizer 消费
```

失败任务进死信队列，超过 3 次转人工排查，不自动丢弃。

---

## 6. 决策层：规则引擎

### 6.1 规则模型

一条规则 = **匹配条件** + **估值基准** + **触发阈值** + **节流** + **动作**。

```yaml
rule:
  id: awp-asiimov-ft-780
  name: AWP 二西莫夫 久经 · 780 元以内蹲
  enabled: true

  match:
    market_hash_name: "AWP | Asiimov (Field-Tested)"
    wear_bucket: FT
    float_max: 0.30          # 磨损太好反而溢价，这里限上限
    stattrak: false
    max_net_cost_cny: 780

  filter:
    exclude_keywords: ["改名", "刮印花", "租", "押金"]
    min_sticker_value_cny: 0
    min_listing_age_sec: 0

  valuation:
    baseline: median_7d       # 近7日成交中位数
    discount_threshold_pct: 8
    min_sample: 30            # 样本不足时不判定

  throttle:
    cooldown_sec: 600
    daily_limit: 20
    merge_window_sec: 120     # 同款多条命中合并成一条推送

  action:
    notify: [feishu, email]
    deeplink: platform_native
    priority: high
```

### 6.2 估值逻辑：怎么判断"真便宜"

只看绝对价格会被两类假机会骗：一是卖家抬价后再打折，二是磨损/印花差导致的低价。所以判定要过三道闸：

1. **基准闸**：近 7 日同款同磨损成交中位数作为基准，样本少于 30 条不判（新饰品或缺货期不适用）。
2. **折扣闸**：`(基准 − 到手成本) / 基准 ≥ discount_threshold_pct`，默认 8%。
3. **相对闸**：该挂单必须是当前三平台同款里的最低到手成本，且比第二低至少 3%。避免"三平台都贵，最便宜那个也被推"。

三道全过才算命中。命中后按 `merge_window_sec` 聚合，同款多条只推一条（列出前 3 个最优挂单）。

### 6.3 防打扰

- 单规则冷却 10 分钟，同款同平台不重复推。
- 单规则日限额 20 条，超限降级为"日报汇总"。
- 夜间 23:00–08:00 静默（可配），紧急规则除外。
- 每条推送带"不感兴趣"快捷按钮，点了之后该卖家 24 小时内不再推。

---

## 7. 执行层：人工确认闭环

### 7.1 通知卡片字段

| 字段 | 说明 |
| --- | --- |
| 饰品图 + 名称 | 一眼认货 |
| 平台 | BUFF / 悠悠有品 / C5GAME |
| 标价 / 到手成本 | 两个数字都给，避免"看着便宜实际加费" |
| 磨损 + float | 精确到小数点后 4 位 |
| 基准价 + 折扣 | "近 7 日中位 860，低 9.3%" |
| 卖家信用 | 等级 / 成交数 / 好评率（页面可见的部分） |
| 深链 | 直跳该挂单详情页 |
| 快捷操作 | 感兴趣 / 不感兴趣 / 已买入 |

卡片示例文案：

> **AWP | 二西莫夫（久经沙场）· BUFF**
> 标价 ¥772.00 ｜ 到手 ¥772.00 ｜ 磨损 0.2143
> 近 7 日中位 ¥860.00，低 **10.2%**
> 卖家 Lv.6 ｜ 成交 1,284 单 ｜ 好评 99.1%
> 剩余 1 件 ｜ 上架 3 分钟前

### 7.2 深链跳转

跳平台原生详情页，用户自己走"立即购买 → 支付"流程。系统不预填表单、不模拟点击、不接管支付。这一步是刻意留白：**它既是合规边界，也是资金安全的最后一道人工闸**。

### 7.3 订单对账（只读）

下单后，Reconciler 每 10 分钟拉一次本人订单列表（同样低频、只读），按 `platform_order_id` 回写状态。用途只有两个：更新状态机、统计实际成交价用于校准基准。**不做任何取消、改价、确认收货等写操作。**

### 7.4 订单状态机

```
DRAFT → PENDING_PAY → PAID → TRADE_LOCK(7天交易冷却) → SELLABLE → SELLING → SOLD
            │            │
            └→ CANCEL    └→ REFUND / DISPUTE
```

CS2 饰品买入后通常有 7 天交易冷却，期间不可转售。状态机必须体现这个窗口，否则"我以为买完就能卖"会造成现金流误判。

---

## 8. 接口设计

### 8.1 REST 一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/rules` | 规则列表（分页、按启用状态过滤） |
| POST | `/api/v1/rules` | 新建规则 |
| PUT | `/api/v1/rules/{id}` | 更新规则 |
| PATCH | `/api/v1/rules/{id}/toggle` | 启停 |
| GET | `/api/v1/compare?mhn={market_hash_name}` | 三平台比价（含费率折算） |
| GET | `/api/v1/price/history?mhn=...&days=30` | 价格曲线 |
| GET | `/api/v1/alerts` | 事件列表 |
| PATCH | `/api/v1/alerts/{id}/ack` | 标记已读 / 不感兴趣 |
| GET | `/api/v1/orders` | 本人订单（只读镜像） |
| GET | `/api/v1/health/collectors` | 采集健康度 |

### 8.2 比价响应示例

```json
{
  "marketHashName": "AWP | Asiimov (Field-Tested)",
  "wearBucket": "FT",
  "baseline": { "median7d": 86000, "sampleSize": 142, "unit": "cent" },
  "platforms": [
    {
      "platform": "BUFF",
      "lowestPrice": 77200,
      "netCost": 77200,
      "sellerLevel": 6,
      "floatValue": 0.2143,
      "hasSticker": false,
      "renamed": false,
      "deeplink": "...",
      "snapshotAt": "2026-11-25T16:40:12+08:00"
    },
    {
      "platform": "YOUPIN",
      "lowestPrice": 78500,
      "netCost": 78500,
      "sellerLevel": 4,
      "floatValue": 0.3011,
      "hasSticker": true,
      "renamed": false,
      "deeplink": "...",
      "snapshotAt": "2026-11-25T16:40:35+08:00"
    },
    {
      "platform": "C5",
      "lowestPrice": 79000,
      "netCost": 79800,
      "sellerLevel": 5,
      "floatValue": 0.1888,
      "hasSticker": false,
      "renamed": true,
      "deeplink": "...",
      "snapshotAt": "2026-11-25T16:41:02+08:00"
    }
  ],
  "verdict": { "best": "BUFF", "gapPct": 2.1, "isOpportunity": true }
}
```

---

## 9. 非功能设计

### 9.1 性能与容量估算

| 项 | 估算 |
| --- | --- |
| 监控标的 3000 个，60s 周期 | 50 次请求/秒的理论峰值 → 实际限速到 2–5 次/秒，靠"只拉首页 + 增量"实现 |
| 单标的快照 2KB | 3000 × 1440 次/天 ≈ 8.6GB/天（含全部快照） |
| 存储优化 | 只在价格或卖家变化时落快照，能砍到 1/10；明细保留 30 天，聚合曲线永久 |

### 9.2 可观测性

| 指标 | 类型 | 用途 |
| --- | --- | --- |
| `collector.success_rate{platform}` | Gauge | 成功率低于 95% 告警 |
| `collector.latency_p95{platform}` | Histogram | 延迟劣化预警 |
| `collector.circuit_open{platform}` | Counter | 熔断次数，突增说明风控收紧 |
| `rule.eval_duration` | Histogram | 规则评估耗时 |
| `alert.ack_rate` | Gauge | 误报率的代理指标 |

日志规范：采集日志打 `platform + item_id + status + elapsed`；**Cookie、Token、手机号、支付信息一律不进日志**，敏感字段走脱敏注解。

### 9.3 安全

- 登录态 AES-GCM 加密，密钥与数据分离存储。
- 数据库只对内网开放，不对公网暴露端口。
- 后台管理页做单用户鉴权（这套系统只服务一个人，不需要复杂权限模型）。
- 依赖做定期漏洞扫描，Playwright 镜像不装无关系统包。

### 9.4 容错与降级

| 场景 | 降级策略 |
| --- | --- |
| 单平台熔断 | 其余平台照常，卡片标注"该平台数据延迟" |
| 规则引擎异常 | 采集继续落库，恢复后补跑最近 30 分钟快照 |
| 通知通道失败 | 飞书失败转邮件，双失败落站内消息并标红 |
| 数据库不可用 | 采集侧写本地文件缓冲，恢复后回放 |

---

## 10. 测试方案

### 10.1 分层测试

| 层次 | 手段 | 重点 |
| --- | --- | --- |
| 单元测试 | JUnit 5 + Mockito | 归一化映射、费率折算、规则阈值边界（含 0 与负数） |
| 契约测试 | 录制真实响应存为 fixture | 适配器解析不因页面改版静默失败 |
| 回放测试 | 用历史快照回放一遍规则 | 验证阈值调整后的推送量变化 |
| 集成测试 | Testcontainers 起 MySQL + Redis | 端到端从采集到推送 |
| 灰度 | 新规则先"只记录不推送"跑 3 天 | 比对命中与实际行情，校准阈值 |

### 10.2 关键验收用例

| 编号 | 用例 | 期望 |
| --- | --- | --- |
| TC-01 | 同一挂单连续 5 轮采集 | 只落 1 条快照（去重生效） |
| TC-02 | 价格下跌 10% 且超阈值 | 10 分钟内推送 1 条 |
| TC-03 | 冷却期内再次命中 | 不推送 |
| TC-04 | 平台返回 429 | 立即熔断，30 分钟内零请求 |
| TC-05 | 费率配置变更 | 新快照按新费率折算，历史数据不变 |
| TC-06 | 磨损 0.381 的挂单匹配 FT 规则 | 不命中（分桶边界正确） |
| TC-07 | 通知通道全挂 | 落站内消息，不丢事件 |
| TC-08 | 基准样本 < 30 | 不判定，记录"样本不足" |

---

## 11. 迭代计划（4 周 MVP）

| 周 | 交付物 | 验收标准 |
| --- | --- | --- |
| W1 | 单平台（BUFF）采集 + 快照落库 + 健康度 | 连续 24 小时采集成功率 ≥ 98%，熔断行为符合预期 |
| W2 | 归一化 + 规则引擎 + 飞书推送 | 手工构造 20 条规则，命中/不命中判断全部正确 |
| W3 | 三平台接入 + 比价面板 + 价格曲线 | 同款在三平台能正确 join，比价误差 ≤ 0（分单位精确） |
| W4 | 订单对账 + 状态机 + 报表导出 | 订单状态回流无错漏，日报可导出 |

节奏说明：W1 只做单平台是故意的——先把"稳定采集 + 不触发风控"这件事验证透，再复制到另外两个平台。三个平台同时开工，出问题时不知道是适配器写错还是策略太激进。

### 建议目录结构

```
cs2-skin-assistant/
├── app-core/                       # Spring Boot 3
│   ├── src/main/java/.../collector/    # 适配器接口与平台实现
│   ├── src/main/java/.../normalizer/   # 归一化
│   ├── src/main/java/.../rule/         # 规则引擎
│   ├── src/main/java/.../notify/       # 通知
│   ├── src/main/java/.../reconcile/    # 对账
│   └── src/main/resources/db/migration/
├── collector-py/                   # Python 采集侧
│   ├── adapters/buff.py
│   ├── adapters/youpin.py
│   ├── adapters/c5.py
│   ├── core/rate_limiter.py
│   └── core/circuit_breaker.py
├── web/                            # Vue 3
├── deploy/docker-compose.yml
└── docs/                           # 本文档 + 接口文档
```

---

## 12. 风险登记册

| 编号 | 风险 | 等级 | 影响 | 缓解 |
| --- | --- | --- | --- | --- |
| R-01 | 平台判定为自动化工具，账号受限 | 高 | 账号与库存冻结 | 低频只读、单账号、不绕过风控；发现提示立即停采 |
| R-02 | 平台页面/接口改版，采集失效 | 高 | 数据断流 | 契约测试 + fixture 回放；解析失败即告警而非静默 |
| R-03 | 磨损/印花识别错误，推送假低价 | 中 | 误买，资金损失 | 三级过滤 + 灰度只记录模式 + 人工反馈闭环 |
| R-04 | 费率理解偏差，比价失真 | 中 | 决策错误 | 费率配置化，每次调整留生效时间与备注 |
| R-05 | 快照量膨胀，存储撑爆 | 中 | 服务不可用 | 变化才落库 + 分区 + TTL |
| R-06 | 通知轰炸，用户关掉通知 | 中 | 系统失效 | 冷却、日限额、聚合、夜间静默 |
| R-07 | 触及平台交易规则或监管口径 | 高 | 法律与合规风险 | 仅个人自用、不对外提供服务、不做代拍代购 |
| R-08 | Steam 侧风控（异地登录、API Key 泄露） | 中 | 库存被盗 | 不代管 Steam 账号，不索要 API Key；只用平台自身登录态 |

---

## 13. 附录

### A. 术语表

| 术语 | 含义 |
| --- | --- |
| market_hash_name | Steam 市场物品名，跨平台归一的业务主键 |
| float / 磨损值 | 物品外观磨损的数值，0.00–1.00 |
| paint_seed | 图案模板编号，影响同款饰品的图案位置与溢价 |
| StatTrak / 纪念品 | 带计数器的版本 / 赛事纪念版本，独立品类 |
| 到手成本 | 标价 + 买家侧附加费用，用于跨平台比价 |
| 熔断 | 检测到风控信号后暂停该平台采集一段时间 |

### B. 平台协议参考（务必自行复核最新版本）

- 悠悠有品《用户协议》：https://h5.youpin898.com/pc/userProtocol.html
- BUFF User Agreement（含 4.5 User Conduct，明确将脚本/机器人归入 Cheats）：https://buff.market/static/user_agreement.html
- 网易《使用许可及服务协议》（第十一条 不正当游戏行为）：https://unisdk.update.netease.com/html/latest_v29.html

> 协议会更新，接入前请以平台当时公示的版本为准；本文档不对条款做法律解释。

### C. 后续可扩展方向

- 租赁行情接入（悠悠有品租转售场景），需单独立项评估。
- float 区间溢价模型：基于历史成交做分档定价，替代单一中位数。
- 跨平台套利成本模型：把提现周期、交易冷却、手续费全部折进"真实收益率"。

---

**文档结束**
