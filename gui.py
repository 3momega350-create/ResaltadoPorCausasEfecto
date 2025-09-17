"""Pequeña GUI opcional basada en tkinter."""
import logging
from analyzer import analyze_text
from spacy_utils import load_spacy_model
from pdf_utils import extract_text_from_pdf, extract_text_from_scanned_pdf
from html_utils import generate_html_report

logger = logging.getLogger(__name__)


def run_gui():
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except Exception:
        logger.exception("tkinter no disponible; GUI deshabilitada.")
        return

    nlp = load_spacy_model()

    root = tk.Tk()
    root.title("Causa-Efecto Highlighter")

    def pick_and_run():
        p = filedialog.askopenfilename()
        if p:
            try:
                ext = p.split('.')[-1].lower()
                if ext == 'pdf':
                    text = extract_text_from_pdf(p)
                    if not text.strip():
                        text = extract_text_from_scanned_pdf(p)
                else:
                    with open(p, 'r', encoding='utf-8') as fh:
                        text = fh.read()
                highlights = analyze_text(text, nlp)
                generate_html_report(text, highlights)
                messagebox.showinfo("Listo", "Reporte generado: highlighted_report.html")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    btn = tk.Button(root, text="Seleccionar archivo y analizar", command=pick_and_run)
    btn.pack(padx=20, pady=20)
    root.mainloop()
