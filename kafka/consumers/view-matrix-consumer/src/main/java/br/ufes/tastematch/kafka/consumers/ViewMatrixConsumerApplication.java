package br.ufes.tastematch.kafka.consumers;

import br.ufes.tastematch.kafka.common.ConsumerRunner;
import br.ufes.tastematch.kafka.common.EventKind;

public final class ViewMatrixConsumerApplication {
    private ViewMatrixConsumerApplication() {
    }

    public static void main(String[] args) {
        new ConsumerRunner(EventKind.VIEW).run();
    }
}
