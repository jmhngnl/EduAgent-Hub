package com.eduagent.platform.auth;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

@Component
public class BootstrapAdminInitializer implements ApplicationRunner {
    private static final Logger log = LoggerFactory.getLogger(BootstrapAdminInitializer.class);

    private final AuthService authService;
    private final String username;
    private final String password;
    private final String displayName;

    public BootstrapAdminInitializer(
            AuthService authService,
            @Value("${eduagent.security.bootstrap-username:}") String username,
            @Value("${eduagent.security.bootstrap-password:}") String password,
            @Value("${eduagent.security.bootstrap-display-name:Platform Owner}") String displayName
    ) {
        this.authService = authService;
        this.username = username;
        this.password = password;
        this.displayName = displayName;
    }

    @Override
    public void run(ApplicationArguments args) {
        if (username == null || username.isBlank() || password == null || password.isBlank()) {
            return;
        }
        if (password.length() < 8) {
            throw new IllegalArgumentException("PLATFORM_BOOTSTRAP_PASSWORD must be at least 8 characters");
        }
        authService.ensureBootstrapUser(username, password, displayName);
        log.info("Bootstrap platform user '{}' is ready", username.trim().toLowerCase());
    }
}
