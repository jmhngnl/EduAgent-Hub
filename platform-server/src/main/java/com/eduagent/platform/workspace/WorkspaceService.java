package com.eduagent.platform.workspace;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.eduagent.platform.conversation.Conversation;
import com.eduagent.platform.conversation.ConversationMapper;
import com.eduagent.platform.identity.AppUser;
import com.eduagent.platform.identity.AppUserMapper;
import com.eduagent.platform.workspace.dto.WorkspaceMemberResponse;
import com.eduagent.platform.workspace.dto.WorkspaceMembershipResponse;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

@Service
public class WorkspaceService {
    private static final String ACTIVE = "ACTIVE";
    private static final String DEMO_WORKSPACE = "demo";

    private final WorkspaceMapper workspaceMapper;
    private final WorkspaceMemberMapper memberMapper;
    private final AppUserMapper userMapper;
    private final ConversationMapper conversationMapper;

    public WorkspaceService(
            WorkspaceMapper workspaceMapper,
            WorkspaceMemberMapper memberMapper,
            AppUserMapper userMapper,
            ConversationMapper conversationMapper
    ) {
        this.workspaceMapper = workspaceMapper;
        this.memberMapper = memberMapper;
        this.userMapper = userMapper;
        this.conversationMapper = conversationMapper;
    }

    public List<WorkspaceMembershipResponse> listForUser(String userId) {
        List<WorkspaceMember> memberships = memberMapper.selectList(
                new LambdaQueryWrapper<WorkspaceMember>()
                        .eq(WorkspaceMember::getUserId, userId)
                        .orderByDesc(WorkspaceMember::getUpdatedAt)
        );
        List<WorkspaceMembershipResponse> result = new ArrayList<>();
        for (WorkspaceMember membership : memberships) {
            Workspace workspace = workspaceMapper.selectById(membership.getWorkspaceId());
            if (workspace != null && ACTIVE.equals(workspace.getStatus())) {
                result.add(new WorkspaceMembershipResponse(
                        workspace.getId(),
                        workspace.getName(),
                        membership.getRole()
                ));
            }
        }
        return result;
    }

    @Transactional
    public WorkspaceMembershipResponse create(String userId, String name) {
        LocalDateTime now = LocalDateTime.now();
        Workspace workspace = new Workspace();
        workspace.setId(UUID.randomUUID().toString());
        workspace.setName(name.trim());
        workspace.setStatus(ACTIVE);
        workspace.setCreatedBy(userId);
        workspace.setCreatedAt(now);
        workspace.setUpdatedAt(now);
        workspaceMapper.insert(workspace);

        WorkspaceMember member = membership(workspace.getId(), userId, WorkspaceRole.OWNER, now);
        memberMapper.insert(member);
        return new WorkspaceMembershipResponse(workspace.getId(), workspace.getName(), WorkspaceRole.OWNER.name());
    }

    public WorkspaceRole requireAtLeast(String userId, String workspaceId, WorkspaceRole required) {
        Workspace workspace = workspaceMapper.selectById(workspaceId);
        if (workspace == null || !ACTIVE.equals(workspace.getStatus())) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Workspace not found: " + workspaceId);
        }
        WorkspaceMember member = findMembership(workspaceId, userId);
        if (member == null) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "You are not a member of this workspace");
        }
        WorkspaceRole actual = WorkspaceRole.parse(member.getRole());
        if (!actual.atLeast(required)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Workspace role " + actual + " does not allow this operation");
        }
        return actual;
    }

    public List<WorkspaceMemberResponse> listMembers(String actorUserId, String workspaceId) {
        requireAtLeast(actorUserId, workspaceId, WorkspaceRole.ADMIN);
        List<WorkspaceMemberResponse> result = new ArrayList<>();
        for (WorkspaceMember member : memberMapper.selectList(
                new LambdaQueryWrapper<WorkspaceMember>()
                        .eq(WorkspaceMember::getWorkspaceId, workspaceId)
                        .orderByDesc(WorkspaceMember::getUpdatedAt)
        )) {
            AppUser user = userMapper.selectById(member.getUserId());
            if (user != null) {
                result.add(new WorkspaceMemberResponse(
                        user.getId(),
                        user.getUsername(),
                        user.getDisplayName(),
                        member.getRole()
                ));
            }
        }
        return result;
    }

    @Transactional
    public WorkspaceMemberResponse upsertMember(
            String actorUserId,
            String workspaceId,
            String username,
            WorkspaceRole targetRole
    ) {
        WorkspaceRole actorRole = requireAtLeast(actorUserId, workspaceId, WorkspaceRole.ADMIN);
        if (targetRole == WorkspaceRole.OWNER) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Ownership transfer is not implemented in V2.2");
        }
        if (targetRole == WorkspaceRole.ADMIN && actorRole != WorkspaceRole.OWNER) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Only OWNER may grant ADMIN");
        }

        AppUser targetUser = userMapper.selectOne(
                new LambdaQueryWrapper<AppUser>().eq(AppUser::getUsername, username.trim().toLowerCase())
        );
        if (targetUser == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "User not found: " + username);
        }

        WorkspaceMember existing = findMembership(workspaceId, targetUser.getId());
        if (existing != null) {
            WorkspaceRole existingRole = WorkspaceRole.parse(existing.getRole());
            if (existingRole == WorkspaceRole.OWNER) {
                throw new ResponseStatusException(HttpStatus.CONFLICT, "Workspace OWNER role cannot be changed here");
            }
            if (existingRole == WorkspaceRole.ADMIN && actorRole != WorkspaceRole.OWNER) {
                throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Only OWNER may manage ADMIN members");
            }
            memberMapper.update(null, new LambdaUpdateWrapper<WorkspaceMember>()
                    .eq(WorkspaceMember::getWorkspaceId, workspaceId)
                    .eq(WorkspaceMember::getUserId, targetUser.getId())
                    .set(WorkspaceMember::getRole, targetRole.name())
                    .set(WorkspaceMember::getUpdatedAt, LocalDateTime.now()));
        } else {
            memberMapper.insert(membership(workspaceId, targetUser.getId(), targetRole, LocalDateTime.now()));
        }
        return new WorkspaceMemberResponse(
                targetUser.getId(), targetUser.getUsername(), targetUser.getDisplayName(), targetRole.name()
        );
    }

    @Transactional
    public void removeMember(String actorUserId, String workspaceId, String targetUserId) {
        WorkspaceRole actorRole = requireAtLeast(actorUserId, workspaceId, WorkspaceRole.ADMIN);
        WorkspaceMember existing = findMembership(workspaceId, targetUserId);
        if (existing == null) {
            return;
        }
        WorkspaceRole targetRole = WorkspaceRole.parse(existing.getRole());
        if (targetRole == WorkspaceRole.OWNER) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Workspace OWNER cannot be removed");
        }
        if (targetRole == WorkspaceRole.ADMIN && actorRole != WorkspaceRole.OWNER) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Only OWNER may remove ADMIN members");
        }
        memberMapper.delete(new LambdaQueryWrapper<WorkspaceMember>()
                .eq(WorkspaceMember::getWorkspaceId, workspaceId)
                .eq(WorkspaceMember::getUserId, targetUserId));
    }

    @Transactional
    public synchronized void ensureDemoOwnerIfEmpty(String userId) {
        Long count = memberMapper.selectCount(
                new LambdaQueryWrapper<WorkspaceMember>().eq(WorkspaceMember::getWorkspaceId, DEMO_WORKSPACE)
        );
        if (count != null && count == 0) {
            memberMapper.insert(membership(DEMO_WORKSPACE, userId, WorkspaceRole.OWNER, LocalDateTime.now()));
            conversationMapper.update(null, new LambdaUpdateWrapper<Conversation>()
                    .eq(Conversation::getWorkspaceId, DEMO_WORKSPACE)
                    .isNull(Conversation::getUserId)
                    .set(Conversation::getUserId, userId));
        }
    }

    private WorkspaceMember findMembership(String workspaceId, String userId) {
        return memberMapper.selectOne(new LambdaQueryWrapper<WorkspaceMember>()
                .eq(WorkspaceMember::getWorkspaceId, workspaceId)
                .eq(WorkspaceMember::getUserId, userId));
    }

    private WorkspaceMember membership(String workspaceId, String userId, WorkspaceRole role, LocalDateTime now) {
        WorkspaceMember member = new WorkspaceMember();
        member.setWorkspaceId(workspaceId);
        member.setUserId(userId);
        member.setRole(role.name());
        member.setCreatedAt(now);
        member.setUpdatedAt(now);
        return member;
    }
}
