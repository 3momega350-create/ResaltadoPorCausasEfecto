import pytest
from main import setup_causal_matcher, nlp, analyze_text


def run_and_collect(text):
    matcher = setup_causal_matcher(nlp)
    return analyze_text(text, matcher)


def test_because_pattern():
    text = "The mission failed because the engine overheated."
    highlights = run_and_collect(text)
    # should detect a cause and an effect (or at least a causal_sentence)
    assert any(h[0] in ('cause','effect','causal_sentence') for h in highlights)


def test_if_then_pattern():
    text = "If you heat water, it boils."
    highlights = run_and_collect(text)
    assert any(h[0] in ('cause','effect','causal_sentence') for h in highlights)


def test_leads_to_pattern():
    text = "The storm led to power outages."
    highlights = run_and_collect(text)
    assert any(h[0] in ('cause','effect','causal_sentence') for h in highlights)
