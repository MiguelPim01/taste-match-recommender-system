package br.ufes.tastematch.kafka.common;

import org.apache.kafka.clients.consumer.ConsumerRecord;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.sql.Statement;
import java.time.Instant;

public final class SQLiteMatrixStore implements AutoCloseable {
    private final EventKind kind;
    private final EventCodec codec;
    private final Connection connection;

    public SQLiteMatrixStore(Path databasePath, EventKind kind) throws SQLException, IOException {
        this.kind = kind;
        this.codec = new EventCodec();
        Path absolutePath = databasePath.toAbsolutePath();
        if (absolutePath.getParent() != null) {
            Files.createDirectories(absolutePath.getParent());
        }
        connection = DriverManager.getConnection("jdbc:sqlite:" + absolutePath);
        initialize();
    }

    public ProcessingOutcome process(ConsumerRecord<String, String> record) throws SQLException {
        final InteractionEvent event;
        try {
            event = codec.decode(record.value(), kind);
            if (record.key() == null || !record.key().equals(event.userId())) {
                throw new InvalidEventException("a chave Kafka deve ser igual a user_id");
            }
        } catch (InvalidEventException exception) {
            saveRejected(record, exception.getMessage());
            return ProcessingOutcome.REJECTED;
        }

        connection.setAutoCommit(false);
        try {
            int inserted = insertEvent(record, event);
            if (inserted == 0) {
                connection.commit();
                return ProcessingOutcome.DUPLICATE;
            }
            updateMatrix(event);
            connection.commit();
            return ProcessingOutcome.ACCEPTED;
        } catch (SQLException exception) {
            connection.rollback();
            throw exception;
        } finally {
            connection.setAutoCommit(true);
        }
    }

    private void initialize() throws SQLException {
        try (Statement statement = connection.createStatement()) {
            statement.execute("PRAGMA journal_mode=WAL");
            statement.execute("PRAGMA synchronous=FULL");
            statement.execute("PRAGMA busy_timeout=5000");
            statement.executeUpdate("""
                    CREATE TABLE IF NOT EXISTS processed_events (
                        event_id TEXT PRIMARY KEY,
                        event_type TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        restaurant_id TEXT NOT NULL,
                        occurred_at TEXT NOT NULL,
                        text_value TEXT,
                        numeric_value INTEGER,
                        raw_json TEXT NOT NULL,
                        topic TEXT NOT NULL,
                        partition_id INTEGER NOT NULL,
                        record_offset INTEGER NOT NULL,
                        processed_at TEXT NOT NULL,
                        UNIQUE(topic, partition_id, record_offset)
                    )
                    """);
            statement.executeUpdate("""
                    CREATE TABLE IF NOT EXISTS rejected_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        topic TEXT NOT NULL,
                        partition_id INTEGER NOT NULL,
                        record_offset INTEGER NOT NULL,
                        kafka_key TEXT,
                        raw_json TEXT,
                        reason TEXT NOT NULL,
                        rejected_at TEXT NOT NULL,
                        UNIQUE(topic, partition_id, record_offset)
                    )
                    """);
            statement.executeUpdate(matrixSchema());
        }
    }

    private String matrixSchema() {
        return switch (kind) {
            case VIEW -> """
                    CREATE TABLE IF NOT EXISTS view_matrix (
                        user_id TEXT NOT NULL,
                        restaurant_id TEXT NOT NULL,
                        view_count INTEGER NOT NULL CHECK(view_count >= 0),
                        last_occurred_at TEXT NOT NULL,
                        last_event_id TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY(user_id, restaurant_id)
                    )
                    """;
            case COMMENT -> """
                    CREATE TABLE IF NOT EXISTS comment_matrix (
                        user_id TEXT NOT NULL,
                        restaurant_id TEXT NOT NULL,
                        comment_text TEXT NOT NULL,
                        occurred_at TEXT NOT NULL,
                        event_id TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY(user_id, restaurant_id)
                    )
                    """;
            case REVIEW -> """
                    CREATE TABLE IF NOT EXISTS review_matrix (
                        user_id TEXT NOT NULL,
                        restaurant_id TEXT NOT NULL,
                        stars INTEGER NOT NULL CHECK(stars BETWEEN 1 AND 5),
                        occurred_at TEXT NOT NULL,
                        event_id TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY(user_id, restaurant_id)
                    )
                    """;
        };
    }

    private int insertEvent(ConsumerRecord<String, String> record, InteractionEvent event) throws SQLException {
        String sql = """
                INSERT OR IGNORE INTO processed_events (
                    event_id, event_type, user_id, restaurant_id, occurred_at,
                    text_value, numeric_value, raw_json, topic, partition_id,
                    record_offset, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """;
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, event.eventId());
            statement.setString(2, event.type());
            statement.setString(3, event.userId());
            statement.setString(4, event.restaurantId());
            statement.setString(5, event.occurredAt().toString());
            statement.setString(6, event instanceof CommentEvent comment ? comment.text() : null);
            if (event instanceof ReviewEvent review) {
                statement.setInt(7, review.stars());
            } else {
                statement.setObject(7, null);
            }
            statement.setString(8, record.value());
            statement.setString(9, record.topic());
            statement.setInt(10, record.partition());
            statement.setLong(11, record.offset());
            statement.setString(12, Instant.now().toString());
            return statement.executeUpdate();
        }
    }

    private void updateMatrix(InteractionEvent event) throws SQLException {
        switch (kind) {
            case VIEW -> updateView((ViewEvent) event);
            case COMMENT -> updateComment((CommentEvent) event);
            case REVIEW -> updateReview((ReviewEvent) event);
        }
    }

    private void updateView(ViewEvent event) throws SQLException {
        String sql = """
                INSERT INTO view_matrix (
                    user_id, restaurant_id, view_count, last_occurred_at, last_event_id, updated_at
                ) VALUES (?, ?, 1, ?, ?, ?)
                ON CONFLICT(user_id, restaurant_id) DO UPDATE SET
                    view_count = view_matrix.view_count + 1,
                    last_occurred_at = CASE
                        WHEN excluded.last_occurred_at > view_matrix.last_occurred_at
                          OR (excluded.last_occurred_at = view_matrix.last_occurred_at
                              AND excluded.last_event_id > view_matrix.last_event_id)
                        THEN excluded.last_occurred_at ELSE view_matrix.last_occurred_at END,
                    last_event_id = CASE
                        WHEN excluded.last_occurred_at > view_matrix.last_occurred_at
                          OR (excluded.last_occurred_at = view_matrix.last_occurred_at
                              AND excluded.last_event_id > view_matrix.last_event_id)
                        THEN excluded.last_event_id ELSE view_matrix.last_event_id END,
                    updated_at = excluded.updated_at
                """;
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, event.userId());
            statement.setString(2, event.restaurantId());
            statement.setString(3, event.occurredAt().toString());
            statement.setString(4, event.eventId());
            statement.setString(5, Instant.now().toString());
            statement.executeUpdate();
        }
    }

    private void updateComment(CommentEvent event) throws SQLException {
        String sql = """
                INSERT INTO comment_matrix (
                    user_id, restaurant_id, comment_text, occurred_at, event_id, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, restaurant_id) DO UPDATE SET
                    comment_text = excluded.comment_text,
                    occurred_at = excluded.occurred_at,
                    event_id = excluded.event_id,
                    updated_at = excluded.updated_at
                WHERE excluded.occurred_at > comment_matrix.occurred_at
                   OR (excluded.occurred_at = comment_matrix.occurred_at
                       AND excluded.event_id > comment_matrix.event_id)
                """;
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, event.userId());
            statement.setString(2, event.restaurantId());
            statement.setString(3, event.text());
            statement.setString(4, event.occurredAt().toString());
            statement.setString(5, event.eventId());
            statement.setString(6, Instant.now().toString());
            statement.executeUpdate();
        }
    }

    private void updateReview(ReviewEvent event) throws SQLException {
        String sql = """
                INSERT INTO review_matrix (
                    user_id, restaurant_id, stars, occurred_at, event_id, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, restaurant_id) DO UPDATE SET
                    stars = excluded.stars,
                    occurred_at = excluded.occurred_at,
                    event_id = excluded.event_id,
                    updated_at = excluded.updated_at
                WHERE excluded.occurred_at > review_matrix.occurred_at
                   OR (excluded.occurred_at = review_matrix.occurred_at
                       AND excluded.event_id > review_matrix.event_id)
                """;
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, event.userId());
            statement.setString(2, event.restaurantId());
            statement.setInt(3, event.stars());
            statement.setString(4, event.occurredAt().toString());
            statement.setString(5, event.eventId());
            statement.setString(6, Instant.now().toString());
            statement.executeUpdate();
        }
    }

    private void saveRejected(ConsumerRecord<String, String> record, String reason) throws SQLException {
        String sql = """
                INSERT OR IGNORE INTO rejected_events (
                    topic, partition_id, record_offset, kafka_key, raw_json, reason, rejected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """;
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, record.topic());
            statement.setInt(2, record.partition());
            statement.setLong(3, record.offset());
            statement.setString(4, record.key());
            statement.setString(5, record.value());
            statement.setString(6, reason);
            statement.setString(7, Instant.now().toString());
            statement.executeUpdate();
        }
    }

    @Override
    public void close() throws SQLException {
        connection.close();
    }
}
