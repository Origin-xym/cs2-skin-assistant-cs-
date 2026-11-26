package com.cs2skin.assistant.rule;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("alert_event")
public class AlertEvent {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    private Long ruleId;
    private String platform;
    private String platformItemId;
    private String marketHashName;
    private Long priceAmount;
    private Long baselinePrice;
    private BigDecimal discountPct;
    private String deeplink;
    private String status;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
