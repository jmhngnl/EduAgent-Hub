package com.eduagent.platform;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
@MapperScan("com.eduagent.platform.conversation")
public class PlatformServerApplication {
    public static void main(String[] args) {
        SpringApplication.run(PlatformServerApplication.class, args);
    }
}
