package br.ufes.tastematch.kafka.common;

import java.time.Instant;

public record ReviewEvent(
        int schemaVersion,
        String eventId,
        String type,
        String userId,
        String restaurantId,
        Instant occurredAt,
        int stars
) implements InteractionEvent {
}
