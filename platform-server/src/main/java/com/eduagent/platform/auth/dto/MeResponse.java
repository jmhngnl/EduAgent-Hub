package com.eduagent.platform.auth.dto;

import com.eduagent.platform.workspace.dto.WorkspaceMembershipResponse;

import java.util.List;

public record MeResponse(UserResponse user, List<WorkspaceMembershipResponse> workspaces) {
}
