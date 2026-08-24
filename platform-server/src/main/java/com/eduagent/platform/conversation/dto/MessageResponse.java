package com.eduagent.platform.conversation.dto;

import com.eduagent.platform.conversation.ChatMessage;

import java.time.LocalDateTime;

public record MessageResponse(
        String id,
        String conversationId,
        String role,
        String content,
        String taskRoute,
        String skillName,
        String toolCallsJson,
        String citationsJson,
        String tokenUsageJson,
        Long latencyMs,
        LocalDateTime createdAt
) {
    public static MessageResponse from(ChatMessage value) {
        return new MessageResponse(
                value.getId(), value.getConversationId(), value.getRole(), value.getContent(),
                value.getTaskRoute(), value.getSkillName(), value.getToolCallsJson(),
                value.getCitationsJson(), value.getTokenUsageJson(), value.getLatencyMs(), value.getCreatedAt()
        );
    }
}
