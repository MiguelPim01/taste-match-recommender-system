package br.ufes.tastematch.kafka.common;

import java.time.Instant;

public sealed interface InteractionEvent permits ViewEvent, CommentEvent, ReviewEvent {
    int schemaVersion();
    String eventId();
    String type();
    String userId();
    String restaurantId();
    Instant occurredAt();
}
