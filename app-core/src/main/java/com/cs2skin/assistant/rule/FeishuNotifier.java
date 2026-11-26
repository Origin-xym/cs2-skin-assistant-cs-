package com.cs2skin.assistant.rule;

import com.cs2skin.assistant.snapshot.ListingSnapshot;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class FeishuNotifier {

    private final ObjectMapper objectMapper;

    @Value("${cs2.feishu.webhook:}")
    private String webhook;

    public boolean send(AlertEvent event, ListingSnapshot listing) {
        if (webhook == null || webhook.isBlank()) {
            log.warn("未配置 cs2.feishu.webhook，事件 {} 保持 PENDING", event.getId());
            return false;
        }
        if (listing == null) {
            log.warn("事件 {} 缺少挂单快照，无法生成卡片", event.getId());
            return false;
        }

        try {
            Map<String, Object> payload = buildCard(event, listing);
            String response = RestClient.create()
                    .post()
                    .uri(webhook)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(payload)
                    .retrieve()
                    .body(String.class);

            if (response == null || response.isBlank()) {
                log.error("飞书通知返回空响应，事件 {} 保持 PENDING", event.getId());
                return false;
            }

            JsonNode root = objectMapper.readTree(response);
            int code = root.path("code").asInt(-1);
            if (code != 0) {
                log.error("飞书通知失败：event={} code={} msg={}",
                        event.getId(), code, root.path("msg").asText());
                return false;
            }

            log.info("飞书通知成功：event={} platform={} item={} price={}",
                    event.getId(), event.getPlatform(),
                    event.getPlatformItemId(), event.getPriceAmount());
            return true;
        } catch (Exception e) {
            log.error("飞书通知异常，事件 {} 保持 PENDING：{}",
                    event.getId(), e.getMessage());
            return false;
        }
    }

    private Map<String, Object> buildCard(AlertEvent event, ListingSnapshot listing) {
        List<Map<String, Object>> elements = new ArrayList<>();

        Map<String, Object> div = new LinkedHashMap<>();
        div.put("tag", "div");
        div.put("text", Map.of("tag", "lark_md", "content", body(event, listing)));
        elements.add(div);

        if (event.getDeeplink() != null && !event.getDeeplink().isBlank()) {
            Map<String, Object> button = new LinkedHashMap<>();
            button.put("tag", "button");
            button.put("text", Map.of("tag", "plain_text", "content", "打开平台"));
            button.put("url", event.getDeeplink());
            button.put("type", "primary");

            Map<String, Object> action = new LinkedHashMap<>();
            action.put("tag", "action");
            action.put("actions", List.of(button));
            elements.add(action);
        }

        Map<String, Object> note = new LinkedHashMap<>();
        note.put("tag", "note");
        note.put("elements", List.of(Map.of("tag", "plain_text",
                "content", "人工确认后自行下单，系统不代付；请核对价格、磨损和卖家。")));
        elements.add(note);

        Map<String, Object> header = new LinkedHashMap<>();
        header.put("title", Map.of("tag", "plain_text",
                "content", event.getMarketHashName() + " · " + event.getPlatform()));
        header.put("template", "red");

        Map<String, Object> card = new LinkedHashMap<>();
        card.put("config", Map.of("wide_screen_mode", true));
        card.put("header", header);
        card.put("elements", elements);

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("msg_type", "interactive");
        payload.put("card", card);
        return payload;
    }

    private String body(AlertEvent event, ListingSnapshot listing) {
        long netCost = listing.getNetCost() == null
                ? listing.getPriceAmount() : listing.getNetCost();

        return String.join("\n",
                "**平台** " + event.getPlatform()
                        + " ｜ **挂单** " + event.getPlatformItemId(),
                "**标价** ¥" + yuan(event.getPriceAmount())
                        + " ｜ **到手** ¥" + yuan(netCost),
                "**磨损** " + formatFloat(listing.getFloatValue())
                        + " ｜ **印花** " + flag(listing.getHasSticker())
                        + " ｜ **改名** " + flag(listing.getRenamed()),
                "近 7 日中位 **¥" + yuan(event.getBaselinePrice())
                        + "**，低 **" + formatPct(event.getDiscountPct()) + "**");
    }

    private String yuan(Long cents) {
        if (cents == null) {
            return "-";
        }
        return String.format(Locale.ROOT, "%.2f", cents / 100.0);
    }

    private String formatFloat(BigDecimal value) {
        return value == null
                ? "-" : value.setScale(4, RoundingMode.HALF_UP).toPlainString();
    }

    private String formatPct(BigDecimal value) {
        return value == null
                ? "-" : value.setScale(2, RoundingMode.HALF_UP).toPlainString() + "%";
    }

    private String flag(Integer value) {
        return value != null && value == 1 ? "有" : "无";
    }
}
