package com.eduagent.platform.conversation;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.eduagent.platform.common.NotFoundException;
import com.eduagent.platform.conversation.dto.CreateConversationRequest;
import com.eduagent.platform.conversation.dto.CreateMessageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

@Service
public class ConversationService {
    private static final String ACTIVE = "ACTIVE";
    private static final String DELETED = "DELETED";
    private static final String DEFAULT_WORKSPACE = "demo";
    private static final String DEFAULT_TITLE = "New Chat";

    private final ConversationMapper conversationMapper;
    private final ChatMessageMapper messageMapper;

    public ConversationService(ConversationMapper conversationMapper, ChatMessageMapper messageMapper) {
        this.conversationMapper = conversationMapper;
        this.messageMapper = messageMapper;
    }

    @Transactional
    public Conversation create(CreateConversationRequest request) {
        LocalDateTime now = LocalDateTime.now();
        Conversation value = new Conversation();
        value.setId(UUID.randomUUID().toString());
        value.setUserId(blankToNull(request.userId()));
        value.setWorkspaceId(defaultIfBlank(request.workspaceId(), DEFAULT_WORKSPACE));
        value.setTitle(defaultIfBlank(request.title(), DEFAULT_TITLE));
        value.setStatus(ACTIVE);
        value.setCreatedAt(now);
        value.setUpdatedAt(now);
        conversationMapper.insert(value);
        return value;
    }

    public List<Conversation> list(String workspaceId, int limit) {
        String resolvedWorkspace = defaultIfBlank(workspaceId, DEFAULT_WORKSPACE);
        return conversationMapper.selectList(new LambdaQueryWrapper<Conversation>()
                .eq(Conversation::getWorkspaceId, resolvedWorkspace)
                .ne(Conversation::getStatus, DELETED)
                .orderByDesc(Conversation::getUpdatedAt)
                .last("LIMIT " + limit));
    }

    public Conversation get(String id) {
        Conversation value = conversationMapper.selectById(id);
        if (value == null || DELETED.equals(value.getStatus())) {
            throw new NotFoundException("Conversation not found: " + id);
        }
        return value;
    }

    public List<ChatMessage> messages(String conversationId) {
        get(conversationId);
        return messageMapper.selectList(new LambdaQueryWrapper<ChatMessage>()
                .eq(ChatMessage::getConversationId, conversationId)
                .orderByAsc(ChatMessage::getCreatedAt)
                .orderByAsc(ChatMessage::getId));
    }

    @Transactional
    public ChatMessage addMessage(String conversationId, CreateMessageRequest request) {
        Conversation conversation = get(conversationId);
        LocalDateTime now = LocalDateTime.now();

        ChatMessage message = new ChatMessage();
        message.setId(UUID.randomUUID().toString());
        message.setConversationId(conversationId);
        message.setRole(request.role().toUpperCase(Locale.ROOT));
        message.setContent(request.content().trim());
        message.setTaskRoute(blankToNull(request.taskRoute()));
        message.setSkillName(blankToNull(request.skillName()));
        message.setToolCallsJson(blankToNull(request.toolCallsJson()));
        message.setCitationsJson(blankToNull(request.citationsJson()));
        message.setTokenUsageJson(blankToNull(request.tokenUsageJson()));
        message.setLatencyMs(request.latencyMs());
        message.setCreatedAt(now);
        messageMapper.insert(message);

        LambdaUpdateWrapper<Conversation> update = new LambdaUpdateWrapper<Conversation>()
                .eq(Conversation::getId, conversationId)
                .set(Conversation::getUpdatedAt, now);
        if ("USER".equals(message.getRole()) && DEFAULT_TITLE.equals(conversation.getTitle())) {
            update.set(Conversation::getTitle, deriveTitle(message.getContent()));
        }
        conversationMapper.update(null, update);
        return message;
    }

    @Transactional
    public void delete(String id) {
        get(id);
        conversationMapper.update(null, new LambdaUpdateWrapper<Conversation>()
                .eq(Conversation::getId, id)
                .set(Conversation::getStatus, DELETED)
                .set(Conversation::getUpdatedAt, LocalDateTime.now()));
    }

    private String deriveTitle(String content) {
        String normalized = content.replaceAll("\\s+", " ").trim();
        int[] points = normalized.codePoints().limit(32).toArray();
        String title = new String(points, 0, points.length);
        return normalized.codePointCount(0, normalized.length()) > 32 ? title + "…" : title;
    }

    private String defaultIfBlank(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value.trim();
    }

    private String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }
}
