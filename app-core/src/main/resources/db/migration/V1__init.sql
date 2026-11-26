-- CS2 饰品监控核心表：5 张业务表，Flyway 会另建 flyway_schema_history
-- 字符集统一 utf8mb4，金额一律整数“分”

CREATE TABLE item_mapping (
  id BIGINT NOT NULL AUTO_INCREMENT,
  market_hash_name VARCHAR(255) NOT NULL COMMENT 'Steam 市场名，跨平台业务主键',
  platform VARCHAR(16) NOT NULL COMMENT 'BUFF / YOUPIN / C5',
  platform_goods_id VARCHAR(64) NOT NULL COMMENT '平台商品 ID：BUFF goods_id、YOUPIN templateId、C5 productId',
  raw_name VARCHAR(255) NULL COMMENT '平台原始名称',
  wear_bucket TINYINT NULL COMMENT '1崭新 2略磨 3久经 4破损 5战痕',
  stat_trak TINYINT(1) NOT NULL DEFAULT 0,
  souvenir TINYINT(1) NOT NULL DEFAULT 0,
  match_level TINYINT NOT NULL DEFAULT 1 COMMENT '1精确 2模糊 3人工',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_platform_goods (platform, platform_goods_id),
  KEY idx_mhn (market_hash_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='商品映射';

CREATE TABLE listing_snapshot (
  id BIGINT NOT NULL AUTO_INCREMENT,
  platform VARCHAR(16) NOT NULL,
  platform_item_id VARCHAR(64) NOT NULL COMMENT '平台挂单 ID',
  market_hash_name VARCHAR(255) NOT NULL,
  wear_bucket TINYINT NULL,
  float_value DECIMAL(10,8) NULL,
  paint_seed INT NULL,
  has_sticker TINYINT(1) NOT NULL DEFAULT 0,
  renamed TINYINT(1) NOT NULL DEFAULT 0,
  price_amount BIGINT NOT NULL COMMENT '标价，单位：分',
  net_cost BIGINT NULL COMMENT '到手成本，单位：分（含费率折算）',
  currency CHAR(3) NOT NULL DEFAULT 'CNY',
  seller_hash CHAR(32) NULL COMMENT '卖家标识哈希，脱敏',
  listed_at DATETIME NULL,
  snapshot_at DATETIME NOT NULL,
  PRIMARY KEY (id, snapshot_at),
  KEY idx_mhn_time (market_hash_name, snapshot_at),
  KEY idx_platform_time (platform, snapshot_at),
  KEY idx_platform_item (platform, platform_item_id, snapshot_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='在售快照'
PARTITION BY RANGE (TO_DAYS(snapshot_at)) (
  PARTITION p_init VALUES LESS THAN MAXVALUE
);

CREATE TABLE watch_rule (
  id BIGINT NOT NULL AUTO_INCREMENT,
  rule_name VARCHAR(128) NOT NULL,
  market_hash_name VARCHAR(255) NOT NULL,
  wear_bucket TINYINT NULL,
  float_min DECIMAL(10,8) NULL,
  float_max DECIMAL(10,8) NULL,
  max_price BIGINT NULL COMMENT '心理价位，单位：分',
  discount_pct DECIMAL(5,2) NULL COMMENT '低于近7日基准的折扣阈值，百分比',
  filter_json JSON NULL COMMENT '排除条件：印花、改名、关键词等',
  cooldown_sec INT NOT NULL DEFAULT 600,
  daily_limit INT NOT NULL DEFAULT 20,
  enabled TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_mhn (market_hash_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='监控规则';

CREATE TABLE alert_event (
  id BIGINT NOT NULL AUTO_INCREMENT,
  rule_id BIGINT NOT NULL,
  platform VARCHAR(16) NOT NULL,
  platform_item_id VARCHAR(64) NOT NULL,
  market_hash_name VARCHAR(255) NULL,
  price_amount BIGINT NULL COMMENT '触发时标价，单位：分',
  baseline_price BIGINT NULL COMMENT '近7日基准价，单位：分',
  discount_pct DECIMAL(5,2) NULL,
  deeplink VARCHAR(512) NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'PENDING' COMMENT 'PENDING/SENT/ACK/IGNORED',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_rule_time (rule_id, created_at),
  KEY idx_status_time (status, created_at),
  KEY idx_item_time (platform, platform_item_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='触发事件';

CREATE TABLE fee_config (
  id BIGINT NOT NULL AUTO_INCREMENT,
  platform VARCHAR(16) NOT NULL,
  side VARCHAR(8) NOT NULL COMMENT 'BUY / SELL',
  fee_rate DECIMAL(6,4) NOT NULL COMMENT '0.0250 表示 2.5%',
  fixed_fee BIGINT NOT NULL DEFAULT 0 COMMENT '固定费，单位：分',
  effective_from DATETIME NOT NULL,
  remark VARCHAR(255) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_platform_side_from (platform, side, effective_from)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='费率配置';
