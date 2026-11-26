package com.cs2skin.assistant.rule;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
public class RuleController {

    private final WatchRuleService watchRuleService;
    private final BaselineService baselineService;
    private final RuleEvaluator ruleEvaluator;

    @GetMapping("/rules")
    public List<WatchRule> rules(
            @RequestParam(value = "enabled", required = false) Boolean enabled) {
        if (enabled == null) {
            return watchRuleService.listAll();
        }
        return watchRuleService.listByEnabled(enabled);
    }

    @PostMapping("/rules")
    @ResponseStatus(HttpStatus.CREATED)
    public WatchRule create(@Valid @RequestBody WatchRuleRequest request) {
        return watchRuleService.create(request);
    }

    @PutMapping("/rules/{id}")
    public WatchRule update(@PathVariable Long id,
                            @Valid @RequestBody WatchRuleRequest request) {
        return watchRuleService.update(id, request);
    }

    @PatchMapping("/rules/{id}/toggle")
    public WatchRule toggle(@PathVariable Long id) {
        return watchRuleService.toggle(id);
    }

    @GetMapping("/baseline")
    public BaselineService.BaselineResult baseline(
            @RequestParam("mhn") String mhn,
            @RequestParam("wearBucket") Integer wearBucket) {
        return baselineService.median7d(mhn.trim(), wearBucket);
    }

    @PostMapping("/evaluate")
    public RuleEvaluator.EvaluationResult evaluate() {
        return ruleEvaluator.evaluateAll();
    }
}
