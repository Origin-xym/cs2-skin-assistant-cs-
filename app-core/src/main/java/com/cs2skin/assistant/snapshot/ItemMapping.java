package com.cs2skin.assistant.snapshot;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("item_mapping")
public class ItemMapping {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    private String marketHashName;
    private String platform;
    private String platformGoodsId;
    private String rawName;
    private Integer wearBucket;
    private Integer statTrak;
    private Integer souvenir;
    private Integer matchLevel;
}
