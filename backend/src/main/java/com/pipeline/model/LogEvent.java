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
public class LogEvent {

    @NotNull
    private Instant timestamp;

    @NotBlank
    private String level;

    @NotBlank
    private String service;

    private String host;

    private String message;

    private Map<String, Object> metadata;
}
