package com.cs2skin.assistant.rule;

import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;

import java.math.BigDecimal;

public record WatchRuleRequest(
        @NotBlank @Size(max = 128) String ruleName,
        @NotBlank @Size(max = 255) String marketHashName,
        @Min(1) @Max(5) Integer wearBucket,
        @DecimalMin("0.0") @DecimalMax("1.0") BigDecimal floatMin,
        @DecimalMin("0.0") @DecimalMax("1.0") BigDecimal floatMax,
        @Positive Long maxPrice,
        @DecimalMin("0.0") @DecimalMax("100.0") BigDecimal discountPct,
        @DecimalMin("0.0") @DecimalMax("100.0") BigDecimal relativeGapPct,
        @Size(max = 2000) String filterJson,
        @Min(0) Integer cooldownSec,
        @Min(0) Integer dailyLimit,
        @Min(1) Integer minSample,
        @Min(0) Integer mergeWindowSec,
        @Min(0) @Max(1) Integer enabled
) {
}
