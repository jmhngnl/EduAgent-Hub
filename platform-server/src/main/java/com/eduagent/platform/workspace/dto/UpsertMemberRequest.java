package com.eduagent.platform.workspace.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record UpsertMemberRequest(
        @NotBlank @Size(max = 64) String username,
        @NotBlank @Size(max = 20) String role
) {
}
