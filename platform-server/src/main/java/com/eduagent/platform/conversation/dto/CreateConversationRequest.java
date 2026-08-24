package com.eduagent.platform.conversation.dto;

import jakarta.validation.constraints.Size;

public record CreateConversationRequest(
        @Size(max = 64) String userId,
        @Size(max = 64) String workspaceId,
        @Size(max = 200) String title
) {
}
