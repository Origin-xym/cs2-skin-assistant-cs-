package com.cs2skin.assistant.stream;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.cs2skin.assistant.snapshot.SnapshotPersistService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.SmartLifecycle;
import org.springframework.data.redis.RedisSystemException;
import org.springframework.data.redis.connection.stream.Consumer;
import org.springframework.data.redis.connection.stream.MapRecord;
import org.springframework.data.redis.connection.stream.ReadOffset;
import org.springframework.data.redis.connection.stream.StreamOffset;
import org.springframework.data.redis.connection.stream.StreamReadOptions;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;

@Slf4j
@Component
@RequiredArgsConstructor
public class RedisStreamConsumer implements SmartLifecycle {

    private final StringRedisTemplate redis;
    private final StreamProperties properties;
    private final ObjectMapper objectMapper;
    private final SnapshotPersistService persistService;

    private final AtomicBoolean running = new AtomicBoolean(false);
    private volatile boolean groupReady = false;
    private Thread worker;

    @Override
    public void start() {
        if (!running.compareAndSet(false, true)) {
            return;
        }
        worker = new Thread(this::loop, "redis-stream-consumer");
        worker.start();
        log.info("Redis Stream 消费者启动：key={} group={} consumer={}",
                properties.getKey(), properties.getGroup(), properties.getConsumer());
    }

    @Override
    public void stop() {
        running.set(false);
        if (worker != null) {
            worker.interrupt();
            try {
                worker.join(5000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
        log.info("Redis Stream 消费者已停止");
    }

    @Override
    public boolean isRunning() {
        return running.get();
    }

    @Override
    public boolean isAutoStartup() {
        return true;
    }

    @Override
    public int getPhase() {
        return Integer.MAX_VALUE;
    }

    private void loop() {
        while (running.get()) {
            try {
                if (!groupReady) {
                    groupReady = ensureGroup();
                    if (!groupReady) {
                        sleep(Duration.ofSeconds(3));
                        continue;
                    }
                }

                List<MapRecord<String, Object, Object>> records = redis.opsForStream().read(
                        Consumer.from(properties.getGroup(), properties.getConsumer()),
                        StreamReadOptions.empty()
                                .count(properties.getBatchSize())
                                .block(properties.getBlockTimeout()),
                        StreamOffset.create(properties.getKey(), ReadOffset.lastConsumed())
                );
                if (records == null || records.isEmpty()) {
                    continue;
                }
                for (MapRecord<String, Object, Object> record : records) {
                    handle(record);
                }
            } catch (RedisSystemException e) {
                String message = errorMessage(e);
                if (message != null && message.contains("NOGROUP")) {
                    groupReady = false;
                    log.warn("消费者组丢失，准备重建：{}", message);
                } else {
                    log.error("Redis Stream 消费异常：" + message, e);
                }
                sleep(Duration.ofSeconds(3));
            } catch (Exception e) {
                log.error("Redis Stream 消费异常", e);
                sleep(Duration.ofSeconds(3));
            }
        }
    }

    private boolean ensureGroup() {
        if (!Boolean.TRUE.equals(redis.hasKey(properties.getKey()))) {
            log.info("Stream {} 还不存在，等待 Python 采集器写入", properties.getKey());
            return false;
        }
        try {
            redis.opsForStream().createGroup(
                    properties.getKey(), ReadOffset.from("0"), properties.getGroup());
            log.info("已创建消费者组 {}（从 0 开始消费）", properties.getGroup());
        } catch (RedisSystemException e) {
            String message = errorMessage(e);
            if (message != null && message.contains("BUSYGROUP")) {
                log.info("消费者组 {} 已存在", properties.getGroup());
            } else {
                throw e;
            }
        }
        return true;
    }

    private void handle(MapRecord<String, Object, Object> record) {
        Map<Object, Object> fields = record.getValue();
        Object payloadField = fields.get("payload");
        if (payloadField == null) {
            log.warn("消息 {} 缺少 payload 字段，留在 pending", record.getId());
            return;
        }

        String goodsId = fields.get("goods_id") == null
                ? null : fields.get("goods_id").toString();

        ListingPayload payload;
        try {
            payload = objectMapper.readValue(
                    payloadField.toString(), ListingPayload.class);
        } catch (JsonProcessingException e) {
            log.error("消息 {} 的 payload 解析失败，留在 pending：{}",
                    record.getId(), e.getMessage());
            return;
        }

        int rows;
        try {
            rows = persistService.persist(payload, goodsId);
        } catch (Exception e) {
            log.error("消息 {} 落库失败，留在 pending", record.getId(), e);
            return;
        }

        log.info("[{}] {} | item={} | price={} 分 | float={} | seed={} | rows={} | streamId={}",
                payload.getPlatform(),
                payload.getMarketHashName(),
                payload.getPlatformItemId(),
                payload.getPriceAmount(),
                payload.getFloatValue(),
                payload.getPaintSeed(),
                rows,
                record.getId());


        redis.opsForStream().acknowledge(
                properties.getKey(), properties.getGroup(), record.getId());
    }

    private void sleep(Duration duration) {
        try {
            Thread.sleep(duration.toMillis());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            running.set(false);
        }
    }

    private String errorMessage(Throwable throwable) {
        Throwable cause = throwable.getCause();
        return cause != null ? cause.getMessage() : throwable.getMessage();
    }
}
