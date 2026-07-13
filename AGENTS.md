# Contributor Guide

## Runtime

Use Python 3.12 and install dependencies with:

```bash
python -m pip install -r requirements.txt -r api/requirements.txt
```

## Verification

Run these checks before opening a pull request:

```bash
python -m unittest discover -s tests -v
docker build -t md2docx .
```

For visual rendering changes, open the generated DOCX in Microsoft Word and verify Hebrew headings, mixed BiDi text, inline/block math, blockquotes, and tables.

## Safety

Do not commit credentials, private documents, generated DOCX/PDF files, debug images, or machine-specific paths. Keep the project usable without an account, payment, hosted service, or optional user-provided AI credential.
