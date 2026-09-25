package br.ufes.tastematch.kafka.common;

public final class InvalidEventException extends Exception {
    public InvalidEventException(String message) {
        super(message);
    }

    public InvalidEventException(String message, Throwable cause) {
        super(message, cause);
    }
}
