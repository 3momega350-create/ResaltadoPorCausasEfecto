# Causa-Efecto Text Highlighter 🚦

Este proyecto es una herramienta de Procesamiento de Lenguaje Natural (NLP) que analiza un archivo de texto (actualmente en formato PDF y en inglés), identifica las relaciones de causa y efecto, y genera un archivo HTML con las causas resaltadas en rojo y las consecuencias en verde.

## Características

- **Análisis de Causalidad**: Utiliza reglas predefinidas y la librería `spaCy` para encontrar frases que denotan causalidad.
- **Resaltado de Texto**: Genera un archivo HTML `highlighted_report.html` con el texto original y los resaltados aplicados para una lectura fácil y contextual.
- **Interfaz Gráfica Simple**: Permite al usuario seleccionar un archivo PDF fácilmente.
- **Portable**: Diseñado para ser convertido en un ejecutable con PyInstaller.

## ¿Cómo Usarlo?

### Prerrequisitos

- Python 3.7 o superior
- Las librerías listadas en `requirements.txt`.

### Pasos

1.  **Clona o descarga este repositorio.**

2.  **Instala las dependencias**:
    Abre tu terminal o línea de comandos y ejecuta:
    ```bash
    pip install -r requirements_final.txt
    ```
    Luego, descarga el modelo de lenguaje de spaCy (recomendado):
    ```bash
    python -m spacy download en_core_web_lg
    ```

### OCR y PDFs escaneados

Si tu PDF es una imagen (escaneado) y no contiene texto seleccionable, puedes usar OCR. Instala Tesseract en tu sistema (https://github.com/tesseract-ocr/tesseract) y luego instala las dependencias de Python con `requirements_final.txt`. El programa tiene una función `extract_text_from_scanned_pdf` que intentará extraer texto vía OCR.

### Notas sobre PDF libs

Se recomienda `pypdf` en vez de `PyPDF2` ya que PyPDF2 está deprecado. El código usa `pypdf` si está disponible y hace fallback a `PyPDF2` cuando no lo está.

3.  **Ejecuta el programa**:
    ```bash
    python main.py
    ```

4.  **Usa la aplicación**:
    - Se abrirá una pequeña ventana.
    - Haz clic en "Select PDF File".
    - Elige el archivo PDF en inglés que quieras analizar.
    - El programa procesará el archivo (puede tardar un poco dependiendo del tamaño del libro) y creará un archivo llamado `highlighted_report.html` en la misma carpeta.
    - Abre `highlighted_report.html` en tu navegador web para ver el resultado.

## Notas sobre mejoras

- El extractor ahora intenta identificar sub-spans de `cause` y `effect` dentro de la misma oración usando heurísticas basadas en marcadores léxicos ("because", "due to", "if...then", "therefore", etc.) y dependencias gramaticales cuando es posible.
- Si la heurística falla, la oración completa se marca como `causal_sentence` como fallback.

## Troubleshooting

- Si no ves resaltados claros, verifica que el PDF tenga texto (no sea una imagen escaneada). Para PDFs escaneados necesitas OCR previo.
- Si spaCy lanza un error sobre `en_core_web_lg`, instala el modelo con:
    ```bash
    python -m spacy download en_core_web_lg
    ```

Si quieres que actualice `requirements.txt` en el repositorio para listar paquetes exactos, dímelo y lo actualizo ahora.