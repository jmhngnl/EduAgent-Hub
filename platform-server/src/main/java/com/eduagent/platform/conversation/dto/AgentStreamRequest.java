package com.eduagent.platform.conversation.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record AgentStreamRequest(
        @NotBlank @Size(max = 12000) String content
) {
}
