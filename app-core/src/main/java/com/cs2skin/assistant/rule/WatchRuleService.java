package com.cs2skin.assistant.rule;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.math.BigDecimal;
import java.util.List;

@Service
@RequiredArgsConstructor
public class WatchRuleService {

    private final WatchRuleMapper mapper;
    private final ObjectMapper objectMapper;

    public List<WatchRule> listAll() {
        return mapper.selectList(
                new LambdaQueryWrapper<WatchRule>().orderByAsc(WatchRule::getId));
    }

    public List<WatchRule> listByEnabled(boolean enabled) {
        return mapper.selectList(
                new LambdaQueryWrapper<WatchRule>()
                        .eq(WatchRule::getEnabled, enabled ? 1 : 0)
                        .orderByAsc(WatchRule::getId));
    }

    public WatchRule findEnabledFor(String marketHashName, Integer wearBucket) {
        List<WatchRule> rules = mapper.selectList(
                new LambdaQueryWrapper<WatchRule>()
                        .eq(WatchRule::getMarketHashName, marketHashName)
                        .eq(wearBucket != null, WatchRule::getWearBucket, wearBucket)
                        .eq(WatchRule::getEnabled, 1)
                        .orderByAsc(WatchRule::getId));
        return rules.isEmpty() ? null : rules.get(0);
    }

    @Transactional
    public WatchRule create(WatchRuleRequest request) {
        WatchRule rule = new WatchRule();
        applyRequest(rule, request);
        try {
            mapper.insert(rule);
        } catch (DuplicateKeyException exception) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "规则名称已存在");
        }
        return rule;
    }

    @Transactional
    public WatchRule update(Long id, WatchRuleRequest request) {
        WatchRule rule = requireRule(id);
        applyRequest(rule, request);
        try {
            mapper.updateById(rule);
        } catch (DuplicateKeyException exception) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "规则名称已存在");
        }
        return rule;
    }

    @Transactional
    public WatchRule toggle(Long id) {
        WatchRule rule = requireRule(id);
        rule.setEnabled(rule.getEnabled() != null && rule.getEnabled() == 1 ? 0 : 1);
        mapper.updateById(rule);
        return rule;
    }

    private void applyRequest(WatchRule rule, WatchRuleRequest request) {
        if (request.floatMin() != null && request.floatMax() != null
                && request.floatMin().compareTo(request.floatMax()) >= 0) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST, "floatMin 必须小于 floatMax");
        }

        rule.setRuleName(request.ruleName().trim());
        rule.setMarketHashName(request.marketHashName().trim());
        rule.setWearBucket(request.wearBucket() == null ? 3 : request.wearBucket());
        rule.setFloatMin(request.floatMin());
        rule.setFloatMax(request.floatMax());
        rule.setMaxPrice(request.maxPrice());
        rule.setDiscountPct(request.discountPct() == null
                ? BigDecimal.valueOf(8) : request.discountPct());
        rule.setRelativeGapPct(request.relativeGapPct() == null
                ? BigDecimal.valueOf(3) : request.relativeGapPct());
        rule.setFilterJson(normalizeFilterJson(request.filterJson()));
        rule.setCooldownSec(request.cooldownSec() == null ? 600 : request.cooldownSec());
        rule.setDailyLimit(request.dailyLimit() == null ? 20 : request.dailyLimit());
        rule.setMinSample(request.minSample() == null ? 30 : request.minSample());
        rule.setMergeWindowSec(request.mergeWindowSec() == null
                ? 120 : request.mergeWindowSec());
        rule.setEnabled(request.enabled() == null ? 1 : request.enabled());
    }

    private String normalizeFilterJson(String raw) {
        if (raw == null || raw.isBlank()) {
            return "{}";
        }
        try {
            objectMapper.readTree(raw);
        } catch (JsonProcessingException exception) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST, "filterJson 必须是合法 JSON");
        }
        return raw;
    }

    private WatchRule requireRule(Long id) {
        WatchRule rule = mapper.selectById(id);
        if (rule == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "规则不存在: " + id);
        }
        return rule;
    }
}
