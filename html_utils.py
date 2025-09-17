"""Generación de HTML para los highlights detectados."""
import logging

logger = logging.getLogger(__name__)


def generate_html_report(text: str, highlights, out_path: str = "highlighted_report.html"):
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
        pieces.append("<span class='{}'>{}</span>".format(h['role'], seg))
        last = h['end']
    if last < len(text):
        pieces.append(text[last:])

    html = """
    <html>
    <head><meta charset='utf-8'><style>{}</style></head>
    <body>
    <h1>Causal Analysis Report</h1>
    <div class='legend'><span class='cause'>Cause</span> <span class='effect'>Effect</span> <span class='causal_sentence'>Causal sentence</span></div>
    <div class='content'>
    {}
    </div>
    </body>
    </html>
    """.format(css, ''.join(pieces))

    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write(html)
    logger.info("HTML report escrito en %s", out_path)
