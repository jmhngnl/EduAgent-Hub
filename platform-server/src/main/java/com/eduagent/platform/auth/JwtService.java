package com.eduagent.platform.auth;

import com.auth0.jwt.JWT;
import com.auth0.jwt.algorithms.Algorithm;
import com.auth0.jwt.exceptions.JWTVerificationException;
import com.auth0.jwt.interfaces.DecodedJWT;
import com.auth0.jwt.interfaces.JWTVerifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.Instant;
import java.util.Date;

@Service
public class JwtService {
    private final Algorithm algorithm;
    private final JWTVerifier verifier;
    private final String issuer;
    private final Duration accessTtl;

    public JwtService(
            @Value("${eduagent.security.jwt-secret}") String secret,
            @Value("${eduagent.security.jwt-issuer:eduagent-hub}") String issuer,
            @Value("${eduagent.security.access-token-minutes:30}") long accessMinutes
    ) {
        if (secret == null || secret.length() < 32) {
            throw new IllegalArgumentException("PLATFORM_JWT_SECRET must contain at least 32 characters");
        }
        this.algorithm = Algorithm.HMAC256(secret);
        this.issuer = issuer;
        this.accessTtl = Duration.ofMinutes(Math.max(5, accessMinutes));
        this.verifier = JWT.require(algorithm).withIssuer(issuer).build();
    }

    public String issue(String userId, String username) {
        Instant now = Instant.now();
        return JWT.create()
                .withIssuer(issuer)
                .withSubject(userId)
                .withClaim("username", username)
                .withIssuedAt(Date.from(now))
                .withExpiresAt(Date.from(now.plus(accessTtl)))
                .sign(algorithm);
    }

    public AuthenticatedUser verify(String token) throws JWTVerificationException {
        DecodedJWT jwt = verifier.verify(token);
        String username = jwt.getClaim("username").asString();
        if (jwt.getSubject() == null || username == null || username.isBlank()) {
            throw new JWTVerificationException("JWT is missing identity claims");
        }
        return new AuthenticatedUser(jwt.getSubject(), username);
    }

    public long expiresInSeconds() {
        return accessTtl.toSeconds();
    }
}
