package com.pipeline.model;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ActivityEvent {

    @NotBlank
    private String eventId;

    @NotNull
    private Instant timestamp;

    @NotBlank
    private String userId;

    private String sessionId;

    @NotBlank
    private String eventType;

    private Map<String, Object> eventData;

    private Map<String, Object> device;
}
