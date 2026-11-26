package com.cs2skin.assistant.compare;

import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
public class CompareController {

    private final CompareService compareService;

    @GetMapping("/compare")
    public CompareResponse compare(
            @RequestParam("mhn") String mhn,
            @RequestParam("wearBucket") Integer wearBucket) {
        return compareService.compare(mhn.trim(), wearBucket);
    }
}
