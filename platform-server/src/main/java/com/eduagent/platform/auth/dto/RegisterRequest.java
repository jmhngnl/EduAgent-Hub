package com.eduagent.platform.auth.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record RegisterRequest(
        @NotBlank
        @Size(min = 3, max = 64)
        @Pattern(regexp = "[A-Za-z0-9._-]+", message = "username may contain letters, numbers, dot, underscore and dash only")
        String username,
        @NotBlank @Size(min = 8, max = 128) String password,
        @NotBlank @Size(max = 100) String displayName
) {
}
