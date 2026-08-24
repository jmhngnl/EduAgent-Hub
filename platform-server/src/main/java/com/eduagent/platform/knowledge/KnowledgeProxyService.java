package com.eduagent.platform.knowledge;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.UUID;

@Service
public class KnowledgeProxyService {
    private final HttpClient httpClient;
    private final String agentBaseUrl;
    private final String agentApiKey;
    private final Duration requestTimeout;

    public KnowledgeProxyService(
            @Value("${eduagent.agent-base-url:http://localhost:8000}") String agentBaseUrl,
            @Value("${eduagent.agent-api-key:}") String agentApiKey,
            @Value("${eduagent.agent-api-keys-fallback:demo}") String agentApiKeysFallback,
            @Value("${eduagent.agent-connect-timeout-seconds:10}") long connectTimeoutSeconds,
            @Value("${eduagent.agent-request-timeout-seconds:180}") long requestTimeoutSeconds
    ) {
        this.agentBaseUrl = stripTrailingSlash(agentBaseUrl);
        this.agentApiKey = resolveApiKey(agentApiKey, agentApiKeysFallback);
        this.requestTimeout = Duration.ofSeconds(requestTimeoutSeconds);
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(connectTimeoutSeconds))
                .version(HttpClient.Version.HTTP_1_1)
                .build();
    }

    public UpstreamResponse listDocuments(String workspaceId, String documentType) {
        String path = "/v1/knowledge/documents?workspace_id=" + encode(workspaceId);
        if (documentType != null && !documentType.isBlank()) {
            path += "&document_type=" + encode(validateDocumentType(documentType));
        }
        return send(HttpRequest.newBuilder().GET(), path);
    }

    public UpstreamResponse search(String workspaceId, String query, String documentType, int topK) {
        String path = "/v1/knowledge/search?workspace_id=" + encode(workspaceId)
                + "&query=" + encode(query)
                + "&top_k=" + Math.max(1, Math.min(topK, 20));
        if (documentType != null && !documentType.isBlank()) {
            path += "&document_type=" + encode(validateDocumentType(documentType));
        }
        return send(HttpRequest.newBuilder().GET(), path);
    }

    public UpstreamResponse taskStatus(String taskId) {
        return send(HttpRequest.newBuilder().GET(), "/v1/tasks/" + encodePath(taskId));
    }

    public UpstreamResponse ingestText(String jsonBody) {
        HttpRequest.Builder builder = HttpRequest.newBuilder()
                .header("Content-Type", MediaType.APPLICATION_JSON_VALUE)
                .POST(HttpRequest.BodyPublishers.ofString(jsonBody, StandardCharsets.UTF_8));
        return send(builder, "/v1/knowledge/text");
    }

    public UpstreamResponse upload(
            MultipartFile file,
            String workspaceId,
            String documentId,
            String documentType
    ) {
        if (file.isEmpty()) {
            throw new IllegalArgumentException("Uploaded file is empty");
        }
        String normalizedType = validateDocumentType(documentType);
        String boundary = "----EduAgentBoundary" + UUID.randomUUID().toString().replace("-", "");
        byte[] body;
        try {
            body = multipartBody(boundary, file, workspaceId, documentId, normalizedType);
        } catch (IOException ex) {
            throw new KnowledgeUpstreamException("Could not read uploaded file", ex);
        }

        HttpRequest.Builder builder = HttpRequest.newBuilder()
                .header("Content-Type", "multipart/form-data; boundary=" + boundary)
                .POST(HttpRequest.BodyPublishers.ofByteArray(body));
        return send(builder, "/v1/knowledge/files");
    }

    private UpstreamResponse send(HttpRequest.Builder builder, String path) {
        builder.uri(URI.create(agentBaseUrl + path))
                .timeout(requestTimeout)
                .header("Accept", MediaType.APPLICATION_JSON_VALUE);
        if (!agentApiKey.isBlank()) {
            builder.header("X-API-Key", agentApiKey);
        }
        try {
            HttpResponse<String> response = httpClient.send(
                    builder.build(),
                    HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8)
            );
            return new UpstreamResponse(response.statusCode(), response.body());
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new KnowledgeUpstreamException("Knowledge runtime request was interrupted", ex);
        } catch (IOException ex) {
            throw new KnowledgeUpstreamException("Knowledge runtime is unavailable", ex);
        }
    }

    private static byte[] multipartBody(
            String boundary,
            MultipartFile file,
            String workspaceId,
            String documentId,
            String documentType
    ) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        writeField(out, boundary, "workspace_id", workspaceId);
        writeField(out, boundary, "document_type", documentType);
        if (documentId != null && !documentId.isBlank()) {
            writeField(out, boundary, "document_id", documentId.trim());
        }

        String filename = sanitizeFilename(file.getOriginalFilename());
        String contentType = file.getContentType();
        if (contentType == null || contentType.isBlank()) {
            contentType = MediaType.APPLICATION_OCTET_STREAM_VALUE;
        }
        write(out, "--" + boundary + "\r\n");
        write(out, "Content-Disposition: form-data; name=\"file\"; filename=\"" + filename + "\"\r\n");
        write(out, "Content-Type: " + contentType + "\r\n\r\n");
        out.write(file.getBytes());
        write(out, "\r\n--" + boundary + "--\r\n");
        return out.toByteArray();
    }

    private static void writeField(ByteArrayOutputStream out, String boundary, String name, String value)
            throws IOException {
        write(out, "--" + boundary + "\r\n");
        write(out, "Content-Disposition: form-data; name=\"" + name + "\"\r\n\r\n");
        write(out, value == null ? "" : value);
        write(out, "\r\n");
    }

    private static void write(ByteArrayOutputStream out, String value) throws IOException {
        out.write(value.getBytes(StandardCharsets.UTF_8));
    }

    private static String sanitizeFilename(String value) {
        if (value == null || value.isBlank()) {
            return "upload.bin";
        }
        return value.replace("\\", "_").replace("/", "_").replace("\"", "_").replace("\r", "_").replace("\n", "_");
    }

    private static String validateDocumentType(String value) {
        String normalized = value == null || value.isBlank() ? "lab_document" : value.trim();
        if (!normalized.equals("lab_document") && !normalized.equals("paper")) {
            throw new IllegalArgumentException("documentType must be lab_document or paper");
        }
        return normalized;
    }

    private static String encode(String value) {
        return URLEncoder.encode(value == null ? "" : value, StandardCharsets.UTF_8);
    }

    private static String encodePath(String value) {
        return encode(value).replace("+", "%20");
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

    public record UpstreamResponse(int statusCode, String body) {
    }
}
