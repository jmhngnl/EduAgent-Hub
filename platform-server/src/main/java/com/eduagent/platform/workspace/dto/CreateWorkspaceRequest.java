package com.eduagent.platform.workspace.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record CreateWorkspaceRequest(@NotBlank @Size(max = 120) String name) {
}
