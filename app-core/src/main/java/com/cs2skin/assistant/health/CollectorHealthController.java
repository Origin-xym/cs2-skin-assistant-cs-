package com.cs2skin.assistant.health;

import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/health")
@RequiredArgsConstructor
public class CollectorHealthController {

    private final CollectorHealthService healthService;

    @GetMapping("/collectors")
    public CollectorHealthService.CollectorHealth collectors() {
        return healthService.health();
    }
}
