package com.eduagent.platform.conversation.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record CreateMessageRequest(
        @NotBlank @Pattern(regexp = "USER|ASSISTANT|SYSTEM") String role,
        @NotBlank @Size(max = 100000) String content,
        @Size(max = 64) String taskRoute,
        @Size(max = 128) String skillName,
        String toolCallsJson,
        String citationsJson,
        String tokenUsageJson,
        Long latencyMs
) {
}
