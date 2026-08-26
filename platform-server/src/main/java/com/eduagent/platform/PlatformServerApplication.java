package com.eduagent.platform;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
@MapperScan({
        "com.eduagent.platform.conversation",
        "com.eduagent.platform.identity",
        "com.eduagent.platform.workspace"
})
public class PlatformServerApplication {
    public static void main(String[] args) {
        SpringApplication.run(PlatformServerApplication.class, args);
    }
}
