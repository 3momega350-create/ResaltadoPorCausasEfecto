import tkinter as tk
from tkinter import filedialog, messagebox
import spacy
try:
    from pypdf import PdfReader as PDFReader
except Exception:
    # fallback to PyPDF2 if pypdf not installed
    import PyPDF2
    PDFReader = PyPDF2.PdfReader
from spacy.matcher import Matcher
from spacy.pipeline import EntityRuler
import logging
from tqdm import tqdm

# --- 1. Lógica de NLP (Procesamiento y Extracción) ---

# Cargar el modelo de lenguaje de spaCy
print("Loading spaCy model...")
try:
    nlp = spacy.load("en_core_web_lg")
except OSError:
    print("Model 'en_core_web_lg' not found.")
    # Intentar cargar un modelo más pequeño si está disponible
    try:
        nlp = spacy.load("en_core_web_sm")
        print("Loaded fallback model 'en_core_web_sm'. Consider installing 'en_core_web_lg' for better results.")
    except OSError:
        # Como último recurso, crear un modelo en blanco con sentencizer para permitir pruebas y evitar SystemExit
        print("Fallback model 'en_core_web_sm' not found. Using a blank English pipeline (limited functionality).")
        nlp = spacy.blank("en")
        # Añadir sentencizer para que `.sents` y separación de oraciones funcione
        try:
            nlp.add_pipe("sentencizer")
        except Exception:
            pass
print("Model loaded successfully.")

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_causal_matcher(nlp_model):
    """Crea y configura el Matcher de spaCy con patrones de causalidad."""
    matcher = Matcher(nlp_model.vocab)
    # Añadir EntityRuler con patrones simples para mejorar detección
    try:
        ruler = EntityRuler(nlp_model, overwrite_ents=False)
        patterns = [
            {"label": "CAUSAL_MARKER", "pattern": "because"},
            {"label": "CAUSAL_MARKER", "pattern": "due to"},
            {"label": "CAUSAL_MARKER", "pattern": "caused by"},
            {"label": "CAUSAL_MARKER", "pattern": "leads to"},
            {"label": "CAUSAL_MARKER", "pattern": "led to"},
            {"label": "CAUSAL_MARKER", "pattern": "if"},
            {"label": "CAUSAL_MARKER", "pattern": "therefore"},
        ]
        ruler.add_patterns(patterns)
        # Insert ruler early so it's available for matching
        nlp_model.add_pipe(ruler, before="parser")
    except Exception:
        logger.debug("EntityRuler not added (spaCy version incompatibility).")

    # Patrón 1: EFFECT because (of) CAUSE
    # Ejemplo: "The mission failed because of the engine."
    pattern1 = [{"LEMMA": {"IN": ["because", "due to", "as a result of", "owing to"]}}, {"OP": "?"}, {"POS": "DET", "OP": "?"}, {"POS": "NOUN"}]
    
    # Patrón 2: CAUSE leads to EFFECT
    # Ejemplo: "The storm led to power outages."
    pattern2 = [{"DEP": "nsubj"}, {"LEMMA": {"IN": ["lead", "cause", "result", "produce"]}}, {"OP": "*"}, {"LOWER": "to", "OP": "?"}, {"DEP": "dobj"}]

    # Patrón 3: If CAUSE, then EFFECT
    # Ejemplo: "If you heat water, it boils."
    pattern3 = [{"LOWER": "if"}, {"DEP": "nsubj"}, {"DEP": "ROOT"}, {"IS_PUNCT": True, "LOWER": ","}, {"LOWER": "then", "OP": "?"}, {"DEP": "nsubj"}]

    # NOTA: Estos patrones son simplificados. La extracción causal real puede ser muy compleja.
    # Asociamos patrones a etiquetas; los patrones devuelven un span que usaremos
    # como punto de partida para extraer sub-spans de causa y efecto.
    matcher.add("CausalPattern", [pattern1, pattern2, pattern3])
    return matcher

def extract_text_from_pdf(pdf_path):
    """Extrae texto de un archivo PDF."""
    try:
        text = ""
        with open(pdf_path, 'rb') as file:
            reader = PDFReader(file)
            # pypdf and PyPDF2 expose pages slightly differently
            pages = getattr(reader, 'pages', None) or getattr(reader, 'pages', None)
            for page in pages:
                try:
                    page_text = page.extract_text()
                except Exception:
                    # support older PyPDF2 API
                    page_text = page.extractText() if hasattr(page, 'extractText') else None
                if page_text:
                    text += page_text + "\n"
        return text
    except Exception as e:
        messagebox.showerror("Error", f"Could not read PDF file: {e}")
        logger.exception("PDF read error")
        return None


def extract_text_from_scanned_pdf(pdf_path, dpi=200):
    """Extrae texto de PDFs escaneados usando OCR (pytesseract + pdf2image)."""
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except Exception as e:
        logger.error("OCR dependencies not installed: %s", e)
        return None
    try:
        images = convert_from_path(pdf_path, dpi=dpi)
        text = ""
        for img in images:
            text += pytesseract.image_to_string(img) + "\n"
        return text
    except Exception as e:
        logger.exception("OCR extraction failed")
        return None

def analyze_text(text, matcher):
    """Analiza el texto para encontrar coincidencias causales y devuelve los spans."""
    doc = nlp(text)
    matches = matcher(doc)
    
    highlights = []
    # Nueva lógica: para cada coincidencia intentamos extraer sub-spans de causa y efecto
    matched_sentences = set()

    for match_id, start, end in matches:
        span = doc[start:end]
        sent_span = span.sent

        # Evitar duplicados si varios patrones coinciden en la misma oración
        if sent_span.start in matched_sentences:
            continue

        # Intentar extraer causa y efecto dentro de la oración
        cause_effect_spans = extract_cause_effect(sent_span)

        if cause_effect_spans:
            # Añadir spans individuales (cause/effect) para resaltado
            for role, s_char, e_char in cause_effect_spans:
                highlights.append((role, s_char, e_char))
        else:
            # Fallback: resaltar la oración completa como causal_sentence
            highlights.append(('causal_sentence', sent_span.start_char, sent_span.end_char))

        matched_sentences.add(sent_span.start)

    # Extra: revisar oraciones que no coinciden con el matcher pero contienen marcadores causales
    causal_markers = ["because", "due to", "if", "then", "therefore", "led to", "leads to", "caused by", "therefore", "thus", "so"]
    for sent in doc.sents:
        if sent.start in matched_sentences:
            continue
        s_text = sent.text.lower()
        if any(m in s_text for m in causal_markers):
            cause_effect_spans = extract_cause_effect(sent)
            if cause_effect_spans:
                for role, s_char, e_char in cause_effect_spans:
                    highlights.append((role, s_char, e_char))
            else:
                highlights.append(('causal_sentence', sent.start_char, sent.end_char))
            matched_sentences.add(sent.start)

    # Normalizar y unir spans solapados/contiguos: causa > efecto > causal_sentence
    highlights = normalize_and_merge_spans(text, highlights)

    return highlights


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