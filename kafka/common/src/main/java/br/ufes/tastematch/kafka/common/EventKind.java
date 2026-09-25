package br.ufes.tastematch.kafka.common;

public enum EventKind {
    VIEW("view-restaurant", "restaurant.viewed", ViewEvent.class),
    COMMENT("comment-restaurant", "restaurant.commented", CommentEvent.class),
    REVIEW("review-restaurant", "restaurant.rated", ReviewEvent.class);

    private final String topic;
    private final String eventType;
    private final Class<? extends InteractionEvent> eventClass;

    EventKind(String topic, String eventType, Class<? extends InteractionEvent> eventClass) {
        this.topic = topic;
        this.eventType = eventType;
        this.eventClass = eventClass;
    }

    public String topic() {
        return topic;
    }

    public String eventType() {
        return eventType;
    }

    public Class<? extends InteractionEvent> eventClass() {
        return eventClass;
    }
}
