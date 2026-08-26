package com.eduagent.platform.knowledge;

import com.eduagent.platform.auth.AuthenticatedUser;
import com.eduagent.platform.auth.CurrentUserService;
import com.eduagent.platform.workspace.WorkspaceRole;
import com.eduagent.platform.workspace.WorkspaceService;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;
import tools.jackson.databind.node.ObjectNode;

@RestController
@RequestMapping("/api")
public class KnowledgeController {
    private final KnowledgeProxyService knowledgeProxyService;
    private final CurrentUserService currentUserService;
    private final WorkspaceService workspaceService;
    private final JsonMapper jsonMapper;

    public KnowledgeController(
            KnowledgeProxyService knowledgeProxyService,
            CurrentUserService currentUserService,
            WorkspaceService workspaceService,
            JsonMapper jsonMapper
    ) {
        this.knowledgeProxyService = knowledgeProxyService;
        this.currentUserService = currentUserService;
        this.workspaceService = workspaceService;
        this.jsonMapper = jsonMapper;
    }

    @GetMapping(value = "/documents", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> listDocuments(
            @RequestParam(defaultValue = "demo") String workspaceId,
            @RequestHeader(name = "X-Workspace-Id", required = false) String workspaceHeader,
            @RequestParam(required = false) String documentType
    ) {
        String verified = requireWorkspace(workspaceHeader, workspaceId, WorkspaceRole.VIEWER);
        return response(knowledgeProxyService.listDocuments(verified, documentType));
    }

    @PostMapping(
            value = "/documents/upload",
            consumes = MediaType.MULTIPART_FORM_DATA_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE
    )
    public ResponseEntity<String> upload(
            @RequestPart("file") MultipartFile file,
            @RequestParam(defaultValue = "demo") String workspaceId,
            @RequestHeader(name = "X-Workspace-Id", required = false) String workspaceHeader,
            @RequestParam(required = false) String documentId,
            @RequestParam(defaultValue = "lab_document") String documentType
    ) {
        String verified = requireWorkspace(workspaceHeader, workspaceId, WorkspaceRole.MEMBER);
        return response(knowledgeProxyService.upload(file, verified, documentId, documentType));
    }

    @PostMapping(
            value = "/documents/text",
            consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE
    )
    public ResponseEntity<String> ingestText(
            @RequestBody String body,
            @RequestHeader(name = "X-Workspace-Id", required = false) String workspaceHeader
    ) {
        try {
            JsonNode parsed = jsonMapper.readTree(body);
            if (!(parsed instanceof ObjectNode objectNode)) {
                throw new IllegalArgumentException("JSON object is required");
            }
            String requested = textOrDefault(objectNode.get("workspace_id"), "demo");
            String verified = requireWorkspace(workspaceHeader, requested, WorkspaceRole.MEMBER);
            objectNode.put("workspace_id", verified);
            return response(knowledgeProxyService.ingestText(jsonMapper.writeValueAsString(objectNode)));
        } catch (org.springframework.web.server.ResponseStatusException ex) {
            throw ex;
        } catch (IllegalArgumentException ex) {
            throw ex;
        } catch (Exception ex) {
            throw new IllegalArgumentException("Invalid text ingestion payload", ex);
        }
    }

    @GetMapping(value = "/document-tasks/{taskId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> taskStatus(@PathVariable String taskId) {
        currentUserService.require();
        return response(knowledgeProxyService.taskStatus(taskId));
    }

    @GetMapping(value = "/knowledge/search", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> search(
            @RequestParam(defaultValue = "demo") String workspaceId,
            @RequestHeader(name = "X-Workspace-Id", required = false) String workspaceHeader,
            @RequestParam String query,
            @RequestParam(required = false) String documentType,
            @RequestParam(defaultValue = "6") int topK
    ) {
        if (query.isBlank()) {
            throw new IllegalArgumentException("query must not be blank");
        }
        String verified = requireWorkspace(workspaceHeader, workspaceId, WorkspaceRole.VIEWER);
        return response(knowledgeProxyService.search(verified, query, documentType, topK));
    }

    private String requireWorkspace(String header, String fallback, WorkspaceRole role) {
        AuthenticatedUser user = currentUserService.require();
        String workspaceId = header == null || header.isBlank() ? fallback : header;
        if (workspaceId == null || workspaceId.isBlank()) {
            workspaceId = "demo";
        }
        workspaceId = workspaceId.trim();
        workspaceService.requireAtLeast(user.userId(), workspaceId, role);
        return workspaceId;
    }

    private String textOrDefault(JsonNode node, String fallback) {
        return node != null && node.isTextual() && !node.asText().isBlank() ? node.asText() : fallback;
    }

    private ResponseEntity<String> response(KnowledgeProxyService.UpstreamResponse upstream) {
        return ResponseEntity.status(upstream.statusCode())
                .contentType(MediaType.APPLICATION_JSON)
                .body(upstream.body());
    }
}
