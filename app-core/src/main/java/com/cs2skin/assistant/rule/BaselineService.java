package com.cs2skin.assistant.rule;

import com.cs2skin.assistant.snapshot.ListingSnapshotMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.List;

@Service
@RequiredArgsConstructor
public class BaselineService {

    private static final ZoneId CN_ZONE = ZoneId.of("Asia/Shanghai");

    private final ListingSnapshotMapper mapper;

    public BaselineResult median7d(String marketHashName, Integer wearBucket) {
        LocalDateTime since = LocalDateTime.now(CN_ZONE).minusDays(7);
        List<Long> prices = mapper.selectLatestPrices(marketHashName, wearBucket, since);
        if (prices == null || prices.isEmpty()) {
            return new BaselineResult(marketHashName, wearBucket, null, 0);
        }

        prices.sort(Long::compareTo);
        int n = prices.size();
        int mid = n / 2;
        long median = (n % 2 == 1)
                ? prices.get(mid)
                : (prices.get(mid - 1) + prices.get(mid)) / 2;

        return new BaselineResult(marketHashName, wearBucket, median, n);
    }

    public record BaselineResult(String marketHashName,
                                 Integer wearBucket,
                                 Long median7d,
                                 int sampleSize) {
    }
}
