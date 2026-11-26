package com.cs2skin.assistant.rule;

import com.cs2skin.assistant.snapshot.ItemMapping;
import com.cs2skin.assistant.snapshot.ItemMappingMapper;
import com.cs2skin.assistant.snapshot.ListingSnapshot;
import com.cs2skin.assistant.snapshot.ListingSnapshotMapper;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class RuleEvaluator {

    private static final ZoneId CN_ZONE = ZoneId.of("Asia/Shanghai");

    private final WatchRuleService watchRuleService;
    private final BaselineService baselineService;
    private final ListingSnapshotMapper snapshotMapper;
    private final AlertEventMapper alertEventMapper;
    private final ItemMappingMapper itemMappingMapper;
    private final ObjectMapper objectMapper;
    private final FeishuNotifier feishuNotifier;

    public synchronized EvaluationResult evaluateAll() {
        List<WatchRule> rules = watchRuleService.listByEnabled(true);
        int candidates = 0;
        int inserted = 0;
        int notified = 0;
        int filterSkipped = 0;
        int cooldownSkipped = 0;
        int dailySkipped = 0;
        int relativeSkipped = 0;
        int baselineSkipped = 0;

        LocalDateTime now = LocalDateTime.now(CN_ZONE).withNano(0);
        LocalDateTime dayStart = now.toLocalDate().atStartOfDay();

        for (WatchRule rule : rules) {
            if (rule.getWearBucket() == null) {
                continue;
            }

            BaselineService.BaselineResult baseline =
                    baselineService.median7d(rule.getMarketHashName(), rule.getWearBucket());
            int minSample = rule.getMinSample() == null ? 30 : rule.getMinSample();
            if (baseline.median7d() == null || baseline.sampleSize() < minSample) {
                baselineSkipped++;
                continue;
            }

            List<ListingSnapshot> latest = snapshotMapper.selectLatestSnapshots(
                    rule.getMarketHashName(), rule.getWearBucket(), now.minusDays(7));
            if (latest.isEmpty()) {
                continue;
            }

            FilterConfig filter = parseFilter(rule.getFilterJson());
            Map<String, ItemMapping> mappings = loadMappings(rule, latest);

            List<ListingSnapshot> market = new ArrayList<>();
            
            List<Candidate> eligible = new ArrayList<>();
            for (ListingSnapshot listing : latest) {
                candidates++;

                if (!filterPass(listing, mappings.get(listing.getPlatform()), filter)) {
                    filterSkipped++;
                    continue;
                }
                if (!floatMatches(rule, listing)) {
                    continue;
                }

                market.add(listing);

                long cost = cost(listing);
                if (rule.getMaxPrice() != null && cost > rule.getMaxPrice()) {
                    continue;
                }

                BigDecimal discount = discountPct(baseline.median7d(), cost);
                BigDecimal threshold = rule.getDiscountPct() == null
                        ? BigDecimal.valueOf(8) : rule.getDiscountPct();
                if (discount.compareTo(threshold) < 0) {
                    continue;
                }

                eligible.add(new Candidate(listing, cost, discount));
            }

            if (eligible.isEmpty()) {
                continue;
            }
            eligible.sort(Comparator.comparingLong(Candidate::cost)
                    .thenComparing(c -> c.listing().getPlatformItemId()));

            Map<String, Long> lowestByPlatform = new HashMap<>();
            for (ListingSnapshot listing : market) {
                lowestByPlatform.merge(listing.getPlatform(), cost(listing),
                        (a, b) -> Math.min(a, b));
            }
            List<Long> platformLows = lowestByPlatform.values().stream().sorted().toList();
            if (platformLows.size() < 2) {
                relativeSkipped += eligible.size();
                continue;
            }
            long globalLowest = platformLows.get(0);
            long secondLowest = platformLows.get(1);
            BigDecimal relativeGap = rule.getRelativeGapPct() == null
                    ? BigDecimal.valueOf(3) : rule.getRelativeGapPct();

            int dailyLimit = rule.getDailyLimit() == null ? 20 : rule.getDailyLimit();
            int dailyCount = alertEventMapper.countByRuleSince(rule.getId(), dayStart);
            if (dailyCount >= dailyLimit) {
                dailySkipped++;
                continue;
            }

            for (Candidate candidate : eligible) {
                if (candidate.cost() > globalLowest) {
                    relativeSkipped++;
                    continue;
                }
                if (!relativePass(candidate.cost(), secondLowest, relativeGap)) {
                    relativeSkipped++;
                    continue;
                }

                ListingSnapshot listing = candidate.listing();
                int cooldownSec = rule.getCooldownSec() == null ? 600 : rule.getCooldownSec();
                int recent = alertEventMapper.countByRuleItemSince(
                        rule.getId(), listing.getPlatform(), listing.getPlatformItemId(),
                        now.minusSeconds(cooldownSec));
                if (recent > 0) {
                    cooldownSkipped++;
                    continue;
                }

                if (dailyCount >= dailyLimit) {
                    dailySkipped++;
                    break;
                }

                AlertEvent event = new AlertEvent();
                event.setRuleId(rule.getId());
                event.setPlatform(listing.getPlatform());
                event.setPlatformItemId(listing.getPlatformItemId());
                event.setMarketHashName(listing.getMarketHashName());
                event.setPriceAmount(listing.getPriceAmount());
                event.setBaselinePrice(baseline.median7d());
                event.setDiscountPct(candidate.discount());
                event.setDeeplink(buildDeeplink(listing, mappings.get(listing.getPlatform())));
                event.setStatus("PENDING");
                alertEventMapper.insert(event);

                if (feishuNotifier.send(event, listing)) {
                    event.setStatus("SENT");
                    alertEventMapper.updateById(event);
                    notified++;
                }


                dailyCount++;
                inserted++;
            }
        }

        return new EvaluationResult(rules.size(), candidates, inserted, notified,
                filterSkipped, cooldownSkipped, dailySkipped, relativeSkipped, baselineSkipped);

    }

    private Map<String, ItemMapping> loadMappings(WatchRule rule, List<ListingSnapshot> latest) {
        Map<String, ItemMapping> mappings = new HashMap<>();
        for (ListingSnapshot listing : latest) {
            String platform = listing.getPlatform();
            if (mappings.containsKey(platform)) {
                continue;
            }
            mappings.put(platform,
                    itemMappingMapper.selectByPlatformAndMhn(platform, rule.getMarketHashName()));
        }
        return mappings;
    }

    private FilterConfig parseFilter(String json) {
        if (json == null || json.isBlank()) {
            return new FilterConfig(List.of());
        }
        try {
            JsonNode root = objectMapper.readTree(json);
            JsonNode keywords = root.get("exclude_keywords");
            List<String> list = new ArrayList<>();
            if (keywords != null && keywords.isArray()) {
                for (JsonNode node : keywords) {
                    if (!node.isNull()) {
                        list.add(node.asText());
                    }
                }
            }
            return new FilterConfig(list);
        } catch (Exception e) {
            log.warn("filter_json 解析失败，按空过滤处理：{}", e.getMessage());
            return new FilterConfig(List.of());
        }
    }

    private boolean filterPass(ListingSnapshot listing, ItemMapping mapping, FilterConfig filter) {
        String rawName = mapping == null ? "" : mapping.getRawName();
        String text = listing.getMarketHashName() + " "
                + (rawName == null ? "" : rawName);
        String lower = text.toLowerCase(Locale.ROOT);

        for (String keyword : filter.excludeKeywords()) {
            if (keyword == null || keyword.isBlank()) {
                continue;
            }
            if ("改名".equals(keyword)
                    && listing.getRenamed() != null && listing.getRenamed() == 1) {
                return false;
            }
            if ("刮印花".equals(keyword)) {
                if (lower.contains("刮印花")) {
                    return false;
                }
                continue;
            }
            if (lower.contains(keyword.toLowerCase(Locale.ROOT))) {
                return false;
            }
        }
        return true;
    }

    private boolean floatMatches(WatchRule rule, ListingSnapshot listing) {
        if (rule.getFloatMin() == null && rule.getFloatMax() == null) {
            return true;
        }
        if (listing.getFloatValue() == null) {
            return false;
        }
        if (rule.getFloatMin() != null
                && listing.getFloatValue().compareTo(rule.getFloatMin()) < 0) {
            return false;
        }
        return rule.getFloatMax() == null
                || listing.getFloatValue().compareTo(rule.getFloatMax()) <= 0;
    }

    private long cost(ListingSnapshot listing) {
        return listing.getNetCost() == null
                ? listing.getPriceAmount() : listing.getNetCost();
    }

    private BigDecimal discountPct(long baseline, long cost) {
        if (baseline <= 0) {
            return BigDecimal.ZERO;
        }
        return BigDecimal.valueOf(baseline - cost)
                .multiply(BigDecimal.valueOf(100))
                .divide(BigDecimal.valueOf(baseline), 2, RoundingMode.HALF_UP);
    }

    private boolean relativePass(long cost, long secondLowest, BigDecimal gapPct) {
        if (cost <= 0) {
            return false;
        }
        BigDecimal gap = BigDecimal.valueOf(secondLowest - cost)
                .multiply(BigDecimal.valueOf(100))
                .divide(BigDecimal.valueOf(cost), 4, RoundingMode.HALF_UP);
        return gap.compareTo(gapPct) >= 0;
    }

    private String buildDeeplink(ListingSnapshot listing, ItemMapping mapping) {
        if (mapping == null || mapping.getPlatformGoodsId() == null) {
            return null;
        }
        String goodsId = mapping.getPlatformGoodsId();
        return switch (listing.getPlatform().toUpperCase(Locale.ROOT)) {
            case "BUFF" -> "https://buff.163.com/goods/" + goodsId + "?from=market";
            case "YOUPIN" -> "https://www.youpin898.com/market/goods-list"
                    + "?listType=10&templateId=" + goodsId + "&gameId=730";
            default -> null;
        };
    }

    private record FilterConfig(List<String> excludeKeywords) {
    }

    private record Candidate(ListingSnapshot listing, long cost, BigDecimal discount) {
    }

    public record EvaluationResult(int rules, int candidates, int inserted, int notified,
                                   int filterSkipped, int cooldownSkipped, int dailySkipped,
                                   int relativeSkipped, int baselineSkipped) {
    }

}
