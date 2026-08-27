package com.eduagent.platform.auth;

import com.eduagent.platform.auth.dto.AuthSessionResponse;
import com.eduagent.platform.auth.dto.LoginRequest;
import com.eduagent.platform.auth.dto.MeResponse;
import com.eduagent.platform.auth.dto.RegisterRequest;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CookieValue;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/auth")
public class AuthController {
    private static final String REFRESH_COOKIE = "eduagent_refresh";

    private final AuthService authService;
    private final CurrentUserService currentUserService;
    private final RefreshTokenStore refreshTokenStore;
    private final boolean secureCookie;

    public AuthController(
            AuthService authService,
            CurrentUserService currentUserService,
            RefreshTokenStore refreshTokenStore,
            @Value("${eduagent.security.refresh-cookie-secure:false}") boolean secureCookie
    ) {
        this.authService = authService;
        this.currentUserService = currentUserService;
        this.refreshTokenStore = refreshTokenStore;
        this.secureCookie = secureCookie;
    }

    @PostMapping("/register")
    public ResponseEntity<AuthSessionResponse> register(@Valid @RequestBody RegisterRequest request) {
        return withRefreshCookie(authService.register(request));
    }

    @PostMapping("/login")
    public ResponseEntity<AuthSessionResponse> login(@Valid @RequestBody LoginRequest request) {
        return withRefreshCookie(authService.login(request));
    }

    @PostMapping("/refresh")
    public ResponseEntity<AuthSessionResponse> refresh(
            @CookieValue(name = REFRESH_COOKIE, required = false) String refreshToken
    ) {
        return withRefreshCookie(authService.refresh(refreshToken));
    }

    @PostMapping("/logout")
    public ResponseEntity<Void> logout(
            @CookieValue(name = REFRESH_COOKIE, required = false) String refreshToken
    ) {
        authService.logout(refreshToken);
        return ResponseEntity.noContent()
                .header(HttpHeaders.SET_COOKIE, clearCookie().toString())
                .build();
    }

    @GetMapping("/me")
    public MeResponse me() {
        return authService.me(currentUserService.require().userId());
    }

    private ResponseEntity<AuthSessionResponse> withRefreshCookie(AuthService.IssuedSession issued) {
        ResponseCookie cookie = ResponseCookie.from(REFRESH_COOKIE, issued.refreshToken())
                .httpOnly(true)
                .secure(secureCookie)
                .sameSite("Strict")
                .path("/api/auth")
                .maxAge(refreshTokenStore.ttl())
                .build();
        return ResponseEntity.ok()
                .header(HttpHeaders.SET_COOKIE, cookie.toString())
                .body(issued.response());
    }

    private ResponseCookie clearCookie() {
        return ResponseCookie.from(REFRESH_COOKIE, "")
                .httpOnly(true)
                .secure(secureCookie)
                .sameSite("Strict")
                .path("/api/auth")
                .maxAge(0)
                .build();
    }
}
