package com.cs2skin.assistant.rule;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/v1/alerts")
@RequiredArgsConstructor
public class AlertController {

    private final AlertEventMapper alertEventMapper;

    @GetMapping
    public List<AlertEvent> list() {
        return alertEventMapper.selectList(
                new LambdaQueryWrapper<AlertEvent>()
                        .orderByDesc(AlertEvent::getId)
                        .last("LIMIT 20"));
    }

    @PatchMapping("/{id}/ack")
    public AlertEvent ack(@PathVariable Long id) {
        AlertEvent event = alertEventMapper.selectById(id);
        if (event == null) {
            throw new IllegalArgumentException("alert not found: " + id);
        }
        event.setStatus("ACK");
        alertEventMapper.updateById(event);
        return event;
    }
}
