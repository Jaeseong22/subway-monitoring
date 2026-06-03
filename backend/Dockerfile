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
COPY --from=builder /app/build/libs/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
