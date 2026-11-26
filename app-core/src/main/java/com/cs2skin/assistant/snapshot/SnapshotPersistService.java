package com.cs2skin.assistant.snapshot;

import com.cs2skin.assistant.stream.ListingPayload;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class SnapshotPersistService {

    private static final ZoneId CN_ZONE = ZoneId.of("Asia/Shanghai");

    private final ListingSnapshotMapper mapper;
    private final ItemMappingMapper itemMappingMapper;

    /**
     * 落一条 listing_snapshot，并顺手补 item_mapping。
     * 返回 1 表示快照新插入，0 表示唯一键已存在（重放）。
     */
    @Transactional
    public int persist(ListingPayload payload, String goodsId) {
        if (payload.getPlatform() == null || payload.getPlatform().isBlank()
                || payload.getPlatformItemId() == null || payload.getPlatformItemId().isBlank()
                || payload.getMarketHashName() == null || payload.getMarketHashName().isBlank()) {
            throw new IllegalArgumentException(
                    "payload 缺少 platform / platform_item_id / market_hash_name");
        }

        String platform = payload.getPlatform().toUpperCase(Locale.ROOT);
        String resolvedGoodsId = resolveGoodsId(payload, goodsId);
        if (resolvedGoodsId == null || resolvedGoodsId.isBlank()) {
            throw new IllegalArgumentException("payload 缺少 goods_id，无法写 item_mapping");
        }

        ListingSnapshot entity = new ListingSnapshot();
        entity.setPlatform(platform);
        entity.setPlatformItemId(payload.getPlatformItemId());
        entity.setMarketHashName(payload.getMarketHashName());
        entity.setWearBucket(wearBucket(payload.getFloatValue()));
        entity.setFloatValue(payload.getFloatValue() == null
                ? null : BigDecimal.valueOf(payload.getFloatValue()));
        entity.setPaintSeed(payload.getPaintSeed());
        entity.setHasSticker(hasSticker(payload));
        entity.setRenamed(renamed(payload));
        entity.setPriceAmount(payload.getPriceAmount());
        entity.setNetCost(null);
        entity.setCurrency(payload.getCurrency() == null ? "CNY" : payload.getCurrency());
        entity.setSellerHash(payload.getSellerId());
        entity.setListedAt(toLocal(payload.getListedAt()));

        OffsetDateTime fetchedAt = payload.getFetchedAt() == null
                ? OffsetDateTime.now() : payload.getFetchedAt();
        entity.setSnapshotAt(toLocal(fetchedAt));

        int inserted = mapper.insertIgnore(entity);

        ItemMapping mapping = new ItemMapping();
        mapping.setMarketHashName(payload.getMarketHashName());
        mapping.setPlatform(platform);
        mapping.setPlatformGoodsId(resolvedGoodsId);
        mapping.setRawName(payload.getRawName());
        mapping.setWearBucket(entity.getWearBucket());
        mapping.setStatTrak(isStatTrak(payload) ? 1 : 0);
        mapping.setSouvenir(isSouvenir(payload) ? 1 : 0);
        mapping.setMatchLevel(1);
        itemMappingMapper.upsert(mapping);

        return inserted;
    }

    private String resolveGoodsId(ListingPayload payload, String goodsId) {
        if (goodsId != null && !goodsId.isBlank()) {
            return goodsId.trim();
        }
        Map<String, Object> raw = payload.getRaw();
        if (raw == null || raw.isEmpty()) {
            return null;
        }
        Object value = raw.get("goods_id");
        if (value == null) {
            value = raw.get("templateId");
        }
        if (value == null) {
            value = raw.get("productId");
        }
        return value == null ? null : String.valueOf(value);
    }

    private boolean isStatTrak(ListingPayload payload) {
        return nameText(payload).toLowerCase(Locale.ROOT).contains("stattrak");
    }

    private boolean isSouvenir(ListingPayload payload) {
        String text = nameText(payload);
        return text.toLowerCase(Locale.ROOT).contains("souvenir")
                || text.contains("纪念品");
    }

    private String nameText(ListingPayload payload) {
        String rawName = payload.getRawName() == null ? "" : payload.getRawName();
        return payload.getMarketHashName() + " " + rawName;
    }

    private Integer wearBucket(Double value) {
        if (value == null || value < 0.0 || value > 1.0) {
            return null;
        }
        if (value < 0.07) {
            return 1;
        }
        if (value < 0.15) {
            return 2;
        }
        if (value < 0.38) {
            return 3;
        }
        if (value < 0.45) {
            return 4;
        }
        return 5;
    }

    private int hasSticker(ListingPayload payload) {
        Map<String, Object> raw = payload.getRaw();
        if (raw == null || raw.isEmpty()) {
            return 0;
        }
        if ("YOUPIN".equalsIgnoreCase(payload.getPlatform())) {
            return toInt(raw.get("haveSticker")) > 0 ? 1 : 0;
        }
        Object asset = raw.get("asset_info");
        if (asset instanceof Map<?, ?> assetMap) {
            Object info = assetMap.get("info");
            if (info instanceof Map<?, ?> infoMap) {
                Object stickers = infoMap.get("stickers");
                if (stickers instanceof List<?> list && !list.isEmpty()) {
                    return 1;
                }
            }
        }
        return 0;
    }

    private int renamed(ListingPayload payload) {
        Map<String, Object> raw = payload.getRaw();
        if (raw == null || raw.isEmpty()) {
            return 0;
        }
        if ("YOUPIN".equalsIgnoreCase(payload.getPlatform())) {
            return toInt(raw.get("haveNameTag")) > 0 ? 1 : 0;
        }
        Object asset = raw.get("asset_info");
        if (asset instanceof Map<?, ?> assetMap) {
            Object info = assetMap.get("info");
            if (info instanceof Map<?, ?> infoMap) {
                Object warnings = infoMap.get("fraudwarnings");
                if (warnings instanceof List<?> list) {
                    for (Object item : list) {
                        if (isRenameText(String.valueOf(item))) {
                            return 1;
                        }
                    }
                    return 0;
                }
                if (warnings != null && isRenameText(String.valueOf(warnings))) {
                    return 1;
                }
            }
        }
        return 0;
    }

    private boolean isRenameText(String value) {
        String lower = value.toLowerCase(Locale.ROOT);
        return lower.contains("name tag")
                || value.contains("名称标签")
                || value.contains("改名");
    }

    private int toInt(Object value) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        if (value == null) {
            return 0;
        }
        try {
            return Integer.parseInt(value.toString());
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    private LocalDateTime toLocal(OffsetDateTime value) {
        if (value == null) {
            return null;
        }
        // 截到秒，和 MySQL DATETIME 的精度一致，重放时唯一键才稳定
        return value.atZoneSameInstant(CN_ZONE).toLocalDateTime().withNano(0);
    }
}
