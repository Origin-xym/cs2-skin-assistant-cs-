ALTER TABLE watch_rule
  ADD COLUMN relative_gap_pct DECIMAL(5,2) NOT NULL DEFAULT 3.00
  COMMENT '相对闸：最低到手价比第二低至少高出的百分比'
  AFTER discount_pct;
