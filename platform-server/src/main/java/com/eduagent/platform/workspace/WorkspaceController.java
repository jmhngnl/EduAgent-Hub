package com.eduagent.platform.workspace;

import com.eduagent.platform.auth.AuthenticatedUser;
import com.eduagent.platform.auth.CurrentUserService;
import com.eduagent.platform.workspace.dto.CreateWorkspaceRequest;
import com.eduagent.platform.workspace.dto.UpsertMemberRequest;
import com.eduagent.platform.workspace.dto.WorkspaceMemberResponse;
import com.eduagent.platform.workspace.dto.WorkspaceMembershipResponse;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/workspaces")
public class WorkspaceController {
    private final CurrentUserService currentUserService;
    private final WorkspaceService workspaceService;

    public WorkspaceController(CurrentUserService currentUserService, WorkspaceService workspaceService) {
        this.currentUserService = currentUserService;
        this.workspaceService = workspaceService;
    }

    @GetMapping
    public List<WorkspaceMembershipResponse> list() {
        return workspaceService.listForUser(currentUserService.require().userId());
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public WorkspaceMembershipResponse create(@Valid @RequestBody CreateWorkspaceRequest request) {
        return workspaceService.create(currentUserService.require().userId(), request.name());
    }

    @GetMapping("/{workspaceId}/members")
    public List<WorkspaceMemberResponse> members(@PathVariable String workspaceId) {
        return workspaceService.listMembers(currentUserService.require().userId(), workspaceId);
    }

    @PutMapping("/{workspaceId}/members")
    public WorkspaceMemberResponse upsertMember(
            @PathVariable String workspaceId,
            @Valid @RequestBody UpsertMemberRequest request
    ) {
        AuthenticatedUser actor = currentUserService.require();
        return workspaceService.upsertMember(
                actor.userId(), workspaceId, request.username(), WorkspaceRole.parse(request.role())
        );
    }

    @DeleteMapping("/{workspaceId}/members/{userId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void removeMember(@PathVariable String workspaceId, @PathVariable String userId) {
        workspaceService.removeMember(currentUserService.require().userId(), workspaceId, userId);
    }
}
