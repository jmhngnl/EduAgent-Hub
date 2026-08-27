package com.eduagent.platform.conversation;

import com.eduagent.platform.agent.AgentStreamingService;
import com.eduagent.platform.auth.AuthenticatedUser;
import com.eduagent.platform.auth.CurrentUserService;
import com.eduagent.platform.conversation.dto.AgentStreamRequest;
import com.eduagent.platform.conversation.dto.ConversationResponse;
import com.eduagent.platform.conversation.dto.CreateConversationRequest;
import com.eduagent.platform.conversation.dto.CreateMessageRequest;
import com.eduagent.platform.conversation.dto.MessageResponse;
import com.eduagent.platform.workspace.WorkspaceRole;
import com.eduagent.platform.workspace.WorkspaceService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.List;

@RestController
@RequestMapping("/api/conversations")
public class ConversationController {
    private final ConversationService service;
    private final AgentStreamingService agentStreamingService;
    private final CurrentUserService currentUserService;
    private final WorkspaceService workspaceService;

    public ConversationController(
            ConversationService service,
            AgentStreamingService agentStreamingService,
            CurrentUserService currentUserService,
            WorkspaceService workspaceService
    ) {
        this.service = service;
        this.agentStreamingService = agentStreamingService;
        this.currentUserService = currentUserService;
        this.workspaceService = workspaceService;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public ConversationResponse create(
            @Valid @RequestBody CreateConversationRequest request,
            @RequestHeader(name = "X-Workspace-Id", required = false) String workspaceHeader
    ) {
        AuthenticatedUser user = currentUserService.require();
        String workspaceId = resolveWorkspace(workspaceHeader, request.workspaceId());
        workspaceService.requireAtLeast(user.userId(), workspaceId, WorkspaceRole.VIEWER);
        CreateConversationRequest secured = new CreateConversationRequest(user.userId(), workspaceId, request.title());
        return ConversationResponse.from(service.create(secured));
    }

    @GetMapping
    public List<ConversationResponse> list(
            @RequestParam(defaultValue = "demo") String workspaceId,
            @RequestHeader(name = "X-Workspace-Id", required = false) String workspaceHeader,
            @RequestParam(defaultValue = "50") int limit
    ) {
        if (limit < 1 || limit > 100) {
            throw new IllegalArgumentException("limit must be between 1 and 100");
        }
        AuthenticatedUser user = currentUserService.require();
        String resolvedWorkspace = resolveWorkspace(workspaceHeader, workspaceId);
        workspaceService.requireAtLeast(user.userId(), resolvedWorkspace, WorkspaceRole.VIEWER);
        return service.listOwned(user.userId(), resolvedWorkspace, limit).stream()
                .map(ConversationResponse::from)
                .toList();
    }

    @GetMapping("/{id}")
    public ConversationResponse get(@PathVariable String id) {
        AuthenticatedUser user = currentUserService.require();
        Conversation conversation = requireOwned(id, user.userId());
        workspaceService.requireAtLeast(user.userId(), conversation.getWorkspaceId(), WorkspaceRole.VIEWER);
        return ConversationResponse.from(conversation);
    }

    @GetMapping("/{id}/messages")
    public List<MessageResponse> messages(@PathVariable String id) {
        AuthenticatedUser user = currentUserService.require();
        Conversation conversation = requireOwned(id, user.userId());
        workspaceService.requireAtLeast(user.userId(), conversation.getWorkspaceId(), WorkspaceRole.VIEWER);
        return service.messages(id).stream().map(MessageResponse::from).toList();
    }

    @PostMapping("/{id}/messages")
    @ResponseStatus(HttpStatus.CREATED)
    public MessageResponse addMessage(@PathVariable String id, @Valid @RequestBody CreateMessageRequest request) {
        AuthenticatedUser user = currentUserService.require();
        Conversation conversation = requireOwned(id, user.userId());
        workspaceService.requireAtLeast(user.userId(), conversation.getWorkspaceId(), WorkspaceRole.VIEWER);
        return MessageResponse.from(service.addMessage(id, request));
    }

    @PostMapping(value = "/{id}/messages/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter streamMessage(
            @PathVariable String id,
            @Valid @RequestBody AgentStreamRequest request
    ) {
        AuthenticatedUser user = currentUserService.require();
        Conversation conversation = requireOwned(id, user.userId());
        workspaceService.requireAtLeast(user.userId(), conversation.getWorkspaceId(), WorkspaceRole.VIEWER);
        return agentStreamingService.stream(id, request);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable String id) {
        AuthenticatedUser user = currentUserService.require();
        Conversation conversation = requireOwned(id, user.userId());
        workspaceService.requireAtLeast(user.userId(), conversation.getWorkspaceId(), WorkspaceRole.VIEWER);
        service.delete(id);
    }

    private Conversation requireOwned(String id, String userId) {
        return service.getOwned(id, userId);
    }

    private String resolveWorkspace(String header, String fallback) {
        String value = header == null || header.isBlank() ? fallback : header;
        return value == null || value.isBlank() ? "demo" : value.trim();
    }
}
