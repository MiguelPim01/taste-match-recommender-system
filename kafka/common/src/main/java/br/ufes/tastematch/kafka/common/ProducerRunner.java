package br.ufes.tastematch.kafka.common;

import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.clients.producer.RecordMetadata;
import org.apache.kafka.common.serialization.StringSerializer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Properties;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.LongFunction;

public final class ProducerRunner {
    private static final Logger LOGGER = LoggerFactory.getLogger(ProducerRunner.class);

    private final EventKind kind;
    private final LongFunction<? extends InteractionEvent> generator;
    private final EventCodec codec = new EventCodec();
    private final AtomicBoolean running = new AtomicBoolean(true);

    public ProducerRunner(EventKind kind, LongFunction<? extends InteractionEvent> generator) {
        this.kind = kind;
        this.generator = generator;
    }

    public void run() {
        Runtime.getRuntime().addShutdownHook(new Thread(() -> running.set(false)));
        long intervalMs = AppEnvironment.positiveInt("PRODUCER_INTERVAL_MS", 1_000);
        long sequence = 0;

        try (KafkaProducer<String, String> producer = new KafkaProducer<>(properties())) {
            LOGGER.info("Produtor iniciado: topic={}, intervalMs={}", kind.topic(), intervalMs);
            while (running.get()) {
                InteractionEvent event = generator.apply(sequence++);
                ProducerRecord<String, String> record = new ProducerRecord<>(
                        kind.topic(), event.userId(), codec.encode(event));
                try {
                    RecordMetadata metadata = producer.send(record).get();
                    LOGGER.info("Evento publicado: eventId={}, topic={}, partition={}, offset={}",
                            event.eventId(), metadata.topic(), metadata.partition(), metadata.offset());
                    Thread.sleep(intervalMs);
                } catch (InterruptedException exception) {
                    Thread.currentThread().interrupt();
                    running.set(false);
                } catch (Exception exception) {
                    LOGGER.error("Falha ao publicar em {}; nova tentativa será feita", kind.topic(), exception);
                    sleepAfterFailure();
                }
            }
        }
    }

    private Properties properties() {
        Properties properties = new Properties();
        properties.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG,
                AppEnvironment.value("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092,localhost:39092,localhost:49092"));
        properties.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        properties.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        properties.put(ProducerConfig.ACKS_CONFIG, "all");
        properties.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);
        properties.put(ProducerConfig.CLIENT_ID_CONFIG, kind.name().toLowerCase() + "-producer");
        properties.put(ProducerConfig.RETRY_BACKOFF_MS_CONFIG, 1_000);
        return properties;
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
