package br.ufes.tastematch.kafka.common;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public final class DemoEventFactory {
    private static final List<String> COMMENTS = List.of(
            "Excellent food and friendly staff.",
            "Good value and quick service.",
            "The meal was fine, but the wait was long.",
            "Fresh ingredients and a pleasant atmosphere.",
            "I would visit this restaurant again."
    );

    private final int userCount;
    private final int restaurantCount;

    public DemoEventFactory(int userCount, int restaurantCount) {
        this.userCount = userCount;
        this.restaurantCount = restaurantCount;
    }

    public ViewEvent view(long sequence) {
        return new ViewEvent(1, id("view"), EventKind.VIEW.eventType(), user(sequence),
                restaurant(sequence), Instant.now());
    }

    public CommentEvent comment(long sequence) {
        return new CommentEvent(1, id("comment"), EventKind.COMMENT.eventType(), user(sequence),
                restaurant(sequence), Instant.now(), COMMENTS.get((int) (sequence % COMMENTS.size())));
    }

    public ReviewEvent review(long sequence) {
        return new ReviewEvent(1, id("review"), EventKind.REVIEW.eventType(), user(sequence),
                restaurant(sequence), Instant.now(), (int) (sequence % 5) + 1);
    }

    private String user(long sequence) {
        return "user-" + (sequence % userCount + 1);
    }

    private String restaurant(long sequence) {
        long distributed = sequence * 7 + sequence / userCount;
        return "restaurant-" + (distributed % restaurantCount + 1);
    }

    private static String id(String prefix) {
        return prefix + "-" + UUID.randomUUID();
    }
}
