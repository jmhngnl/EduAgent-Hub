package com.eduagent.platform.workspace;

public enum WorkspaceRole {
    VIEWER(1),
    MEMBER(2),
    ADMIN(3),
    OWNER(4);

    private final int rank;

    WorkspaceRole(int rank) {
        this.rank = rank;
    }

    public boolean atLeast(WorkspaceRole required) {
        return rank >= required.rank;
    }

    public static WorkspaceRole parse(String value) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("role must not be blank");
        }
        try {
            return WorkspaceRole.valueOf(value.trim().toUpperCase());
        } catch (IllegalArgumentException ex) {
            throw new IllegalArgumentException("role must be OWNER, ADMIN, MEMBER or VIEWER", ex);
        }
    }
}
