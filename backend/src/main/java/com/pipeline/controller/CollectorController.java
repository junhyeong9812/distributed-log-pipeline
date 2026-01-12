package com.pipeline.controller;

import com.pipeline.model.ActivityEvent;
import com.pipeline.model.LogEvent;
import com.pipeline.service.DataService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/api/collect")
@RequiredArgsConstructor
public class CollectorController {

    private final DataService dataService;

    @PostMapping("/log")
    public ResponseEntity<Map<String, Object>> collectLog(@Valid @RequestBody LogEvent logEvent) {
        log.debug("Received log: service={}, level={}", logEvent.getService(), logEvent.getLevel());
        
        dataService.processLog(logEvent);
        
        return ResponseEntity.ok(Map.of(
                "status", "accepted",
                "type", "log"
        ));
    }

    @PostMapping("/logs")
    public ResponseEntity<Map<String, Object>> collectLogs(@Valid @RequestBody List<LogEvent> logEvents) {
        log.debug("Received {} logs", logEvents.size());
        
        dataService.processLogs(logEvents);
        
        return ResponseEntity.ok(Map.of(
                "status", "accepted",
                "type", "logs",
                "count", logEvents.size()
        ));
    }

    @PostMapping("/activity")
    public ResponseEntity<Map<String, Object>> collectActivity(@Valid @RequestBody ActivityEvent activityEvent) {
        log.debug("Received activity: userId={}, eventType={}", 
                activityEvent.getUserId(), activityEvent.getEventType());
        
        dataService.processActivity(activityEvent);
        
        return ResponseEntity.ok(Map.of(
                "status", "accepted",
                "type", "activity"
        ));
    }

    @PostMapping("/activities")
    public ResponseEntity<Map<String, Object>> collectActivities(@Valid @RequestBody List<ActivityEvent> activityEvents) {
        log.debug("Received {} activities", activityEvents.size());
        
        dataService.processActivities(activityEvents);
        
        return ResponseEntity.ok(Map.of(
                "status", "accepted",
                "type", "activities",
                "count", activityEvents.size()
        ));
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of("status", "UP"));
    }
}
