package com.eduagent.platform.agent;

import com.eduagent.platform.conversation.ChatMessage;
import com.eduagent.platform.conversation.Conversation;
import com.eduagent.platform.conversation.ConversationService;
import com.eduagent.platform.conversation.dto.AgentStreamRequest;
import com.eduagent.platform.conversation.dto.CreateMessageRequest;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;
import tools.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;

@Service
public class AgentStreamingService {
    private static final Logger log = LoggerFactory.getLogger(AgentStreamingService.class);

    private final ConversationService conversationService;
    private final JsonMapper jsonMapper;
    private final HttpClient httpClient;
    private final String agentBaseUrl;
    private final String agentApiKey;
    private final Duration requestTimeout;

    public AgentStreamingService(
            ConversationService conversationService,
            JsonMapper jsonMapper,
            @Value("${eduagent.agent-base-url:http://localhost:8000}") String agentBaseUrl,
            @Value("${eduagent.agent-api-key:}") String agentApiKey,
            @Value("${eduagent.agent-api-keys-fallback:demo}") String agentApiKeysFallback,
            @Value("${eduagent.agent-connect-timeout-seconds:10}") long connectTimeoutSeconds,
            @Value("${eduagent.agent-request-timeout-seconds:180}") long requestTimeoutSeconds
    ) {
        this.conversationService = conversationService;
        this.jsonMapper = jsonMapper;
        this.agentBaseUrl = stripTrailingSlash(agentBaseUrl);
        this.agentApiKey = resolveApiKey(agentApiKey, agentApiKeysFallback);
        this.requestTimeout = Duration.ofSeconds(requestTimeoutSeconds);
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(connectTimeoutSeconds))
                .version(HttpClient.Version.HTTP_1_1)
                .build();
    }

    public SseEmitter stream(String conversationId, AgentStreamRequest request) {
        Conversation conversation = conversationService.get(conversationId);
        String content = request.content().trim();

        // Persist the user's intent before invoking the non-deterministic agent runtime.
        // There is deliberately no long-running transaction across the SSE request.
        ChatMessage userMessage = conversationService.addMessage(
                conversationId,
                new CreateMessageRequest("USER", content, null, null, null, null, null, null)
        );

        SseEmitter emitter = new SseEmitter(0L);
        AtomicBoolean clientOpen = new AtomicBoolean(true);
        emitter.onCompletion(() -> clientOpen.set(false));
        emitter.onTimeout(() -> clientOpen.set(false));
        emitter.onError(error -> clientOpen.set(false));

        Thread.startVirtualThread(() -> proxyAgentStream(
                emitter,
                clientOpen,
                conversation,
                content,
                userMessage.getId()
        ));
        return emitter;
    }

    private void proxyAgentStream(
            SseEmitter emitter,
            AtomicBoolean clientOpen,
            Conversation conversation,
            String content,
            String currentUserMessageId
    ) {
        StreamAccumulator accumulator = new StreamAccumulator(System.nanoTime());
        try {
            ObjectNode payload = jsonMapper.createObjectNode();
            payload.put("message", content);
            payload.put("session_id", conversation.getId());
            payload.put("workspace_id", conversation.getWorkspaceId());

            ConversationService.AgentContextSnapshot contextSnapshot =
                    conversationService.agentContext(conversation.getId(), currentUserMessageId);
            ObjectNode contextNode = payload.putObject("conversation_context");
            contextNode.put("summary", contextSnapshot.summary());
            contextNode.put("summarized_message_count", contextSnapshot.summarizedMessageCount());
            var messagesNode = contextNode.putArray("messages");
            for (ConversationService.ContextMessage item : contextSnapshot.messages()) {
                ObjectNode messageNode = jsonMapper.createObjectNode();
                messageNode.put("role", item.role());
                messageNode.put("content", item.content());
                messagesNode.add(messageNode);
            }

            HttpRequest.Builder requestBuilder = HttpRequest.newBuilder()
                    .uri(URI.create(agentBaseUrl + "/v1/chat/stream"))
                    .timeout(requestTimeout)
                    .header("Content-Type", "application/json")
                    .header("Accept", "text/event-stream")
                    .POST(HttpRequest.BodyPublishers.ofString(
                            jsonMapper.writeValueAsString(payload),
                            StandardCharsets.UTF_8
                    ));
            if (!agentApiKey.isBlank()) {
                requestBuilder.header("X-API-Key", agentApiKey);
            }

            HttpResponse<InputStream> response = httpClient.send(
                    requestBuilder.build(),
                    HttpResponse.BodyHandlers.ofInputStream()
            );

            if (response.statusCode() != 200) {
                String upstreamBody = readLimited(response.body(), 4000);
                ObjectNode error = jsonMapper.createObjectNode();
                error.put("code", "AGENT_UPSTREAM_HTTP_ERROR");
                error.put("message", "Agent runtime returned HTTP " + response.statusCode());
                error.put("upstream_status", response.statusCode());
                if (!upstreamBody.isBlank()) {
                    error.put("upstream_body", upstreamBody);
                }
                sendJson(emitter, clientOpen, "error", jsonMapper.writeValueAsString(error));
                complete(emitter, clientOpen);
                return;
            }

            consumeSse(response.body(), (eventName, dataJson) -> {
                if (eventName == null || eventName.isBlank() || dataJson == null || dataJson.isBlank()) {
                    return false;
                }

                JsonNode data = jsonMapper.readTree(dataJson);
                accumulator.accept(eventName, data);

                if ("done".equals(eventName)) {
                    ChatMessage saved = persistAssistant(conversation.getId(), accumulator);
                    ObjectNode enhancedDone = data.isObject()
                            ? ((ObjectNode) data).deepCopy()
                            : jsonMapper.createObjectNode();
                    enhancedDone.put("platform_message_id", saved.getId());
                    enhancedDone.put("latency_ms", saved.getLatencyMs());
                    sendJson(
                            emitter,
                            clientOpen,
                            "done",
                            jsonMapper.writeValueAsString(enhancedDone)
                    );
                    return true;
                }

                sendJson(emitter, clientOpen, eventName, dataJson);
                return "error".equals(eventName);
            });

            if (!accumulator.terminalSeen()) {
                ObjectNode error = jsonMapper.createObjectNode();
                error.put("code", "AGENT_STREAM_INCOMPLETE");
                error.put("message", "Agent runtime closed the stream before done/error");
                sendJson(emitter, clientOpen, "error", jsonMapper.writeValueAsString(error));
            }
            complete(emitter, clientOpen);
        } catch (Exception ex) {
            log.error("Agent SSE proxy failed for conversation {}", conversation.getId(), ex);
            try {
                ObjectNode error = jsonMapper.createObjectNode();
                error.put("code", "AGENT_PROXY_ERROR");
                error.put("message", "Agent runtime request failed: " + safeMessage(ex));
                sendJson(emitter, clientOpen, "error", jsonMapper.writeValueAsString(error));
            } catch (Exception serializationError) {
                log.warn("Could not serialize proxy error", serializationError);
            }
            complete(emitter, clientOpen);
        }
    }

    private ChatMessage persistAssistant(String conversationId, StreamAccumulator accumulator) throws Exception {
        String answer = accumulator.answer();
        String toolsJson = jsonMapper.writeValueAsString(accumulator.toolCalls());
        String citationsJson = accumulator.citations() == null
                ? "[]"
                : jsonMapper.writeValueAsString(accumulator.citations());

        String contextStatsJson = accumulator.contextStats() == null
                ? null
                : jsonMapper.writeValueAsString(accumulator.contextStats());

        ChatMessage saved = conversationService.addMessage(
                conversationId,
                new CreateMessageRequest(
                        "ASSISTANT",
                        answer,
                        accumulator.taskRoute(),
                        accumulator.skillName(),
                        toolsJson,
                        citationsJson,
                        contextStatsJson,
                        accumulator.elapsedMillis()
                )
        );

        JsonNode contextUpdate = accumulator.contextUpdate();
        if (contextUpdate != null && contextUpdate.isObject()) {
            JsonNode summary = contextUpdate.get("summary");
            JsonNode count = contextUpdate.get("summarized_message_count");
            if (summary != null && summary.isTextual()
                    && count != null && count.isIntegralNumber()) {
                conversationService.updateContextSummary(
                        conversationId,
                        summary.asText(),
                        count.asInt()
                );
            }
        }
        return saved;
    }

    private void consumeSse(InputStream body, SseConsumer consumer) throws Exception {
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(body, StandardCharsets.UTF_8))) {
            String eventName = null;
            StringBuilder data = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.isEmpty()) {
                    if (data.length() > 0) {
                        boolean stop = consumer.accept(eventName, data.toString());
                        if (stop) {
                            return;
                        }
                    }
                    eventName = null;
                    data.setLength(0);
                    continue;
                }
                if (line.startsWith(":")) {
                    continue;
                }
                if (line.startsWith("event:")) {
                    eventName = line.substring("event:".length()).trim();
                    continue;
                }
                if (line.startsWith("data:")) {
                    if (data.length() > 0) {
                        data.append('\n');
                    }
                    data.append(line.substring("data:".length()).trim());
                }
            }
            if (data.length() > 0) {
                consumer.accept(eventName, data.toString());
            }
        }
    }

    private void sendJson(
            SseEmitter emitter,
            AtomicBoolean clientOpen,
            String eventName,
            String dataJson
    ) {
        if (!clientOpen.get()) {
            return;
        }
        try {
            emitter.send(SseEmitter.event().name(eventName).data(dataJson));
        } catch (IOException | IllegalStateException ex) {
            clientOpen.set(false);
            log.debug("SSE client disconnected while forwarding {}", eventName, ex);
        }
    }

    private void complete(SseEmitter emitter, AtomicBoolean clientOpen) {
        if (clientOpen.getAndSet(false)) {
            try {
                emitter.complete();
            } catch (IllegalStateException ignored) {
                // Client may already have disconnected.
            }
        }
    }

    private String readLimited(InputStream inputStream, int maxChars) throws IOException {
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(inputStream, StandardCharsets.UTF_8))) {
            char[] buffer = new char[maxChars];
            int read = reader.read(buffer);
            return read <= 0 ? "" : new String(buffer, 0, read);
        }
    }

    private static String resolveApiKey(String preferred, String fallback) {
        String candidate = preferred == null || preferred.isBlank() ? fallback : preferred;
        if (candidate == null || candidate.isBlank()) {
            return "";
        }
        int comma = candidate.indexOf(',');
        return (comma >= 0 ? candidate.substring(0, comma) : candidate).trim();
    }

    private static String stripTrailingSlash(String value) {
        String normalized = value == null ? "" : value.trim();
        while (normalized.endsWith("/")) {
            normalized = normalized.substring(0, normalized.length() - 1);
        }
        if (normalized.isBlank()) {
            throw new IllegalArgumentException("eduagent.agent-base-url must not be blank");
        }
        return normalized;
    }

    private static String safeMessage(Exception ex) {
        String message = ex.getMessage();
        return message == null || message.isBlank() ? ex.getClass().getSimpleName() : message;
    }

    @FunctionalInterface
    private interface SseConsumer {
        boolean accept(String eventName, String dataJson) throws Exception;
    }

    private static final class StreamAccumulator {
        private final long startedAtNanos;
        private final StringBuilder answer = new StringBuilder();
        private final Set<String> toolCalls = new LinkedHashSet<>();
        private JsonNode citations;
        private JsonNode contextStats;
        private JsonNode contextUpdate;
        private String taskRoute;
        private String skillName;
        private boolean terminalSeen;

        private StreamAccumulator(long startedAtNanos) {
            this.startedAtNanos = startedAtNanos;
        }

        private void accept(String eventName, JsonNode data) {
            switch (eventName) {
                case "route" -> captureRoute(data);
                case "token" -> {
                    if (data.isTextual()) {
                        answer.append(data.asText());
                    }
                }
                case "tool_start" -> captureToolStart(data);
                case "done" -> {
                    captureDone(data);
                    terminalSeen = true;
                }
                case "error" -> terminalSeen = true;
                default -> {
                    // tool_end and future event types are forwarded but need no persistence work here.
                }
            }
        }

        private void captureRoute(JsonNode data) {
            taskRoute = textOrNull(data.get("task_route"));
            skillName = textOrNull(data.get("skill"));
        }

        private void captureToolStart(JsonNode data) {
            String name = textOrNull(data.get("name"));
            if (name != null) {
                toolCalls.add(name);
            }
        }

        private void captureDone(JsonNode data) {
            String doneRoute = textOrNull(data.get("task_route"));
            String doneSkill = textOrNull(data.get("skill"));
            if (doneRoute != null) {
                taskRoute = doneRoute;
            }
            if (doneSkill != null) {
                skillName = doneSkill;
            }
            JsonNode doneCitations = data.get("citations");
            if (doneCitations != null && doneCitations.isArray()) {
                citations = doneCitations.deepCopy();
            }
            JsonNode doneContextStats = data.get("context_stats");
            if (doneContextStats != null && doneContextStats.isObject()) {
                contextStats = doneContextStats.deepCopy();
            }
            JsonNode doneContextUpdate = data.get("context_update");
            if (doneContextUpdate != null && doneContextUpdate.isObject()) {
                contextUpdate = doneContextUpdate.deepCopy();
            }
            JsonNode doneTools = data.get("tool_calls");
            if (doneTools != null && doneTools.isArray()) {
                toolCalls.clear();
                for (JsonNode item : doneTools) {
                    if (item.isTextual() && !item.asText().isBlank()) {
                        toolCalls.add(item.asText());
                    }
                }
            }
        }

        private String answer() {
            String value = answer.toString().trim();
            return value.isBlank() ? "Agent 未生成有效回答，请稍后重试。" : value;
        }

        private List<String> toolCalls() {
            return new ArrayList<>(toolCalls);
        }

        private JsonNode citations() {
            return citations;
        }

        private JsonNode contextStats() {
            return contextStats;
        }

        private JsonNode contextUpdate() {
            return contextUpdate;
        }

        private String taskRoute() {
            return taskRoute;
        }

        private String skillName() {
            return skillName;
        }

        private long elapsedMillis() {
            return Duration.ofNanos(System.nanoTime() - startedAtNanos).toMillis();
        }

        private boolean terminalSeen() {
            return terminalSeen;
        }

        private static String textOrNull(JsonNode node) {
            return node == null || node.isNull() || !node.isTextual() || node.asText().isBlank()
                    ? null
                    : node.asText();
        }
    }
}
