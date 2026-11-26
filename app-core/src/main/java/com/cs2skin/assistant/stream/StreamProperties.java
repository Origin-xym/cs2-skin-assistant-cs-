package com.cs2skin.assistant.stream;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.time.Duration;

@Data
@Component
@ConfigurationProperties(prefix = "cs2.stream")
public class StreamProperties {

    /** Python 侧写入的 Stream 键 */
    private String key = "cs2:listings";

    /** 消费者组名，所有 app-core 实例共用 */
    private String group = "app-core";

    /** 当前实例的消费者名，多实例部署时要唯一 */
    private String consumer = "app-core-1";

    /** 一次最多取多少条 */
    private int batchSize = 10;

    /** XREADGROUP 阻塞等待时长 */
    private Duration blockTimeout = Duration.ofSeconds(5);
}
