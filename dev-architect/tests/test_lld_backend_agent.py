#!/usr/bin/env python
import sys
from types import SimpleNamespace

sys.path.insert(0, "src")

from lld_backend_agent.lldback import _extract_response_text


class DummyResponse:
    def __init__(self, output):
        self.output = output


def test_extract_response_text_from_string_output():
    response = DummyResponse("hello world")
    assert _extract_response_text(response) == "hello world"


def test_extract_response_text_from_non_string_output():
    response = DummyResponse(12345)
    assert _extract_response_text(response) == "12345"


def test_extract_response_text_from_custom_length_object():
    class WeirdOutput:
        def __len__(self):
            return 100000

        def __str__(self):
            return "short text"

    response = DummyResponse(WeirdOutput())
    assert _extract_response_text(response) == "short text"


def test_extract_response_text_from_none_output():
    response = DummyResponse(None)
    assert _extract_response_text(response) == ""
