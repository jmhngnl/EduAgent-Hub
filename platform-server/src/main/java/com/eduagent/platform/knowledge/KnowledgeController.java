package com.eduagent.platform.knowledge;

import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api")
public class KnowledgeController {
    private final KnowledgeProxyService knowledgeProxyService;

    public KnowledgeController(KnowledgeProxyService knowledgeProxyService) {
        this.knowledgeProxyService = knowledgeProxyService;
    }

    @GetMapping(value = "/documents", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> listDocuments(
            @RequestParam(defaultValue = "demo") String workspaceId,
            @RequestParam(required = false) String documentType
    ) {
        return response(knowledgeProxyService.listDocuments(workspaceId, documentType));
    }

    @PostMapping(
            value = "/documents/upload",
            consumes = MediaType.MULTIPART_FORM_DATA_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE
    )
    public ResponseEntity<String> upload(
            @RequestPart("file") MultipartFile file,
            @RequestParam(defaultValue = "demo") String workspaceId,
            @RequestParam(required = false) String documentId,
            @RequestParam(defaultValue = "lab_document") String documentType
    ) {
        return response(knowledgeProxyService.upload(file, workspaceId, documentId, documentType));
    }

    @PostMapping(
            value = "/documents/text",
            consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE
    )
    public ResponseEntity<String> ingestText(@RequestBody String body) {
        return response(knowledgeProxyService.ingestText(body));
    }

    @GetMapping(value = "/document-tasks/{taskId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> taskStatus(@PathVariable String taskId) {
        return response(knowledgeProxyService.taskStatus(taskId));
    }

    @GetMapping(value = "/knowledge/search", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> search(
            @RequestParam(defaultValue = "demo") String workspaceId,
            @RequestParam String query,
            @RequestParam(required = false) String documentType,
            @RequestParam(defaultValue = "6") int topK
    ) {
        if (query.isBlank()) {
            throw new IllegalArgumentException("query must not be blank");
        }
        return response(knowledgeProxyService.search(workspaceId, query, documentType, topK));
    }

    private ResponseEntity<String> response(KnowledgeProxyService.UpstreamResponse upstream) {
        return ResponseEntity.status(upstream.statusCode())
                .contentType(MediaType.APPLICATION_JSON)
                .body(upstream.body());
    }
}
