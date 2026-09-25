package br.ufes.tastematch.kafka.common;

import org.junit.jupiter.api.Test;

import java.time.Instant;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class EventCodecTest {
    private final EventCodec codec = new EventCodec();

    @Test
    void roundTripsAValidReview() throws Exception {
        ReviewEvent original = new ReviewEvent(1, "review-1", "restaurant.rated",
                "user-1", "restaurant-2", Instant.parse("2026-09-25T12:00:00Z"), 5);

        InteractionEvent decoded = codec.decode(codec.encode(original), EventKind.REVIEW);

        assertEquals(original, decoded);
    }

    @Test
    void ignoresUnknownFieldsForForwardCompatibility() throws Exception {
        String json = """
                {"schema_version":1,"event_id":"view-1","type":"restaurant.viewed",
                 "user_id":"user-1","restaurant_id":"restaurant-1",
                 "occurred_at":"2026-09-25T12:00:00Z","future_field":true}
                """;

        ViewEvent event = (ViewEvent) codec.decode(json, EventKind.VIEW);

        assertEquals("view-1", event.eventId());
    }

    @Test
    void rejectsWrongTypeAndInvalidPayloads() {
        String wrongType = """
                {"schema_version":1,"event_id":"x","type":"restaurant.commented",
                 "user_id":"u","restaurant_id":"r","occurred_at":"2026-09-25T12:00:00Z"}
                """;
        String invalidStars = """
                {"schema_version":1,"event_id":"x","type":"restaurant.rated",
                 "user_id":"u","restaurant_id":"r","occurred_at":"2026-09-25T12:00:00Z","stars":6}
                """;

        assertThrows(InvalidEventException.class, () -> codec.decode(wrongType, EventKind.VIEW));
        assertThrows(InvalidEventException.class, () -> codec.decode(invalidStars, EventKind.REVIEW));
        assertThrows(InvalidEventException.class, () -> codec.decode("not-json", EventKind.VIEW));
    }
}
