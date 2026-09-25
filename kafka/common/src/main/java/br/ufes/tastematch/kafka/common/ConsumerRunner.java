package br.ufes.tastematch.kafka.common;

import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.Properties;
import java.util.concurrent.atomic.AtomicBoolean;

public final class ConsumerRunner {
    private static final Logger LOGGER = LoggerFactory.getLogger(ConsumerRunner.class);

    private final EventKind kind;
    private final AtomicBoolean running = new AtomicBoolean(true);

    public ConsumerRunner(EventKind kind) {
        this.kind = kind;
    }

    public void run() {
        Runtime.getRuntime().addShutdownHook(new Thread(() -> running.set(false)));
        while (running.get()) {
            try {
                consumeUntilStopped();
            } catch (Exception exception) {
                if (running.get()) {
                    LOGGER.error("Consumidor {} falhou; reiniciando sem confirmar o lote atual", kind, exception);
                    sleepAfterFailure();
                }
            }
        }
    }

    private void consumeUntilStopped() throws Exception {
        Path databasePath = Path.of(AppEnvironment.value("DATABASE_PATH", defaultDatabasePath()));
        try (SQLiteMatrixStore store = new SQLiteMatrixStore(databasePath, kind);
             KafkaConsumer<String, String> consumer = new KafkaConsumer<>(properties())) {
            consumer.subscribe(List.of(kind.topic()));
            LOGGER.info("Consumidor iniciado: topic={}, group={}, database={}",
                    kind.topic(), groupId(), databasePath.toAbsolutePath());

            while (running.get()) {
                var records = consumer.poll(Duration.ofSeconds(1));
                for (ConsumerRecord<String, String> record : records) {
                    ProcessingOutcome outcome = store.process(record);
                    LOGGER.info("Evento processado: outcome={}, eventTopic={}, partition={}, offset={}",
                            outcome, record.topic(), record.partition(), record.offset());
                }
                if (!records.isEmpty()) {
                    consumer.commitSync();
                }
            }
        }
    }

    private Properties properties() {
        Properties properties = new Properties();
        properties.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG,
                AppEnvironment.value("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092,localhost:39092,localhost:49092"));
        properties.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        properties.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        properties.put(ConsumerConfig.GROUP_ID_CONFIG, groupId());
        properties.put(ConsumerConfig.CLIENT_ID_CONFIG, kind.name().toLowerCase() + "-matrix-consumer");
        properties.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, false);
        properties.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
        properties.put(ConsumerConfig.MAX_POLL_RECORDS_CONFIG, 100);
        return properties;
    }

    private String groupId() {
        return kind.name().toLowerCase() + "-matrix-consumer-v1";
    }

    private String defaultDatabasePath() {
        return "data/" + switch (kind) {
            case VIEW -> "views.db";
            case COMMENT -> "comments.db";
            case REVIEW -> "reviews.db";
        };
    }

    private void sleepAfterFailure() {
        try {
            Thread.sleep(3_000);
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            running.set(false);
        }
    }
}
