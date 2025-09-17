"""Configuración del Matcher para detectar marcadores causales."""
from spacy.matcher import Matcher


def setup_causal_matcher(nlp):
    matcher = Matcher(nlp.vocab)
    patterns = [
        [{"LOWER": "because"}],
        [{"LOWER": "due"}, {"LOWER": "to"}],
        [{"LEMMA": "cause"}],
        [{"LEMMA": "lead"}, {"LOWER": "to"}],
        [{"LOWER": "as"}, {"LOWER": "a"}, {"LOWER": "result"}, {"LOWER": "of"}],
    ]
    matcher.add("CAUSAL_MARKER", patterns)
    return matcher
