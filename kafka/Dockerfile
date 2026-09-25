FROM maven:3.9.11-eclipse-temurin-21 AS build
WORKDIR /workspace
COPY . .
RUN --mount=type=cache,target=/root/.m2 mvn -B clean package

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /workspace/producers/view-producer/target/app.jar /app/view-producer.jar
COPY --from=build /workspace/producers/comment-producer/target/app.jar /app/comment-producer.jar
COPY --from=build /workspace/producers/review-producer/target/app.jar /app/review-producer.jar
COPY --from=build /workspace/consumers/view-matrix-consumer/target/app.jar /app/view-matrix-consumer.jar
COPY --from=build /workspace/consumers/comment-matrix-consumer/target/app.jar /app/comment-matrix-consumer.jar
COPY --from=build /workspace/consumers/review-matrix-consumer/target/app.jar /app/review-matrix-consumer.jar
