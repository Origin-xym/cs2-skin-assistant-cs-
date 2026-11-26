package com.cs2skin.assistant.snapshot;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface ItemMappingMapper extends BaseMapper<ItemMapping> {

    /**
     * (platform, platform_goods_id) 唯一键冲突时更新名称和属性。
     * 返回 1 表示新插入，2 表示更新，0 表示值没变。
     */
    @Insert("""
            INSERT INTO item_mapping
            (market_hash_name, platform, platform_goods_id, raw_name,
             wear_bucket, stat_trak, souvenir, match_level)
            VALUES
            (#{marketHashName}, #{platform}, #{platformGoodsId}, #{rawName},
             #{wearBucket}, #{statTrak}, #{souvenir}, #{matchLevel})
            ON DUPLICATE KEY UPDATE
              market_hash_name = #{marketHashName},
              raw_name = #{rawName},
              wear_bucket = #{wearBucket},
              stat_trak = #{statTrak},
              souvenir = #{souvenir},
              match_level = #{matchLevel}
            """)
    int upsert(ItemMapping mapping);

    @Select("""
            SELECT * FROM item_mapping
            WHERE platform = #{platform}
              AND market_hash_name = #{mhn}
            ORDER BY id
            LIMIT 1
            """)
    ItemMapping selectByPlatformAndMhn(@Param("platform") String platform,
                                       @Param("mhn") String mhn);

}
