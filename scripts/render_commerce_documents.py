"""Publish one PDF per source document, with deterministic bytes and an index.

Markdown is the source of record. Rebuilding never rewrites product prose.
Every current short guide must fit one page; overflow fails publication instead
of silently invalidating the section citations stored in the manifest.
"""
from hashlib import sha256
import json
from pathlib import Path
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / 'fixtures/commerce'
OUTPUT = ROOT / 'output/pdf/commerce'


class SinglePageDocument(SimpleDocTemplate):
    def afterPage(self):
        if self.page > 1:
            raise ValueError('Guide overflow: revise layout or implement section-level page mapping before publishing.')


def render(document, text, target):
    navy = colors.HexColor('#173447')
    teal = colors.HexColor('#267A78')
    grey = colors.HexColor('#52616B')
    title_style = ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=22,
                                 leading=26, textColor=navy, spaceAfter=12)
    meta_style = ParagraphStyle('meta', fontName='Helvetica', fontSize=8,
                                leading=11, textColor=grey, spaceAfter=3)
    heading_style = ParagraphStyle('heading', fontName='Helvetica-Bold', fontSize=11.5,
                                   leading=15, textColor=teal, spaceBefore=12, spaceAfter=5)
    body_style = ParagraphStyle('body', fontName='Helvetica', fontSize=10,
                                leading=14.5, textColor=navy, spaceAfter=4)
    story = [Paragraph(escape(document['title']), title_style),
             Paragraph(escape(f"{document['document_id']} | Version {document['version']} | Applies in: {', '.join(document['markets'])}"), meta_style),
             Paragraph(escape(f"Effective {document['effective_from'][:10]} | English | Fictional training publication"), meta_style)]
    if document['canonical_product_id']:
        story.append(Paragraph(escape(f"Product: {document['canonical_product_id']}"), meta_style))
    else:
        story.append(Paragraph('Shared market policy; no individual order decision.', meta_style))
    story.append(Spacer(1, 3*mm))
    parts = re.split(r'^## (.+)$', text, flags=re.MULTILINE)
    for index in range(1, len(parts), 2):
        story.append(Paragraph(escape(parts[index]), heading_style))
        for paragraph in parts[index+1].strip().split('\n\n'):
            story.append(Paragraph(escape(paragraph.strip()), body_style))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(teal)
        canvas.line(22*mm, 20*mm, 188*mm, 20*mm)
        canvas.setFillColor(grey)
        canvas.setFont('Helvetica', 7.5)
        canvas.drawString(22*mm, 14*mm, 'LIVE HOST LAB / FICTIONAL PRODUCT INFORMATION')
        canvas.drawRightString(188*mm, 14*mm, f"{document['document_id']} / {doc.page}")
        canvas.restoreState()

    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix('.pdf.tmp')
    try:
        pdf = SinglePageDocument(str(temp), pagesize=A4, leftMargin=22*mm, rightMargin=22*mm,
                                 topMargin=23*mm, bottomMargin=27*mm, title=document['title'],
                                 author='Live Host Lab', invariant=1)
        pdf.build(story, onFirstPage=footer, onLaterPages=footer)
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)


def main():
    manifest_path = CORPUS / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    products = [d for d in manifest['documents'] if d['canonical_product_id'] is not None]
    ids = [d['canonical_product_id'] for d in products]
    if len(ids) != len(set(ids)):
        raise ValueError('Multiple guides for a product in this publication')
    for document in manifest['documents']:
        source = (CORPUS / document['file']).resolve()
        target = (OUTPUT / document['pdf_file']).resolve()
        if not source.is_relative_to(CORPUS.resolve()) or not target.is_relative_to(OUTPUT.resolve()):
            raise ValueError('Publication path outside root')
        raw = source.read_bytes()
        if sha256(raw).hexdigest() != document['sha256']:
            raise ValueError('Markdown differs from the publication manifest')
        if document['pdf_page'] != 1:
            raise ValueError('Standalone single-page guide requires page 1')
        render(document, raw.decode(), target)
        document['pdf_sha256'] = sha256(target.read_bytes()).hexdigest()
    temp = manifest_path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(manifest, indent=2) + '\n')
    temp.replace(manifest_path)
    lines = ['# 商品资料与市场政策', '',
             '50个商品各有一份独立PDF；德法政策单独维护。全部为虚构资料，Markdown是主来源。', '',
             '| 商品/政策 | 商品ID | PDF | Markdown |', '|---|---|---|---|']
    for document in manifest['documents']:
        pdf = OUTPUT / document['pdf_file']
        md = CORPUS / document['file']
        lines.append(f"| {document['title']} | {document['canonical_product_id'] or '-'} | [PDF]({document['pdf_file']}) | [Markdown](<{md}>) |")
    (OUTPUT / 'INDEX.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({'products': len(products), 'policies': len(manifest['documents'])-len(products),
                      'output': str(OUTPUT)}))


if __name__ == '__main__':
    main()
