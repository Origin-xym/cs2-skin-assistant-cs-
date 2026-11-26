package com.cs2skin.assistant.snapshot;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("listing_snapshot")
public class ListingSnapshot {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    private String platform;
    private String platformItemId;
    private String marketHashName;
    private Integer wearBucket;
    private BigDecimal floatValue;
    private Integer paintSeed;
    private Integer hasSticker;
    private Integer renamed;
    private Long priceAmount;
    private Long netCost;
    private String currency;
    private String sellerHash;
    private LocalDateTime listedAt;
    private LocalDateTime snapshotAt;
}
