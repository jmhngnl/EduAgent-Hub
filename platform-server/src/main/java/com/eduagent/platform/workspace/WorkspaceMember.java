package com.eduagent.platform.workspace;

import com.baomidou.mybatisplus.annotation.TableName;

import java.time.LocalDateTime;

@TableName("workspace_member")
public class WorkspaceMember {
    private String workspaceId;
    private String userId;
    private String role;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;

    public String getWorkspaceId() { return workspaceId; }
    public void setWorkspaceId(String workspaceId) { this.workspaceId = workspaceId; }
    public String getUserId() { return userId; }
    public void setUserId(String userId) { this.userId = userId; }
    public String getRole() { return role; }
    public void setRole(String role) { this.role = role; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(LocalDateTime updatedAt) { this.updatedAt = updatedAt; }
}
