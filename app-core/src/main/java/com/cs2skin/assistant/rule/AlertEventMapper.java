package com.cs2skin.assistant.rule;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import java.util.List;


import java.time.LocalDateTime;

@Mapper
public interface AlertEventMapper extends BaseMapper<AlertEvent> {

    @Select("""
            SELECT COUNT(*) FROM alert_event
            WHERE rule_id = #{ruleId}
              AND created_at >= #{since}
            """)
    int countByRuleSince(@Param("ruleId") Long ruleId,
                         @Param("since") LocalDateTime since);

    @Select("""
            SELECT COUNT(*) FROM alert_event
            WHERE rule_id = #{ruleId}
              AND platform = #{platform}
              AND platform_item_id = #{itemId}
              AND created_at >= #{since}
            """)
    int countByRuleItemSince(@Param("ruleId") Long ruleId,
                             @Param("platform") String platform,
                             @Param("itemId") String itemId,
                             @Param("since") LocalDateTime since);

    @Select("""
            SELECT * FROM alert_event
            WHERE status = 'PENDING'
              AND created_at >= #{since}
            ORDER BY id ASC
            LIMIT #{limit}
            """)
    List<AlertEvent> selectPending(@Param("since") LocalDateTime since,
                                   @Param("limit") int limit);

}
