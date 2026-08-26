package com.eduagent.platform.auth;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.eduagent.platform.auth.dto.AuthSessionResponse;
import com.eduagent.platform.auth.dto.LoginRequest;
import com.eduagent.platform.auth.dto.MeResponse;
import com.eduagent.platform.auth.dto.RegisterRequest;
import com.eduagent.platform.auth.dto.UserResponse;
import com.eduagent.platform.identity.AppUser;
import com.eduagent.platform.identity.AppUserMapper;
import com.eduagent.platform.workspace.WorkspaceService;
import com.eduagent.platform.workspace.dto.WorkspaceMembershipResponse;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

@Service
public class AuthService {
    private static final String ACTIVE = "ACTIVE";

    private final AppUserMapper userMapper;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;
    private final RefreshTokenStore refreshTokenStore;
    private final WorkspaceService workspaceService;

    public AuthService(
            AppUserMapper userMapper,
            PasswordEncoder passwordEncoder,
            JwtService jwtService,
            RefreshTokenStore refreshTokenStore,
            WorkspaceService workspaceService
    ) {
        this.userMapper = userMapper;
        this.passwordEncoder = passwordEncoder;
        this.jwtService = jwtService;
        this.refreshTokenStore = refreshTokenStore;
        this.workspaceService = workspaceService;
    }

    @Transactional
    public IssuedSession register(RegisterRequest request) {
        String username = normalizeUsername(request.username());
        AppUser existing = findByUsername(username);
        if (existing != null) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Username already exists");
        }

        LocalDateTime now = LocalDateTime.now();
        AppUser user = new AppUser();
        user.setId(UUID.randomUUID().toString());
        user.setUsername(username);
        user.setPasswordHash(passwordEncoder.encode(request.password()));
        user.setDisplayName(request.displayName().trim());
        user.setStatus(ACTIVE);
        user.setCreatedAt(now);
        user.setUpdatedAt(now);
        userMapper.insert(user);

        workspaceService.ensureDemoOwnerIfEmpty(user.getId());
        return issueSession(user);
    }

    public IssuedSession login(LoginRequest request) {
        AppUser user = findByUsername(normalizeUsername(request.username()));
        if (user == null || !ACTIVE.equals(user.getStatus()) || !passwordEncoder.matches(request.password(), user.getPasswordHash())) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid username or password");
        }
        return issueSession(user);
    }

    public IssuedSession refresh(String refreshToken) {
        String userId = refreshTokenStore.consume(refreshToken);
        if (userId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Refresh token is invalid or expired");
        }
        AppUser user = userMapper.selectById(userId);
        if (user == null || !ACTIVE.equals(user.getStatus())) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "User is unavailable");
        }
        return issueSession(user);
    }

    public void logout(String refreshToken) {
        refreshTokenStore.revoke(refreshToken);
    }

    public MeResponse me(String userId) {
        AppUser user = userMapper.selectById(userId);
        if (user == null || !ACTIVE.equals(user.getStatus())) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "User is unavailable");
        }
        return new MeResponse(UserResponse.from(user), workspaceService.listForUser(userId));
    }

    public AppUser ensureBootstrapUser(String username, String password, String displayName) {
        String normalized = normalizeUsername(username);
        AppUser user = findByUsername(normalized);
        if (user == null) {
            LocalDateTime now = LocalDateTime.now();
            user = new AppUser();
            user.setId(UUID.randomUUID().toString());
            user.setUsername(normalized);
            user.setPasswordHash(passwordEncoder.encode(password));
            user.setDisplayName(displayName == null || displayName.isBlank() ? "Platform Owner" : displayName.trim());
            user.setStatus(ACTIVE);
            user.setCreatedAt(now);
            user.setUpdatedAt(now);
            userMapper.insert(user);
        }
        workspaceService.ensureDemoOwnerIfEmpty(user.getId());
        return user;
    }

    private IssuedSession issueSession(AppUser user) {
        String accessToken = jwtService.issue(user.getId(), user.getUsername());
        String refreshToken = refreshTokenStore.issue(user.getId());
        List<WorkspaceMembershipResponse> workspaces = workspaceService.listForUser(user.getId());
        AuthSessionResponse response = new AuthSessionResponse(
                accessToken,
                "Bearer",
                jwtService.expiresInSeconds(),
                UserResponse.from(user),
                workspaces
        );
        return new IssuedSession(response, refreshToken);
    }

    private AppUser findByUsername(String username) {
        return userMapper.selectOne(new LambdaQueryWrapper<AppUser>().eq(AppUser::getUsername, username));
    }

    private String normalizeUsername(String username) {
        return username.trim().toLowerCase(Locale.ROOT);
    }

    public record IssuedSession(AuthSessionResponse response, String refreshToken) {
    }
}
