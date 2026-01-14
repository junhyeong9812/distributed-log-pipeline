//package com.pipeline.service;
//
//import com.pipeline.model.ActivityEvent;
//import com.pipeline.model.LogEvent;
//import lombok.RequiredArgsConstructor;
//import lombok.extern.slf4j.Slf4j;
//import org.springframework.beans.factory.annotation.Value;
//import org.springframework.kafka.core.KafkaTemplate;
//import org.springframework.stereotype.Service;
//
//import java.util.List;
//
//@Slf4j
//@Service
//@RequiredArgsConstructor
//public class KafkaProducerService {
//
//    private final KafkaTemplate<String, Object> kafkaTemplate;
//
//    @Value("${kafka.topics.logs}")
//    private String logsTopic;
//
//    @Value("${kafka.topics.events}")
//    private String eventsTopic;
//
//    @Value("${kafka.topics.alerts}")
//    private String alertsTopic;
//
//    public void sendLogAsync(LogEvent logEvent) {
//        String key = logEvent.getService();
//        kafkaTemplate.send(logsTopic, key, logEvent);
//
//        if ("ERROR".equalsIgnoreCase(logEvent.getLevel())) {
//            kafkaTemplate.send(alertsTopic, key, logEvent);
//        }
//    }
//
//    public void sendLogsAsync(List<LogEvent> logEvents) {
//        logEvents.forEach(this::sendLogAsync);
//    }
//
//    public void sendActivityAsync(ActivityEvent activityEvent) {
//        String key = activityEvent.getUserId();
//        kafkaTemplate.send(eventsTopic, key, activityEvent);
//    }
//
//    public void sendActivitiesAsync(List<ActivityEvent> activityEvents) {
//        activityEvents.forEach(this::sendActivityAsync);
//    }
//}
