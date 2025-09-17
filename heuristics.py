"""Heurísticas para identificar spans de causa y efecto en oraciones."""
import re


def extract_cause_effect_basic(sent):
    text = sent.text
    lower = text.lower()
    base = sent.start_char
    if 'because' in lower:
        idx = lower.find('because')
        left = text[:idx].strip()
        right = text[idx + len('because'):].strip(' ,.')
        spans = []
        if left:
            s = base + text.find(left)
            spans.append(('effect', s, s + len(left)))
        if right:
            s2 = base + text.find(right)
            spans.append(('cause', s2, s2 + len(right)))
        return spans
    m = re.search(r"\bif\b\s*(.+?),\s*(then\s*)?(.+)", lower)
    if m:
        cause = m.group(1).strip()
        effect = m.group(3).strip()
        if cause and effect:
            s1 = base + text.lower().find(cause)
            s2 = base + text.lower().find(effect)
            return [('cause', s1, s1 + len(cause)), ('effect', s2, s2 + len(effect))]
    m2 = re.search(r"(.+?)\s+lead[s]?\s+to\s+(.+)", lower)
    if m2:
        left = m2.group(1).strip()
        right = m2.group(2).strip()
        s1 = base + text.lower().find(left)
        s2 = base + text.lower().find(right)
        return [('cause', s1, s1 + len(left)), ('effect', s2, s2 + len(right))]
    return []
