package com.pipeline.service;

import com.pipeline.model.ActivityEvent;
import com.pipeline.model.LogEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.stereotype.Service;

import java.util.concurrent.CompletableFuture;

@Slf4j
@Service
@RequiredArgsConstructor
public class KafkaProducerService {

    private final KafkaTemplate<String, Object> kafkaTemplate;

    @Value("${kafka.topics.logs}")
    private String logsTopic;

    @Value("${kafka.topics.events}")
    private String eventsTopic;

    @Value("${kafka.topics.alerts}")
    private String alertsTopic;

    public void sendLog(LogEvent logEvent) {
        String key = logEvent.getService();
        
        CompletableFuture<SendResult<String, Object>> future = 
                kafkaTemplate.send(logsTopic, key, logEvent);

        future.whenComplete((result, ex) -> {
            if (ex == null) {
                log.debug("Log sent: topic={}, partition={}, offset={}",
                        result.getRecordMetadata().topic(),
                        result.getRecordMetadata().partition(),
                        result.getRecordMetadata().offset());
            } else {
                log.error("Failed to send log: {}", ex.getMessage());
            }
        });

        // ERROR 레벨이면 알림 토픽에도 발행
        if ("ERROR".equalsIgnoreCase(logEvent.getLevel())) {
            kafkaTemplate.send(alertsTopic, key, logEvent);
            log.info("Alert sent for ERROR log: service={}", logEvent.getService());
        }
    }

    public void sendActivity(ActivityEvent activityEvent) {
        String key = activityEvent.getUserId();

        CompletableFuture<SendResult<String, Object>> future = 
                kafkaTemplate.send(eventsTopic, key, activityEvent);

        future.whenComplete((result, ex) -> {
            if (ex == null) {
                log.debug("Activity sent: topic={}, partition={}, offset={}",
                        result.getRecordMetadata().topic(),
                        result.getRecordMetadata().partition(),
                        result.getRecordMetadata().offset());
            } else {
                log.error("Failed to send activity: {}", ex.getMessage());
            }
        });
    }
}
