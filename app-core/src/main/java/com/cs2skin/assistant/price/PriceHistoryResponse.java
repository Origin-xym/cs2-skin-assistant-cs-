package com.cs2skin.assistant.price;

import java.util.List;

public record PriceHistoryResponse(
        String marketHashName,
        Integer wearBucket,
        int days,
        List<DailyPoint> points) {

    public record DailyPoint(
            String date,
            Long minPrice,
            Long medianPrice,
            int sampleSize) {
    }
}
