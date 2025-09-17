"""Orquesta el análisis: matcher, heurísticas, normalización y HTML."""
from spacy_utils import load_spacy_model, add_entity_ruler
from matcher_utils import setup_causal_matcher
from heuristics import extract_cause_effect_basic
from pdf_utils import extract_text_from_pdf, extract_text_from_scanned_pdf
from spacy_utils import load_spacy_model
import logging

logger = logging.getLogger(__name__)


def normalize_and_merge_spans(text, spans):
    normalized = []
    for s in spans:
        if isinstance(s, dict):
            normalized.append((s.get('role'), s.get('start'), s.get('end')))
        else:
            normalized.append(s)
    if not normalized:
        return []
    normalized.sort(key=lambda x: (x[1], -(x[2] - x[1])))
    merged = []
    for role, start, end in normalized:
        if not merged:
            merged.append([role, start, end])
            continue
        last_role, last_s, last_e = merged[-1]
        if start <= last_e:
            priority = {'cause': 2, 'effect': 2, 'causal_sentence': 1}
            if priority.get(role, 0) > priority.get(last_role, 0):
                merged[-1] = [role, start, max(end, last_e)]
            else:
                merged[-1][2] = max(last_e, end)
        else:
            merged.append([role, start, end])
    return [{'role': r, 'start': a, 'end': b, 'text': text[a:b]} for r, a, b in merged]


def analyze_text(text: str, nlp):
    matcher = setup_causal_matcher(nlp)
    doc = nlp(text)
    highlights = []
    matches = matcher(doc)
    matched_sent_starts = set()
    for match_id, start, end in matches:
        span = doc[start:end]
        sent = span.sent
        if sent.start in matched_sent_starts:
            continue
        ce = extract_cause_effect_basic(sent)
        if ce:
            for role, a, b in ce:
                highlights.append({'role': role, 'start': a, 'end': b, 'text': text[a:b]})
        else:
            highlights.append({'role': 'causal_sentence', 'start': sent.start_char, 'end': sent.end_char, 'text': sent.text})
        matched_sent_starts.add(sent.start)
    if not highlights:
        causal_markers = ["because", "due to", "as a result", "leads to", "lead to", "if", "then"]
        for sent in doc.sents:
            if any(m in sent.text.lower() for m in causal_markers):
                ce = extract_cause_effect_basic(sent)
                if ce:
                    for role, a, b in ce:
                        highlights.append({'role': role, 'start': a, 'end': b, 'text': text[a:b]})
                else:
                    highlights.append({'role': 'causal_sentence', 'start': sent.start_char, 'end': sent.end_char, 'text': sent.text})
    return normalize_and_merge_spans(text, highlights)
