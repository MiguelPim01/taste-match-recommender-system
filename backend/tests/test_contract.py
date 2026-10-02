"""The Java side (kafka/common BackendContractTest) checks that the consumers accept these same examples."""

import json
import re
from pathlib import Path

import pytest

from tastematch_api.contracts import COMMENT, REVIEW, VIEW


EXAMPLES = Path(__file__).resolve().parents[2] / "kafka/common/src/test/resources/contracts/backend"


@pytest.mark.parametrize("kind, fields", [
    (VIEW, {}),
    (COMMENT, {"text": "Ótima massa, atendimento rápido."}),
    (REVIEW, {"stars": 5}),
])
def test_backend_publishes_the_examples_the_java_consumers_accept(kind, fields):
    expected = json.loads((EXAMPLES / f"{kind.prefix}.json").read_text(encoding="utf-8"))

    event = kind.build("app-0123456789abcdef", "r-contract", "contract-0001", **fields).model_dump()

    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", event["occurred_at"])
    assert event | {"occurred_at": expected["occurred_at"]} == expected
