package br.ufes.tastematch.kafka.common;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;

public final class EventCodec {
    private final ObjectMapper mapper;

    public EventCodec() {
        mapper = JsonMapper.builder()
                .addModule(new JavaTimeModule())
                .propertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE)
                .disable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES)
                .build();
    }

    public String encode(InteractionEvent event) {
        try {
            return mapper.writeValueAsString(event);
        } catch (JsonProcessingException exception) {
            throw new IllegalArgumentException("Não foi possível serializar o evento", exception);
        }
    }

    public InteractionEvent decode(String json, EventKind kind) throws InvalidEventException {
        final InteractionEvent event;
        try {
            event = mapper.readValue(json, kind.eventClass());
        } catch (JsonProcessingException exception) {
            throw new InvalidEventException("JSON inválido: " + exception.getOriginalMessage(), exception);
        }
        validate(event, kind);
        return event;
    }

    private static void validate(InteractionEvent event, EventKind kind) throws InvalidEventException {
        require(event.schemaVersion() == 1, "schema_version deve ser 1");
        require(kind.eventType().equals(event.type()), "type deve ser " + kind.eventType());
        require(notBlank(event.eventId()), "event_id é obrigatório");
        require(notBlank(event.userId()), "user_id é obrigatório");
        require(notBlank(event.restaurantId()), "restaurant_id é obrigatório");
        require(event.occurredAt() != null, "occurred_at é obrigatório e deve usar ISO 8601");

        if (event instanceof CommentEvent comment) {
            require(notBlank(comment.text()), "text deve ser uma string não vazia");
        }
        if (event instanceof ReviewEvent review) {
            require(review.stars() >= 1 && review.stars() <= 5, "stars deve ser um inteiro entre 1 e 5");
        }
    }

    private static boolean notBlank(String value) {
        return value != null && !value.isBlank();
    }

    private static void require(boolean condition, String message) throws InvalidEventException {
        if (!condition) {
            throw new InvalidEventException(message);
        }
    }
}
