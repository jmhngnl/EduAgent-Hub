package com.eduagent.platform.auth.dto;

import com.eduagent.platform.workspace.dto.WorkspaceMembershipResponse;

import java.util.List;

public record AuthSessionResponse(
        String accessToken,
        String tokenType,
        long expiresInSeconds,
        UserResponse user,
        List<WorkspaceMembershipResponse> workspaces
) {
}
