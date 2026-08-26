package com.eduagent.platform.auth.dto;

import com.eduagent.platform.identity.AppUser;

public record UserResponse(String id, String username, String displayName) {
    public static UserResponse from(AppUser user) {
        return new UserResponse(user.getId(), user.getUsername(), user.getDisplayName());
    }
}
