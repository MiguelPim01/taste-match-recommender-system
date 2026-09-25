package br.ufes.tastematch.kafka.producers;

import br.ufes.tastematch.kafka.common.AppEnvironment;
import br.ufes.tastematch.kafka.common.DemoEventFactory;
import br.ufes.tastematch.kafka.common.EventKind;
import br.ufes.tastematch.kafka.common.ProducerRunner;

public final class ViewProducerApplication {
    private ViewProducerApplication() {
    }

    public static void main(String[] args) {
        DemoEventFactory factory = new DemoEventFactory(
                AppEnvironment.positiveInt("DEMO_USER_COUNT", 5),
                AppEnvironment.positiveInt("DEMO_RESTAURANT_COUNT", 8));
        new ProducerRunner(EventKind.VIEW, factory::view).run();
    }
}
