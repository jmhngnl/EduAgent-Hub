package com.eduagent.platform.conversation;

import com.eduagent.platform.agent.AgentStreamingService;
import com.eduagent.platform.conversation.dto.AgentStreamRequest;
import com.eduagent.platform.conversation.dto.ConversationResponse;
import com.eduagent.platform.conversation.dto.CreateConversationRequest;
import com.eduagent.platform.conversation.dto.CreateMessageRequest;
import com.eduagent.platform.conversation.dto.MessageResponse;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
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

    public ConversationController(ConversationService service, AgentStreamingService agentStreamingService) {
        this.service = service;
        this.agentStreamingService = agentStreamingService;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public ConversationResponse create(@Valid @RequestBody CreateConversationRequest request) {
        return ConversationResponse.from(service.create(request));
    }

    @GetMapping
    public List<ConversationResponse> list(
            @RequestParam(defaultValue = "demo") String workspaceId,
            @RequestParam(defaultValue = "50") int limit
    ) {
        if (limit < 1 || limit > 100) {
            throw new IllegalArgumentException("limit must be between 1 and 100");
        }
        return service.list(workspaceId, limit).stream().map(ConversationResponse::from).toList();
    }

    @GetMapping("/{id}")
    public ConversationResponse get(@PathVariable String id) {
        return ConversationResponse.from(service.get(id));
    }

    @GetMapping("/{id}/messages")
    public List<MessageResponse> messages(@PathVariable String id) {
        return service.messages(id).stream().map(MessageResponse::from).toList();
    }

    @PostMapping("/{id}/messages")
    @ResponseStatus(HttpStatus.CREATED)
    public MessageResponse addMessage(@PathVariable String id, @Valid @RequestBody CreateMessageRequest request) {
        return MessageResponse.from(service.addMessage(id, request));
    }

    @PostMapping(value = "/{id}/messages/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter streamMessage(
            @PathVariable String id,
            @Valid @RequestBody AgentStreamRequest request
    ) {
        return agentStreamingService.stream(id, request);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable String id) {
        service.delete(id);
    }
}
