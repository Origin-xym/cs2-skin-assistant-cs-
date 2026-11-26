-- 补上设计文档规则模型里有、V1 表结构漏掉的两个字段
ALTER TABLE watch_rule
  ADD COLUMN min_sample INT NOT NULL DEFAULT 30
  COMMENT '基准最少样本数，少于这个数不判定' AFTER daily_limit;

ALTER TABLE watch_rule
  ADD COLUMN merge_window_sec INT NOT NULL DEFAULT 120
  COMMENT '同款多条命中合并窗口，单位秒' AFTER min_sample;

ALTER TABLE watch_rule
  ADD UNIQUE KEY uk_rule_name (rule_name);

-- 当前唯一标的的种子规则；金额单位是分
INSERT IGNORE INTO watch_rule
(rule_name, market_hash_name, wear_bucket, float_min, float_max,
 max_price, discount_pct, filter_json, cooldown_sec, daily_limit,
 min_sample, merge_window_sec, enabled)
VALUES
('AWP 二西莫夫 久经 · 780 元以内蹲',
 'AWP | Asiimov (Field-Tested)',
 3, 0.15000000, 0.38000000,
 78000, 8.00,
 JSON_OBJECT('exclude_keywords', JSON_ARRAY('改名', '刮印花', '租', '押金')),
 600, 20, 30, 120, 1);
