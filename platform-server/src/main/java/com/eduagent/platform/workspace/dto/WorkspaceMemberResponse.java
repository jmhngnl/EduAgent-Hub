package com.eduagent.platform.workspace.dto;

public record WorkspaceMemberResponse(
        String userId,
        String username,
        String displayName,
        String role
) {
}
