package com.cs2skin.assistant.price;

import com.cs2skin.assistant.snapshot.ListingSnapshotMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

@Service
@RequiredArgsConstructor
public class PriceHistoryService {

    private static final ZoneId CN_ZONE = ZoneId.of("Asia/Shanghai");

    private final ListingSnapshotMapper snapshotMapper;

    public PriceHistoryResponse history(String marketHashName, Integer wearBucket, int days) {
        int normalizedDays = Math.min(90, Math.max(1, days));
        LocalDateTime since = LocalDateTime.now(CN_ZONE).minusDays(normalizedDays);

        List<PriceHistoryRow> rows = snapshotMapper.selectDailyLatestPrices(
                marketHashName, wearBucket, since);

        Map<String, List<Long>> byDay = new TreeMap<>();
        for (PriceHistoryRow row : rows) {
            byDay.computeIfAbsent(row.getDay(), key -> new ArrayList<>())
                    .add(row.getPrice());
        }

        List<PriceHistoryResponse.DailyPoint> points = new ArrayList<>();
        for (Map.Entry<String, List<Long>> entry : byDay.entrySet()) {
            List<Long> prices = entry.getValue();
            prices.sort(Long::compareTo);

            long min = prices.get(0);
            int n = prices.size();
            int mid = n / 2;
            long median = (n % 2 == 1)
                    ? prices.get(mid)
                    : (prices.get(mid - 1) + prices.get(mid)) / 2;

            points.add(new PriceHistoryResponse.DailyPoint(
                    entry.getKey(), min, median, n));
        }

        return new PriceHistoryResponse(
                marketHashName, wearBucket, normalizedDays, points);
    }
}
