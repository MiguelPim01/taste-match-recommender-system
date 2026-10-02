package br.ufes.tastematch.kafka.common;

import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

/**
 * The backend test (backend/tests/test_contract.py) checks that the API publishes exactly these examples;
 * this one checks that the consumers accept them, through the same path a Kafka record takes.
 */
class BackendContractTest {
    @TempDir
    Path temporaryDirectory;

    @ParameterizedTest
    @EnumSource(EventKind.class)
    void consumersAcceptWhatTheBackendPublishes(EventKind kind) throws Exception {
        String json = example(kind);
        InteractionEvent event = new EventCodec().decode(json, kind);

        try (SQLiteMatrixStore store = new SQLiteMatrixStore(temporaryDirectory.resolve(kind + ".db"), kind)) {
            ConsumerRecord<String, String> record = new ConsumerRecord<>(kind.topic(), 0, 0, event.userId(), json);
            assertEquals(ProcessingOutcome.ACCEPTED, store.process(record));
        }
    }

    private static String example(EventKind kind) throws Exception {
        String path = "/contracts/backend/" + kind.name().toLowerCase() + ".json";
        try (InputStream stream = BackendContractTest.class.getResourceAsStream(path)) {
            assertNotNull(stream, "Exemplo de contrato ausente: " + path);
            return new String(stream.readAllBytes(), StandardCharsets.UTF_8);
        }
    }
}
