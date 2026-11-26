package com.cs2skin.assistant.rule;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@RequiredArgsConstructor
public class RuleScheduler {

    private final RuleEvaluator ruleEvaluator;

    @Scheduled(fixedDelayString = "${cs2.rule.evaluate-interval-ms:60000}")
    public void evaluate() {
        try {
            RuleEvaluator.EvaluationResult result = ruleEvaluator.evaluateAll();
            if (result.inserted() > 0) {
                log.info("定时规则评估：{}", result);
            } else {
                log.debug("定时规则评估：{}", result);
            }
        } catch (Exception e) {
            log.error("定时规则评估失败", e);
        }
    }
}
