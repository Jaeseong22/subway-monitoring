FROM eclipse-temurin:25-jdk AS builder
WORKDIR /app

# Copy gradle wrapper and dependencies to cache them
COPY gradlew .
COPY gradle gradle
COPY build.gradle settings.gradle ./
RUN ./gradlew --version || true

# Copy source code and build
COPY src src
RUN ./gradlew build -x test

# Runtime stage
FROM eclipse-temurin:25-jre
WORKDIR /app

# curl: 컨테이너 헬스체크(/actuator/health/readiness)에 사용
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# 컨테이너를 root로 실행하지 않는다.
RUN useradd --system --create-home --uid 10001 appuser
COPY --from=builder /app/build/libs/*.jar app.jar
USER appuser

EXPOSE 8080
# 컨테이너 메모리 한도(mem_limit)를 JVM 힙 산정에 반영한다.
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75.0", "-jar", "app.jar"]
