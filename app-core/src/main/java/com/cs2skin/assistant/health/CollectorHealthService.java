package com.cs2skin.assistant.health;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.cs2skin.assistant.stream.StreamProperties;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.connection.stream.StreamInfo;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class CollectorHealthService {

    private static final ZoneId CN_ZONE = ZoneId.of("Asia/Shanghai");
    private static final List<String> PLATFORMS = List.of("BUFF", "YOUPIN");
    private static final long DEFAULT_TTL_SEC = 180;

    private final StringRedisTemplate redis;
    private final StreamProperties streamProperties;
    private final ObjectMapper objectMapper;

    public CollectorHealth health() {
        StreamStatus stream = readStream();
        List<CollectorStatus> collectors = PLATFORMS.stream()
                .map(this::readCollector)
                .toList();

        long up = collectors.stream()
                .filter(item -> "UP".equals(item.status()))
                .count();
        String status = up == collectors.size()
                ? "UP"
                : up == 0 ? "DOWN" : "DEGRADED";

        return new CollectorHealth(
                status, stream, collectors, OffsetDateTime.now(CN_ZONE));
    }

    private StreamStatus readStream() {
        long length = 0;
        String lastEntryId = null;
        OffsetDateTime lastEntryAt = null;
        long pending = 0;

        try {
            StreamInfo.XInfoStream info =
                    redis.opsForStream().info(streamProperties.getKey());
            if (info != null) {
                length = info.streamLength();
                lastEntryId = info.lastEntryId();
                lastEntryAt = parseStreamId(lastEntryId);
            }
        } catch (Exception exception) {
            log.warn("读取 Stream 信息失败：{}", exception.getMessage());
        }

        try {
            StreamInfo.XInfoGroups groups =
                    redis.opsForStream().groups(streamProperties.getKey());
            if (groups != null) {
                for (StreamInfo.XInfoGroup group : groups) {
                    if (streamProperties.getGroup().equals(group.groupName())) {
                        pending = group.pendingCount() == null
                                ? 0 : group.pendingCount();
                        break;
                    }
                }
            }
        } catch (Exception exception) {
            log.warn("读取消费者组信息失败：{}", exception.getMessage());
        }

        return new StreamStatus(
                streamProperties.getKey(),
                length,
                lastEntryId,
                lastEntryAt,
                pending,
                streamProperties.getGroup());
    }

    private CollectorStatus readCollector(String platform) {
        String key = "collector:heartbeat:" + platform;
        String json;
        try {
            json = redis.opsForValue().get(key);
        } catch (Exception exception) {
            log.warn("读取 {} 心跳失败：{}", platform, exception.getMessage());
            return new CollectorStatus(
                    platform, "UNKNOWN", null, null,
                    null, null, null, null, "Redis 读取失败");
        }

        if (json == null || json.isBlank()) {
            return new CollectorStatus(
                    platform, "DOWN", null, null,
                    null, null, null, null, "心跳不存在");
        }

        try {
            Map<String, Object> map = objectMapper.readValue(
                    json, new TypeReference<Map<String, Object>>() {});
            OffsetDateTime at = OffsetDateTime.parse(
                    String.valueOf(map.get("at")));
            long ttl = toLong(map.get("ttl_sec"), DEFAULT_TTL_SEC);
            long age = Math.max(0,
                    Duration.between(at, OffsetDateTime.now(CN_ZONE)).getSeconds());
            String status = age <= ttl ? "UP" : "STALE";

            return new CollectorStatus(
                    platform,
                    status,
                    at,
                    age,
                    toInt(map.get("items")),
                    toInt(map.get("written")),
                    toInt(map.get("skipped")),
                    toInt(map.get("errors")),
                    String.valueOf(map.getOrDefault("summary", "")));
        } catch (Exception exception) {
            log.warn("{} 心跳解析失败：{}", platform, exception.getMessage());
            return new CollectorStatus(
                    platform, "UNKNOWN", null, null,
                    null, null, null, null, "心跳解析失败");
        }
    }

    private OffsetDateTime parseStreamId(String id) {
        if (id == null || id.isBlank() || "0-0".equals(id)) {
            return null;
        }
        try {
            long millis = Long.parseLong(id.split("-")[0]);
            if (millis <= 0) {
                return null;
            }
            return Instant.ofEpochMilli(millis)
                    .atZone(CN_ZONE)
                    .toOffsetDateTime();
        } catch (NumberFormatException exception) {
            return null;
        }
    }

    private long toLong(Object value, long fallback) {
        if (value instanceof Number number) {
            return number.longValue();
        }
        if (value == null) {
            return fallback;
        }
        try {
            return Long.parseLong(value.toString());
        } catch (NumberFormatException exception) {
            return fallback;
        }
    }

    private Integer toInt(Object value) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        if (value == null) {
            return null;
        }
        try {
            return Integer.parseInt(value.toString());
        } catch (NumberFormatException exception) {
            return null;
        }
    }

    public record CollectorHealth(
            String status,
            StreamStatus stream,
            List<CollectorStatus> collectors,
            OffsetDateTime checkedAt) {
    }

    public record StreamStatus(
            String key,
            long length,
            String lastEntryId,
            OffsetDateTime lastEntryAt,
            long pending,
            String group) {
    }

    public record CollectorStatus(
            String platform,
            String status,
            OffsetDateTime lastHeartbeatAt,
            Long ageSeconds,
            Integer items,
            Integer written,
            Integer skipped,
            Integer errors,
            String summary) {
    }
}
