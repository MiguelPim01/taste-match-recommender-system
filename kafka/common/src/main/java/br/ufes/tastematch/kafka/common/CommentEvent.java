package br.ufes.tastematch.kafka.common;

import java.time.Instant;

public record CommentEvent(
        int schemaVersion,
        String eventId,
        String type,
        String userId,
        String restaurantId,
        Instant occurredAt,
        String text
) implements InteractionEvent {
}
