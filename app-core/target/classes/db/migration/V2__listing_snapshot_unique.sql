-- 同一条挂单的同一采集时刻只允许一行，保证消息重放幂等。
-- 分区表要求唯一键包含分区列 snapshot_at，这里正好包含。
ALTER TABLE listing_snapshot
  ADD UNIQUE KEY uk_item_snapshot (platform, platform_item_id, snapshot_at);
