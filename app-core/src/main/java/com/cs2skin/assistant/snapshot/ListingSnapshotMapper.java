package com.cs2skin.assistant.snapshot;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import com.cs2skin.assistant.price.PriceHistoryRow;

import java.time.LocalDateTime;
import java.util.List;


@Mapper
public interface ListingSnapshotMapper extends BaseMapper<ListingSnapshot> {

    /**
     * 唯一键冲突时静默跳过，保证 Stream 重放幂等。
     * 返回 1 表示真插入，0 表示已存在。
     */
    @Insert("""
            INSERT IGNORE INTO listing_snapshot
            (platform, platform_item_id, market_hash_name, wear_bucket, float_value,
             paint_seed, has_sticker, renamed, price_amount, net_cost, currency,
             seller_hash, listed_at, snapshot_at)
            VALUES
            (#{platform}, #{platformItemId}, #{marketHashName}, #{wearBucket}, #{floatValue},
             #{paintSeed}, #{hasSticker}, #{renamed}, #{priceAmount}, #{netCost}, #{currency},
             #{sellerHash}, #{listedAt}, #{snapshotAt})
            """)
    int insertIgnore(ListingSnapshot snapshot);

    @Select("""
            SELECT price FROM (
                SELECT COALESCE(net_cost, price_amount) AS price,
                       ROW_NUMBER() OVER (
                           PARTITION BY platform, platform_item_id
                           ORDER BY snapshot_at DESC
                       ) AS rn
                FROM listing_snapshot
                WHERE market_hash_name = #{mhn}
                  AND wear_bucket = #{wearBucket}
                  AND snapshot_at >= #{since}
                  AND COALESCE(net_cost, price_amount) IS NOT NULL
            ) t
            WHERE rn = 1
            """)
    List<Long> selectLatestPrices(@Param("mhn") String mhn,
                                  @Param("wearBucket") Integer wearBucket,
                                  @Param("since") LocalDateTime since);

    @Select("""
            SELECT id, platform, platform_item_id, market_hash_name, wear_bucket,
                   float_value, paint_seed, has_sticker, renamed, price_amount,
                   net_cost, currency, seller_hash, listed_at, snapshot_at
            FROM (
                SELECT l.*,
                       ROW_NUMBER() OVER (
                           PARTITION BY l.platform, l.platform_item_id
                           ORDER BY l.snapshot_at DESC
                       ) AS rn
                FROM listing_snapshot l
                WHERE l.market_hash_name = #{mhn}
                  AND l.wear_bucket = #{wearBucket}
                  AND l.snapshot_at >= #{since}
            ) t
            WHERE rn = 1
            """)
    List<ListingSnapshot> selectLatestSnapshots(@Param("mhn") String mhn,
                                                @Param("wearBucket") Integer wearBucket,
                                                @Param("since") LocalDateTime since);

    @Select("""
            SELECT DATE(snapshot_at) AS day,
                   price
            FROM (
                SELECT l.*,
                       COALESCE(l.net_cost, l.price_amount) AS price,
                       ROW_NUMBER() OVER (
                           PARTITION BY l.platform, l.platform_item_id, DATE(l.snapshot_at)
                           ORDER BY l.snapshot_at DESC
                       ) AS rn
                FROM listing_snapshot l
                WHERE l.market_hash_name = #{mhn}
                  AND l.wear_bucket = #{wearBucket}
                  AND l.snapshot_at >= #{since}
                  AND COALESCE(l.net_cost, l.price_amount) IS NOT NULL
            ) t
            WHERE rn = 1
            ORDER BY day, price
            """)
    List<PriceHistoryRow> selectDailyLatestPrices(@Param("mhn") String mhn,
                                                  @Param("wearBucket") Integer wearBucket,
                                                  @Param("since") LocalDateTime since);


    @Select("""
            SELECT id, platform, platform_item_id, market_hash_name, wear_bucket,
                   float_value, paint_seed, has_sticker, renamed, price_amount,
                   net_cost, currency, seller_hash, listed_at, snapshot_at
            FROM listing_snapshot
            WHERE platform = #{platform}
              AND platform_item_id = #{itemId}
            ORDER BY snapshot_at DESC
            LIMIT 1
            """)
    ListingSnapshot selectLatestByItem(@Param("platform") String platform,
                                       @Param("itemId") String itemId);



}
