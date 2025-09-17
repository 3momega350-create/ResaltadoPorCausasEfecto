"""Utilities para extracción de texto desde PDF o archivos de texto."""
import logging

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_path: str) -> str:
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
