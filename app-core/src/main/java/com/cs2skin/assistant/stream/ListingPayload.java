package com.cs2skin.assistant.stream;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.OffsetDateTime;
import java.util.Map;

/**
 * Python RawListing.model_dump() 的 Java 映射。
 * 字段名是 snake_case，用 JsonNaming 统一转换。
 */
@Data
@NoArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public class ListingPayload {

    private String platform;
    private String platformItemId;
    private long priceAmount;
    private OffsetDateTime fetchedAt;
    private String currency;
    private String marketHashName;
    private String rawName;
    private Double floatValue;
    private Integer paintSeed;
    private String sellerId;
    private OffsetDateTime listedAt;
    private Map<String, Object> raw;
}
