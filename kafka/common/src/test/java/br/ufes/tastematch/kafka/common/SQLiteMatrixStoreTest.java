package br.ufes.tastematch.kafka.common;

import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Path;
import java.sql.DriverManager;
import java.time.Instant;

import static org.junit.jupiter.api.Assertions.assertEquals;

class SQLiteMatrixStoreTest {
    private final EventCodec codec = new EventCodec();

    @TempDir
    Path temporaryDirectory;

    @Test
    void countsAViewOnlyOnceWhenEventIsRedelivered() throws Exception {
        Path database = temporaryDirectory.resolve("views.db");
        ViewEvent event = new ViewEvent(1, "view-1", EventKind.VIEW.eventType(),
                "user-1", "restaurant-1", Instant.parse("2026-09-25T12:00:00Z"));

        try (SQLiteMatrixStore store = new SQLiteMatrixStore(database, EventKind.VIEW)) {
            assertEquals(ProcessingOutcome.ACCEPTED, store.process(record(EventKind.VIEW, 0, event)));
            assertEquals(ProcessingOutcome.DUPLICATE, store.process(record(EventKind.VIEW, 1, event)));
        }

        assertEquals(1, queryInt(database, "SELECT view_count FROM view_matrix"));
        assertEquals(1, queryInt(database, "SELECT COUNT(*) FROM processed_events"));
    }

    @Test
    void keepsLatestCommentUsingEventIdAsTieBreaker() throws Exception {
        Path database = temporaryDirectory.resolve("comments.db");
        Instant instant = Instant.parse("2026-09-25T12:00:00Z");
        CommentEvent laterTie = new CommentEvent(1, "comment-c", EventKind.COMMENT.eventType(),
                "user-1", "restaurant-1", instant, "winner");
        CommentEvent earlierTie = new CommentEvent(1, "comment-b", EventKind.COMMENT.eventType(),
                "user-1", "restaurant-1", instant, "older tie");
        CommentEvent older = new CommentEvent(1, "comment-z", EventKind.COMMENT.eventType(),
                "user-1", "restaurant-1", instant.minusSeconds(60), "old");

        try (SQLiteMatrixStore store = new SQLiteMatrixStore(database, EventKind.COMMENT)) {
            store.process(record(EventKind.COMMENT, 0, earlierTie));
            store.process(record(EventKind.COMMENT, 1, older));
            store.process(record(EventKind.COMMENT, 2, laterTie));
        }

        assertEquals("winner", queryString(database, "SELECT comment_text FROM comment_matrix"));
        assertEquals(3, queryInt(database, "SELECT COUNT(*) FROM processed_events"));
    }

    @Test
    void recordsInvalidMessageWithoutAddingItToMatrix() throws Exception {
        Path database = temporaryDirectory.resolve("reviews.db");
        String invalid = """
                {"schema_version":1,"event_id":"bad","type":"restaurant.rated",
                 "user_id":"user-1","restaurant_id":"restaurant-1",
                 "occurred_at":"2026-09-25T12:00:00Z","stars":9}
                """;
        ConsumerRecord<String, String> record = new ConsumerRecord<>(EventKind.REVIEW.topic(), 0, 0,
                "user-1", invalid);

        try (SQLiteMatrixStore store = new SQLiteMatrixStore(database, EventKind.REVIEW)) {
            assertEquals(ProcessingOutcome.REJECTED, store.process(record));
            assertEquals(ProcessingOutcome.REJECTED, store.process(record));
        }

        assertEquals(1, queryInt(database, "SELECT COUNT(*) FROM rejected_events"));
        assertEquals(0, queryInt(database, "SELECT COUNT(*) FROM review_matrix"));
    }

    @Test
    void rejectsKafkaKeyThatDoesNotMatchUser() throws Exception {
        Path database = temporaryDirectory.resolve("key.db");
        ReviewEvent event = new ReviewEvent(1, "review-1", EventKind.REVIEW.eventType(),
                "user-1", "restaurant-1", Instant.parse("2026-09-25T12:00:00Z"), 4);
        ConsumerRecord<String, String> record = new ConsumerRecord<>(EventKind.REVIEW.topic(), 0, 0,
                "another-user", codec.encode(event));

        try (SQLiteMatrixStore store = new SQLiteMatrixStore(database, EventKind.REVIEW)) {
            assertEquals(ProcessingOutcome.REJECTED, store.process(record));
        }

        assertEquals(1, queryInt(database, "SELECT COUNT(*) FROM rejected_events"));
    }

    private ConsumerRecord<String, String> record(EventKind kind, long offset, InteractionEvent event) {
        return new ConsumerRecord<>(kind.topic(), 0, offset, event.userId(), codec.encode(event));
    }

    private static int queryInt(Path database, String sql) throws Exception {
        try (var connection = DriverManager.getConnection("jdbc:sqlite:" + database.toAbsolutePath());
             var statement = connection.createStatement();
             var result = statement.executeQuery(sql)) {
            return result.getInt(1);
        }
    }

    private static String queryString(Path database, String sql) throws Exception {
        try (var connection = DriverManager.getConnection("jdbc:sqlite:" + database.toAbsolutePath());
             var statement = connection.createStatement();
             var result = statement.executeQuery(sql)) {
            return result.getString(1);
        }
    }
}
