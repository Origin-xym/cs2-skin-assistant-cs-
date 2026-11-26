package com.cs2skin.assistant.compare;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

public record CompareResponse(
        String marketHashName,
        Integer wearBucket,
        Baseline baseline,
        List<PlatformQuote> platforms,
        Verdict verdict) {

    public record Baseline(Long median7d, int sampleSize, String unit) {
    }

    public record PlatformQuote(
            String platform,
            Long lowestPrice,
            Long netCost,
            BigDecimal floatValue,
            Integer paintSeed,
            boolean hasSticker,
            boolean renamed,
            String sellerHash,
            String deeplink,
            LocalDateTime snapshotAt) {
    }

    public record Verdict(
            String best,
            BigDecimal gapPct,
            BigDecimal discountPct,
            boolean isOpportunity) {
    }
}
