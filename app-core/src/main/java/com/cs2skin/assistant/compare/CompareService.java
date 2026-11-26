package com.cs2skin.assistant.compare;

import com.cs2skin.assistant.rule.BaselineService;
import com.cs2skin.assistant.rule.WatchRule;
import com.cs2skin.assistant.rule.WatchRuleService;
import com.cs2skin.assistant.snapshot.ItemMapping;
import com.cs2skin.assistant.snapshot.ItemMappingMapper;
import com.cs2skin.assistant.snapshot.ListingSnapshot;
import com.cs2skin.assistant.snapshot.ListingSnapshotMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class CompareService {

    private static final ZoneId CN_ZONE = ZoneId.of("Asia/Shanghai");

    private final ListingSnapshotMapper snapshotMapper;
    private final BaselineService baselineService;
    private final ItemMappingMapper itemMappingMapper;
    private final WatchRuleService watchRuleService;

    public CompareResponse compare(String marketHashName, Integer wearBucket) {
        LocalDateTime since = LocalDateTime.now(CN_ZONE).minusDays(7);
        List<ListingSnapshot> latest = snapshotMapper.selectLatestSnapshots(
                marketHashName, wearBucket, since);

        Map<String, ListingSnapshot> lowestByPlatform = new HashMap<>();
        for (ListingSnapshot listing : latest) {
            lowestByPlatform.merge(listing.getPlatform(), listing,
                    (a, b) -> cost(a) <= cost(b) ? a : b);
        }

        Map<String, ItemMapping> mappings = new HashMap<>();
        for (String platform : lowestByPlatform.keySet()) {
            mappings.put(platform,
                    itemMappingMapper.selectByPlatformAndMhn(platform, marketHashName));
        }

        List<CompareResponse.PlatformQuote> quotes = lowestByPlatform.values().stream()
                .sorted(Comparator.comparingLong(this::cost))
                .map(listing -> toQuote(listing, mappings.get(listing.getPlatform())))
                .toList();

        BaselineService.BaselineResult baseline =
                baselineService.median7d(marketHashName, wearBucket);

        Long bestCost = quotes.isEmpty() ? null : quotes.get(0).netCost();
        Long secondCost = quotes.size() > 1 ? quotes.get(1).netCost() : null;

        BigDecimal gapPct = bestCost != null && secondCost != null
                ? pct(secondCost - bestCost, bestCost)
                : null;
        BigDecimal discountPct = bestCost != null && baseline.median7d() != null
                ? pct(baseline.median7d() - bestCost, baseline.median7d())
                : null;

        WatchRule rule = watchRuleService.findEnabledFor(marketHashName, wearBucket);
        BigDecimal discountThreshold = rule != null && rule.getDiscountPct() != null
                ? rule.getDiscountPct() : BigDecimal.valueOf(8);
        BigDecimal gapThreshold = rule != null && rule.getRelativeGapPct() != null
                ? rule.getRelativeGapPct() : BigDecimal.valueOf(3);

        boolean opportunity = discountPct != null && gapPct != null
                && discountPct.compareTo(discountThreshold) >= 0
                && gapPct.compareTo(gapThreshold) >= 0;

        String best = quotes.isEmpty() ? null : quotes.get(0).platform();

        return new CompareResponse(
                marketHashName,
                wearBucket,
                new CompareResponse.Baseline(
                        baseline.median7d(), baseline.sampleSize(), "cent"),
                quotes,
                new CompareResponse.Verdict(best, gapPct, discountPct, opportunity));
    }

    private CompareResponse.PlatformQuote toQuote(ListingSnapshot listing, ItemMapping mapping) {
        return new CompareResponse.PlatformQuote(
                listing.getPlatform(),
                listing.getPriceAmount(),
                cost(listing),
                listing.getFloatValue(),
                listing.getPaintSeed(),
                listing.getHasSticker() != null && listing.getHasSticker() == 1,
                listing.getRenamed() != null && listing.getRenamed() == 1,
                listing.getSellerHash(),
                buildDeeplink(listing, mapping),
                listing.getSnapshotAt());
    }

    private long cost(ListingSnapshot listing) {
        return listing.getNetCost() == null
                ? listing.getPriceAmount() : listing.getNetCost();
    }

    private BigDecimal pct(long diff, long base) {
        if (base <= 0) {
            return null;
        }
        return BigDecimal.valueOf(diff)
                .multiply(BigDecimal.valueOf(100))
                .divide(BigDecimal.valueOf(base), 2, RoundingMode.HALF_UP);
    }

    private String buildDeeplink(ListingSnapshot listing, ItemMapping mapping) {
        if (mapping == null || mapping.getPlatformGoodsId() == null) {
            return null;
        }
        String goodsId = mapping.getPlatformGoodsId();
        return switch (listing.getPlatform().toUpperCase(Locale.ROOT)) {
            case "BUFF" -> "https://buff.163.com/goods/" + goodsId + "?from=market";
            case "YOUPIN" -> "https://www.youpin898.com/market/goods-list"
                    + "?listType=10&templateId=" + goodsId + "&gameId=730";
            default -> null;
        };
    }
}
