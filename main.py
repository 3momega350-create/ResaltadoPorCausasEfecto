"""Launcher mínimo: sólo importa y orquesta las llamadas entre módulos.

Este archivo debe contener únicamente la lógica de orquestación —toda la
funcionalidad real vive en los módulos: `spacy_utils`, `matcher_utils`,
`pdf_utils`, `heuristics`, `analyzer`, `html_utils` y `gui`.
"""

import sys
from spacy_utils import load_spacy_model
from analyzer import analyze_text
from pdf_utils import extract_text_from_pdf, extract_text_from_scanned_pdf
from html_utils import generate_html_report


def select_file_and_process(path: str):
    """Orquesta el pipeline: extrae texto, carga spaCy, analiza y escribe HTML.

    Esta función delega todo a los módulos apropiados.
    """
    if not path or not path.strip():
        raise FileNotFoundError(path)
    ext = path.split('.')[-1].lower()
    if ext == 'pdf':
        text = extract_text_from_pdf(path)
        if not text.strip():
            text = extract_text_from_scanned_pdf(path)
    else:
        with open(path, 'r', encoding='utf-8') as fh:
            text = fh.read()

    nlp = load_spacy_model()
    highlights = analyze_text(text, nlp)
    generate_html_report(text, highlights)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        select_file_and_process(sys.argv[1])
    else:
        try:
            from gui import run_gui
            run_gui()
        except Exception:
            print("Uso: python main.py <archivo>\nO la GUI no está disponible.")


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extrae texto de un PDF. Usa `pypdf` si está disponible o `PyPDF2` como fallback.

    Devuelve cadena (vacía si falla).
    """
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        texts = []
        for page in getattr(reader, 'pages', []):
            try:
                texts.append(page.extract_text() or "")
            except Exception:
                texts.append("")
        return "\n".join(texts)
    except Exception:
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(pdf_path)
            texts = []
            for page in reader.pages:
                try:
                    texts.append(page.extract_text() or "")
                except Exception:
                    texts.append("")
            return "\n".join(texts)
        except Exception:
            logger.exception("Error extrayendo texto del PDF. Instale 'pypdf' o 'PyPDF2'.")
            return ""


def extract_text_from_scanned_pdf(pdf_path: str, dpi: int = 200) -> str:
    """OCR para PDFs escaneados (requiere `pdf2image` y `pytesseract`)."""
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except Exception:
        logger.exception("Dependencias OCR no instaladas ('pdf2image','pytesseract').")
        return ""
    try:
        pages = convert_from_path(pdf_path, dpi=dpi)
        texts = [pytesseract.image_to_string(img) for img in pages]
        return "\n".join(texts)
    except Exception:
        logger.exception("Error durante OCR del PDF escaneado.")
        return ""


def extract_cause_effect(sent):
    """Heurísticas para extraer spans aproximados de causa y efecto en una oración.

    - Devuelve lista de tuplas (role, start_char, end_char).
    - Reemplaza o amplía estas reglas según necesites más precisión.
    """
    text = sent.text
    lower = text.lower()
    base = sent.start_char

    # 'because' -> antes = efecto, después = causa (estructura común)
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

    # 'if X, then Y' -> X=cause, Y=effect
    m = re.search(r"\bif\b\s*(.+?),\s*(then\s*)?(.+)", lower)
    if m:
        cause = m.group(1).strip()
        effect = m.group(3).strip()
        if cause and effect:
            s1 = base + text.lower().find(cause)
            s2 = base + text.lower().find(effect)
            return [('cause', s1, s1 + len(cause)), ('effect', s2, s2 + len(effect))]

    # 'X leads to Y'
    m2 = re.search(r"(.+?)\s+lead[s]?\s+to\s+(.+)", lower)
    if m2:
        left = m2.group(1).strip()
        right = m2.group(2).strip()
        s1 = base + text.lower().find(left)
        s2 = base + text.lower().find(right)
        return [('cause', s1, s1 + len(left)), ('effect', s2, s2 + len(right))]

    return []


def normalize_and_merge_spans(text, spans):
    """Normaliza y resuelve solapamientos entre spans detectados."""
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


def analyze_text(text: str, matcher):
    """Orquesta el análisis de un texto y devuelve los highlights listos para HTML."""
    doc = nlp(text)
    highlights = []

    matches = matcher(doc)
    seen = set()
    for match_id, start, end in matches:
        span = doc[start:end]
        sent = span.sent
        if sent.start in seen:
            continue
        ce = extract_cause_effect(sent)
        if ce:
            for role, a, b in ce:
                highlights.append({'role': role, 'start': a, 'end': b, 'text': text[a:b]})
        else:
            highlights.append({'role': 'causal_sentence', 'start': sent.start_char, 'end': sent.end_char, 'text': sent.text})
        seen.add(sent.start)

    if not highlights:
        causal_markers = ["because", "due to", "as a result", "leads to", "lead to", "if", "then"]
        for sent in doc.sents:
            if any(m in sent.text.lower() for m in causal_markers):
                ce = extract_cause_effect(sent)
                if ce:
                    for role, a, b in ce:
                        highlights.append({'role': role, 'start': a, 'end': b, 'text': text[a:b]})
                else:
                    highlights.append({'role': 'causal_sentence', 'start': sent.start_char, 'end': sent.end_char, 'text': sent.text})

    return normalize_and_merge_spans(text, highlights)


def generate_html_report(text: str, highlights, out_path: str = "highlighted_report.html"):
    """Genera un HTML con los spans resaltados. Modifica `css` para cambiar estilos."""
    css = """
    body { font-family: sans-serif; line-height: 1.6; padding: 20px; }
    .causal_sentence { background-color: #fff8c4; padding: 3px; border-radius: 4px; }
    .cause { background-color: #ffd6d6; padding: 2px; border-radius: 3px; }
    .effect { background-color: #d6ffd6; padding: 2px; border-radius: 3px; }
    .legend span { display:inline-block; margin-right:10px; padding:4px; border-radius:4px; }
    """

    pieces = []
    last = 0
    hs = sorted(highlights, key=lambda h: h['start']) if highlights else []
    for h in hs:
        if h['start'] > last:
            pieces.append(text[last:h['start']])
        seg = text[h['start']:h['end']]
        pieces.append(f'<span class="{h["role"]}">{seg}</span>')
        last = h['end']
    if last < len(text):
        pieces.append(text[last:])

    html = f"""
    <html>
    <head><meta charset='utf-8'><style>{css}</style></head>
    <body>
    <h1>Causal Analysis Report</h1>
    <div class='legend'><span class='cause'>Cause</span> <span class='effect'>Effect</span> <span class='causal_sentence'>Causal sentence</span></div>
    <div class='content'>
    {''.join(pieces)}
    </div>
    </body>
    </html>
    """

    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write(html)
    logger.info("HTML report escrito en %s", out_path)


def select_file_and_process(path: str):
    """Flujo completo: extrae texto de `path`, analiza y genera HTML."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    ext = os.path.splitext(path)[1].lower()
    if ext == '.pdf':
        text = extract_text_from_pdf(path)
        if not text.strip():
            logger.info("No se extrajo texto; intentando OCR para PDF escaneado.")
            text = extract_text_from_scanned_pdf(path)
    else:
        with open(path, 'r', encoding='utf-8') as fh:
            text = fh.read()

    matcher = setup_causal_matcher(nlp)
    highlights = analyze_text(text, matcher)
    generate_html_report(text, highlights)


def run_gui():
    """Interfaz mínima usando tkinter. Importa tkinter internamente para evitar dependencia global."""
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except Exception:
        logger.exception("tkinter no disponible; GUI deshabilitada.")
        return

    root = tk.Tk()
    root.title("Causa-Efecto Highlighter")

    def pick_and_run():
        p = filedialog.askopenfilename()
        if p:
            try:
                select_file_and_process(p)
                messagebox.showinfo("Listo", "Reporte generado: highlighted_report.html")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    btn = tk.Button(root, text="Seleccionar archivo y analizar", command=pick_and_run)
    btn.pack(padx=20, pady=20)
    root.mainloop()


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        select_file_and_process(sys.argv[1])
    else:
        print("Uso: python main.py <archivo>\nO ejecute run_gui() en una sesión interactiva para iniciar la GUI.")


def extract_cause_effect(sent):
    """Intenta identificar spans de 'cause' y 'effect' dentro de una oración spaCy `sent`.

    Estrategia heurística:
    - Buscar conjunciones y marcadores ('because', 'due to', 'caused by', 'leads to', 'if', 'then').
    - Usar dependencias y búsquedas por token para dividir la oración en causa/efecto aproximados.
    - Devolver lista de tuplas: (role, start_char, end_char) con role en {'cause','effect'}.
    """
    sent_doc = sent.as_doc()
    lower_text = sent.text.lower()
    spans = []

    # Marcadores comunes y su tratamiento
    markers = ["because", "due to", "caused by", "causes", "cause", "leads to", "lead to", "led to", "if", "then", "therefore", "so that", "as a result"]

    # Buscar tokens que sean marcadores
    marker_token = None
    marker_text = None
    for tok in sent_doc:
        for m in markers:
            if tok.text.lower() == m.split()[0] and m in lower_text:
                marker_token = tok
                marker_text = m
                break
        if marker_token:
            break

    def add_span_by_chars(role, abs_start, abs_end):
        spans.append((role, abs_start, abs_end))

    # Heurística 1: 'because' y variantes: everything before = cause, after = effect (or viceversa depending on order)
    # Tratamiento textual más robusto para marcadores comunes
    import re
    # IF ... , ...  or IF ... then ...
    if re.search(r"\bif\b", lower_text):
        m = re.search(r"\bif\s+([^,]+),\s*(.+)$", sent.text, flags=re.I)
        if m:
            cause_str = m.group(1).strip()
            effect_str = m.group(2).strip()
            # absolute positions
            s1 = sent.start_char + sent.text.find(cause_str)
            e1 = s1 + len(cause_str)
            s2 = sent.start_char + sent.text.find(effect_str, sent.text.find(cause_str) + len(cause_str))
            e2 = s2 + len(effect_str)
            add_span_by_chars('cause', s1, e1)
            add_span_by_chars('effect', s2, e2)
            return spans
        m2 = re.search(r"\bif\s+(.+)\bthen\b\s+(.+)$", lower_text)
        if m2:
            # use .lower() positions mapping is trickier; use simple split
            parts = re.split(r"\bthen\b", sent.text, flags=re.I)
            if len(parts) >= 2:
                cause_str = parts[0].replace('If', '').strip()
                effect_str = parts[1].strip()
                s1 = sent.start_char + sent.text.find(cause_str)
                e1 = s1 + len(cause_str)
                s2 = sent.start_char + sent.text.find(effect_str)
                e2 = s2 + len(effect_str)
                add_span_by_chars('cause', s1, e1)
                add_span_by_chars('effect', s2, e2)
                return spans

    # 'because', 'due to', 'caused by' and similar
    for marker in [" because ", " due to ", " caused by ", " caused ", " as a result of "]:
        if marker in lower_text:
            idx = lower_text.find(marker)
            left = sent.text[:idx].strip()
            right = sent.text[idx + len(marker):].strip()
            # Common pattern 'X because Y' -> X=effect, Y=cause
            if left:
                s_left = sent.start_char + sent.text.find(left)
                add_span_by_chars('effect', s_left, s_left + len(left))
            if right:
                s_right = sent.start_char + sent.text.find(right, idx + len(marker))
                add_span_by_chars('cause', s_right, s_right + len(right))
            return spans

    # Heurística 2: verbos causales 'lead', 'cause', 'result in' -> subject/object split
    causal_verbs = ['lead', 'lead to', 'cause', 'result', 'produce', 'trigger']
    for tok in sent_doc:
        if tok.lemma_.lower() in causal_verbs:
            # subject as cause and object/clause after verb as effect
            subj = None
            dobj = None
            for child in tok.children:
                if child.dep_ in ('nsubj', 'nsubjpass'):
                    subj = list(child.subtree)
                if child.dep_ in ('dobj', 'pobj', 'attr', 'oprd'):
                    dobj = list(child.subtree)

            if subj:
                s = min([t.idx for t in subj])
                e = max([t.idx + len(t.text) for t in subj])
                add_span_by_chars('cause', s, e)
            if dobj:
                s = min([t.idx for t in dobj])
                e = max([t.idx + len(t.text) for t in dobj])
                add_span_by_chars('effect', s, e)
            if subj or dobj:
                return spans

    # Heurística 3: 'therefore' / 'thus' / 'so' -> left = cause, right = effect
    concl_markers = ['therefore', 'thus', 'so', 'hence', 'as a result']
    for m in concl_markers:
        if m in lower_text:
            idx = lower_text.find(m)
            left = sent.text[:idx].strip()
            right = sent.text[idx + len(m):].strip()
            if left:
                s_rel = sent.text.find(left)
                if s_rel != -1:
                    s_abs = sent.start_char + s_rel
                    add_span_by_chars('cause', s_abs, s_abs + len(left))
            if right:
                s_rel = sent.text.find(right, idx + len(m))
                if s_rel != -1:
                    s_abs = sent.start_char + s_rel
                    add_span_by_chars('effect', s_abs, s_abs + len(right))
            return spans

    # Si no encontramos nada, devolvemos vacío para fallback
    return []


def normalize_and_merge_spans(text, spans):
    """Normaliza spans y resuelve solapamientos: convierte caracteres absolutos y prioriza cause/effect.

    Entrada: lista de (role, start_char, end_char)
    Salida: lista similar con solapamientos resueltos y sin duplicados.
    """
    if not spans:
        return []

    # Ordenar por inicio
    spans_sorted = sorted(spans, key=lambda x: (x[1], -(x[2]-x[1])))
    merged = []

    for role, s, e in spans_sorted:
        if not merged:
            merged.append([role, s, e])
            continue
        last = merged[-1]
        # Si solapan
        if s <= last[2]:
            # Priorizar cause/effect sobre causal_sentence
            if last[0] == 'causal_sentence' and role in ('cause', 'effect'):
                merged[-1] = [role, s, max(e, last[2])]
            elif role == 'causal_sentence' and last[0] in ('cause', 'effect'):
                # ignorar causal_sentence que esté dentro de cause/effect
                merged[-1][2] = max(merged[-1][2], e)
            else:
                # combinar extendiendo el último span
                merged[-1][2] = max(merged[-1][2], e)
        else:
            merged.append([role, s, e])

    # Convertir a tuplas
    return [(r, s, e) for r, s, e in merged]

# --- 2. Lógica de Generación de HTML ---

def generate_html_report(text, highlights):
    """Genera un archivo HTML con el texto resaltado."""
    highlights.sort(key=lambda x: x[1]) # Ordenar por posición inicial

    html_output = """
    <html>
    <head>
        <title>Causal Analysis Report</title>
        <style>
            body { font-family: sans-serif; line-height: 1.6; padding: 20px; }
            .causal_sentence { background-color: #fff8c4; padding: 3px; border-radius: 4px; }
            .cause { background-color: #ffd6d6; padding: 2px; border-radius: 3px; } /* Rojo claro para causa */
            .effect { background-color: #d6ffd6; padding: 2px; border-radius: 3px; } /* Verde claro para efecto */
            .meta { font-size: 0.9em; color: #666; margin-bottom: 10px; }
            .legend span { display:inline-block; margin-right:10px; padding:4px; border-radius:4px; }
        </style>
    </head>
    <body>
        <h1>Causal Analysis Report</h1>
        <div class='meta'>Generated by Causa-Efecto Highlighter</div>
        <div class='legend'><span class='cause'>Cause</span><span class='effect'>Effect</span><span class='causal_sentence'>Causal sentence</span></div>
        <p>
    """

    last_index = 0
    for type, start, end in highlights:
        # Añadir texto no resaltado
        html_output += text[last_index:start]
        # Añadir el span resaltado
        html_output += f"<span class='{type}'>{text[start:end]}</span>"
        last_index = end

    # Añadir el resto del texto
    html_output += text[last_index:]
    html_output += "</p></body></html>"

    with open("highlighted_report.html", "w", encoding='utf-8') as f:
        f.write(html_output)
    print("Report 'highlighted_report.html' generated successfully.")

# --- 3. Interfaz Gráfica (GUI) ---

def select_file_and_process():
    """Abre un diálogo para seleccionar archivo y comienza el procesamiento."""
    file_path = filedialog.askopenfilename(
        title="Select a PDF file",
        filetypes=[("PDF Files", "*.pdf")]
    )
    if not file_path:
        return # El usuario canceló

    messagebox.showinfo("Processing", "Starting analysis. This may take a few moments for large files...")
    
    # Extraer texto
    text = extract_text_from_pdf(file_path)
    if not text:
        return

    # Analizar y generar reporte
    matcher = setup_causal_matcher(nlp)
    highlights = analyze_text(text, matcher)
    generate_html_report(text, highlights)
    
    messagebox.showinfo("Success", "Analysis complete! Check 'highlighted_report.html'.")

def run_gui():
    # Configuración de la ventana principal
    root = tk.Tk()
    root.title("Causa-Efecto Highlighter")
    root.geometry("300x150")

    label = tk.Label(root, text="Select a PDF to analyze for causality.")
    label.pack(pady=10)

    process_button = tk.Button(root, text="Select PDF File", command=select_file_and_process)
    process_button.pack(pady=20)

    root.mainloop()


if __name__ == '__main__':
    run_gui()