package com.pipeline.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.pipeline.model.ActivityEvent;
import com.pipeline.model.LogEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.BatchPreparedStatementSetter;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class DataService {

    private final JdbcTemplate jdbcTemplate;
    // private final KafkaProducerService kafkaProducerService;
    private final ObjectMapper objectMapper;

    private String toJson(Object obj) {
        if (obj == null) return "{}";
        try {
            return objectMapper.writeValueAsString(obj);
        } catch (JsonProcessingException e) {
            return "{}";
        }
    }

    @Transactional
    public void processLog(LogEvent logEvent) {
        String sql = "INSERT INTO logs (timestamp, level, service, host, message, metadata, created_at) " +
                "VALUES (?, ?, ?, ?, ?, ?::jsonb, NOW())";

        jdbcTemplate.update(sql,
                logEvent.getTimestamp().toEpochMilli() / 1000.0,
                logEvent.getLevel(),
                logEvent.getService(),
                logEvent.getHost(),
                logEvent.getMessage(),
                toJson(logEvent.getMetadata())
        );

        // kafkaProducerService.sendLogAsync(logEvent);
    }

    @Transactional
    public void processLogs(List<LogEvent> logEvents) {
        String sql = "INSERT INTO logs (timestamp, level, service, host, message, metadata, created_at) " +
                "VALUES (?, ?, ?, ?, ?, ?::jsonb, NOW())";

        jdbcTemplate.batchUpdate(sql, new BatchPreparedStatementSetter() {
            @Override
            public void setValues(PreparedStatement ps, int i) throws SQLException {
                LogEvent event = logEvents.get(i);
                ps.setDouble(1, event.getTimestamp().toEpochMilli() / 1000.0);
                ps.setString(2, event.getLevel());
                ps.setString(3, event.getService());
                ps.setString(4, event.getHost());
                ps.setString(5, event.getMessage());
                ps.setString(6, toJson(event.getMetadata()));
            }

            @Override
            public int getBatchSize() {
                return logEvents.size();
            }
        });

        log.debug("Batch inserted {} logs", logEvents.size());
        // kafkaProducerService.sendLogsAsync(logEvents);
    }

    @Transactional
    public void processActivity(ActivityEvent activityEvent) {
        String sql = "INSERT INTO events (event_id, timestamp, user_id, session_id, event_type, event_data, device, created_at) " +
                "VALUES (?, ?, ?, ?, ?, ?::jsonb, ?::jsonb, NOW())";

        jdbcTemplate.update(sql,
                activityEvent.getEventId(),
                activityEvent.getTimestamp().toEpochMilli() / 1000.0,
                activityEvent.getUserId(),
                activityEvent.getSessionId(),
                activityEvent.getEventType(),
                toJson(activityEvent.getEventData()),
                toJson(activityEvent.getDevice())
        );

        // kafkaProducerService.sendActivityAsync(activityEvent);
    }

    @Transactional
    public void processActivities(List<ActivityEvent> activityEvents) {
        String sql = "INSERT INTO events (event_id, timestamp, user_id, session_id, event_type, event_data, device, created_at) " +
                "VALUES (?, ?, ?, ?, ?, ?::jsonb, ?::jsonb, NOW())";

        jdbcTemplate.batchUpdate(sql, new BatchPreparedStatementSetter() {
            @Override
            public void setValues(PreparedStatement ps, int i) throws SQLException {
                ActivityEvent event = activityEvents.get(i);
                ps.setString(1, event.getEventId());
                ps.setDouble(2, event.getTimestamp().toEpochMilli() / 1000.0);
                ps.setString(3, event.getUserId());
                ps.setString(4, event.getSessionId());
                ps.setString(5, event.getEventType());
                ps.setString(6, toJson(event.getEventData()));
                ps.setString(7, toJson(event.getDevice()));
            }

            @Override
            public int getBatchSize() {
                return activityEvents.size();
            }
        });

        log.debug("Batch inserted {} events", activityEvents.size());
        // kafkaProducerService.sendActivitiesAsync(activityEvents);
    }
}