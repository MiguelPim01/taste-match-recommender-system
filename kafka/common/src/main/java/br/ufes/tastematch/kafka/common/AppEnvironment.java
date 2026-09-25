package br.ufes.tastematch.kafka.common;

public final class AppEnvironment {
    private AppEnvironment() {
    }

    public static String value(String name, String defaultValue) {
        String configured = System.getenv(name);
        return configured == null || configured.isBlank() ? defaultValue : configured;
    }

    public static int positiveInt(String name, int defaultValue) {
        String configured = System.getenv(name);
        if (configured == null || configured.isBlank()) {
            return defaultValue;
        }
        try {
            int value = Integer.parseInt(configured);
            if (value <= 0) {
                throw new IllegalArgumentException(name + " deve ser maior que zero");
            }
            return value;
        } catch (NumberFormatException exception) {
            throw new IllegalArgumentException(name + " deve ser um número inteiro", exception);
        }
    }
}
