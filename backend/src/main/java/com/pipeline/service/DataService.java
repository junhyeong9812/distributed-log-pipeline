package com.pipeline.service;

import com.pipeline.entity.EventEntity;
import com.pipeline.entity.LogEntity;
import com.pipeline.model.ActivityEvent;
import com.pipeline.model.LogEvent;
import com.pipeline.repository.EventRepository;
import com.pipeline.repository.LogRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class DataService {

    private final LogRepository logRepository;
    private final EventRepository eventRepository;
    private final KafkaProducerService kafkaProducerService;

    @Transactional
    public void processLog(LogEvent logEvent) {
        // 1. PostgreSQL 저장
        LogEntity entity = LogEntity.builder()
                .timestamp(logEvent.getTimestamp().toEpochMilli() / 1000.0)
                .level(logEvent.getLevel())
                .service(logEvent.getService())
                .host(logEvent.getHost())
                .message(logEvent.getMessage())
                .metadata(logEvent.getMetadata())
                .build();
        
        logRepository.save(entity);
        log.debug("Log saved to PostgreSQL: id={}", entity.getId());

        // 2. Kafka 발행
        kafkaProducerService.sendLog(logEvent);
    }

    @Transactional
    public void processLogs(List<LogEvent> logEvents) {
        // 1. PostgreSQL 배치 저장
        List<LogEntity> entities = logEvents.stream()
                .map(event -> LogEntity.builder()
                        .timestamp(event.getTimestamp().toEpochMilli() / 1000.0)
                        .level(event.getLevel())
                        .service(event.getService())
                        .host(event.getHost())
                        .message(event.getMessage())
                        .metadata(event.getMetadata())
                        .build())
                .toList();
        
        logRepository.saveAll(entities);
        log.debug("Saved {} logs to PostgreSQL", entities.size());

        // 2. Kafka 발행
        logEvents.forEach(kafkaProducerService::sendLog);
    }

    @Transactional
    public void processActivity(ActivityEvent activityEvent) {
        // 1. PostgreSQL 저장
        EventEntity entity = EventEntity.builder()
                .eventId(activityEvent.getEventId())
                .timestamp(activityEvent.getTimestamp().toEpochMilli() / 1000.0)
                .userId(activityEvent.getUserId())
                .sessionId(activityEvent.getSessionId())
                .eventType(activityEvent.getEventType())
                .eventData(activityEvent.getEventData())
                .device(activityEvent.getDevice())
                .build();
        
        eventRepository.save(entity);
        log.debug("Event saved to PostgreSQL: id={}", entity.getId());

        // 2. Kafka 발행
        kafkaProducerService.sendActivity(activityEvent);
    }

    @Transactional
    public void processActivities(List<ActivityEvent> activityEvents) {
        // 1. PostgreSQL 배치 저장
        List<EventEntity> entities = activityEvents.stream()
                .map(event -> EventEntity.builder()
                        .eventId(event.getEventId())
                        .timestamp(event.getTimestamp().toEpochMilli() / 1000.0)
                        .userId(event.getUserId())
                        .sessionId(event.getSessionId())
                        .eventType(event.getEventType())
                        .eventData(event.getEventData())
                        .device(event.getDevice())
                        .build())
                .toList();
        
        eventRepository.saveAll(entities);
        log.debug("Saved {} events to PostgreSQL", entities.size());

        // 2. Kafka 발행
        activityEvents.forEach(kafkaProducerService::sendActivity);
    }
}
