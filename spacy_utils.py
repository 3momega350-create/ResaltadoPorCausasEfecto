"""Funciones para cargar y configurar el modelo spaCy."""
import logging
import spacy
from spacy.pipeline import EntityRuler

logger = logging.getLogger(__name__)


def load_spacy_model(preferred_model: str = "en_core_web_lg"):
    logger.info("Cargando modelo spaCy (preferido=%s)", preferred_model)
    try:
        return spacy.load(preferred_model)
    except Exception:
        logger.warning("No se encontró %s. Intentando en_core_web_sm...", preferred_model)
    try:
        return spacy.load("en_core_web_sm")
    except Exception:
        logger.warning("No hay modelos instalados. Creando pipeline en blanco con sentencizer.")
        nlp = spacy.blank("en")
        try:
            nlp.add_pipe("sentencizer")
        except Exception:
            pass
        return nlp


def add_entity_ruler(nlp):
    try:
        ruler = EntityRuler(nlp)
        ruler.add_patterns([
            {"label": "CAUSAL_PHRASE", "pattern": "as a result of"},
            {"label": "CAUSAL_PHRASE", "pattern": "due to"},
            {"label": "CAUSAL_PHRASE", "pattern": "because"},
        ])
        try:
            nlp.add_pipe(ruler, before="ner")
        except Exception:
            try:
                nlp.add_pipe(ruler)
            except Exception:
                pass
    except Exception:
        logger.debug("EntityRuler no añadido (incompatibilidad).")
