"""Bundle only published guides, Markdown and publication metadata for transfer."""
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / 'fixtures/commerce'
PDFS = ROOT / 'output/pdf/commerce'


def main():
    manifest = json.loads((CORPUS / 'manifest.json').read_text())
    destination = ROOT / 'output/pdf/commerce-documents.zip'
    temporary = destination.with_suffix('.zip.tmp')
    index = ['# Product guides and market policies', '',
             'Fictional training publications. One guide per product; policies are shared by market.', '',
             '| Document | PDF | Markdown |', '|---|---|---|']
    try:
        with ZipFile(temporary, 'w', compression=ZIP_DEFLATED) as archive:
            archive.write(CORPUS / 'manifest.json', 'manifest.json')
            archive.write(CORPUS / 'catalog-snapshot.json', 'catalog-snapshot.json')
            for document in manifest['documents']:
                for root, field, digest in ((PDFS, 'pdf_file', 'pdf_sha256'), (CORPUS, 'file', 'sha256')):
                    path = (root / document[field]).resolve()
                    if not path.is_relative_to(root.resolve()) or sha256(path.read_bytes()).hexdigest() != document[digest]:
                        raise ValueError('Publication changed before packaging')
                    archive.write(path, document[field])
                index.append(f"| {document['title']} | [PDF]({document['pdf_file']}) | [Markdown]({document['file']}) |")
            archive.writestr('INDEX.md', '\n'.join(index) + '\n')
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    print(destination)


if __name__ == '__main__':
    main()
