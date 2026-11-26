package com.cs2skin.assistant.price;

import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
public class PriceHistoryController {

    private final PriceHistoryService priceHistoryService;

    @GetMapping("/price/history")
    public PriceHistoryResponse history(
            @RequestParam("mhn") String mhn,
            @RequestParam("wearBucket") Integer wearBucket,
            @RequestParam(value = "days", defaultValue = "30") int days) {
        return priceHistoryService.history(mhn.trim(), wearBucket, days);
    }
}
