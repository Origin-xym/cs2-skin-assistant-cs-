package com.cs2skin.assistant.rule;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("watch_rule")
public class WatchRule {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    private String ruleName;
    private String marketHashName;
    private Integer wearBucket;
    private BigDecimal floatMin;
    private BigDecimal floatMax;
    private Long maxPrice;
    private BigDecimal discountPct;
    private BigDecimal relativeGapPct;
    private String filterJson;
    private Integer cooldownSec;
    private Integer dailyLimit;
    private Integer minSample;
    private Integer mergeWindowSec;
    private Integer enabled;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
