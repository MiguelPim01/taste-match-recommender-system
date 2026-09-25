package br.ufes.tastematch.kafka.common;

import java.time.Instant;

public record ViewEvent(
        int schemaVersion,
        String eventId,
        String type,
        String userId,
        String restaurantId,
        Instant occurredAt
) implements InteractionEvent {
}
