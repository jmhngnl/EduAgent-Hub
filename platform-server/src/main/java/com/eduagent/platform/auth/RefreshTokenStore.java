package com.eduagent.platform.auth;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Duration;
import java.util.Base64;

@Service
public class RefreshTokenStore {
    private static final String PREFIX = "eduagent:refresh:";
    private final StringRedisTemplate redisTemplate;
    private final SecureRandom secureRandom = new SecureRandom();
    private final Duration ttl;

    public RefreshTokenStore(
            StringRedisTemplate redisTemplate,
            @Value("${eduagent.security.refresh-token-days:7}") long refreshDays
    ) {
        this.redisTemplate = redisTemplate;
        this.ttl = Duration.ofDays(Math.max(1, refreshDays));
    }

    public String issue(String userId) {
        byte[] bytes = new byte[32];
        secureRandom.nextBytes(bytes);
        String token = Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
        redisTemplate.opsForValue().set(key(token), userId, ttl);
        return token;
    }

    public String consume(String token) {
        if (token == null || token.isBlank()) {
            return null;
        }
        String key = key(token);
        String userId = redisTemplate.opsForValue().get(key);
        if (userId != null) {
            redisTemplate.delete(key);
        }
        return userId;
    }

    public void revoke(String token) {
        if (token != null && !token.isBlank()) {
            redisTemplate.delete(key(token));
        }
    }

    public Duration ttl() {
        return ttl;
    }

    private String key(String token) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hashed = digest.digest(token.getBytes(StandardCharsets.UTF_8));
            return PREFIX + Base64.getUrlEncoder().withoutPadding().encodeToString(hashed);
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 is unavailable", ex);
        }
    }
}
