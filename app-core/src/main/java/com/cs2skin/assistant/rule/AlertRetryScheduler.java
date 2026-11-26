package com.cs2skin.assistant.rule;

import com.cs2skin.assistant.snapshot.ListingSnapshot;
import com.cs2skin.assistant.snapshot.ListingSnapshotMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.List;

@Slf4j
@Component
@RequiredArgsConstructor
public class AlertRetryScheduler {

    private static final ZoneId CN_ZONE = ZoneId.of("Asia/Shanghai");

    private final AlertEventMapper alertEventMapper;
    private final ListingSnapshotMapper listingSnapshotMapper;
    private final FeishuNotifier feishuNotifier;

    @Scheduled(fixedDelayString = "${cs2.alert.retry-interval-ms:300000}")
    public void retryPending() {
        LocalDateTime since = LocalDateTime.now(CN_ZONE).minusHours(24);
        List<AlertEvent> pending = alertEventMapper.selectPending(since, 20);
        if (pending.isEmpty()) {
            return;
        }

        for (AlertEvent event : pending) {
            ListingSnapshot listing = listingSnapshotMapper.selectLatestByItem(
                    event.getPlatform(), event.getPlatformItemId());
            if (listing == null) {
                log.warn("事件 {} 找不到对应挂单快照，暂不重发", event.getId());
                continue;
            }

            if (feishuNotifier.send(event, listing)) {
                event.setStatus("SENT");
                alertEventMapper.updateById(event);
                log.info("PENDING 事件重发成功：event={} platform={} price={}",
                        event.getId(), event.getPlatform(), event.getPriceAmount());
            }
        }
    }
}
