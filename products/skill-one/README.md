# Skill One

Provider-neutral AI skill for creating deterministic, self-validated Word
documents. The installable package is in `skill-one/`; product planning,
packaging, and installation material stays beside it so the uploaded skill
contains only runtime resources.

## Status

Verified. The compiler, deterministic package, official skill structure,
Docker smoke test, OOXML validator, and PDF page-image benchmark pass. The
installed skill has been exercised locally. Provider marketplace publication
is optional and is not required for direct installation.

## Features

- Dependency-free Python 3 DocSpec-to-DOCX compiler.
- Deterministic ZIP/XML packaging and structural self-validation.
- RTL paragraphs and runs, mixed BiDi spacing, RTL tables, centered cells, and
  independent list numbering.
- Native OMML equations, code blocks, links, quotes, headings, and page breaks.
- Modern Word compatibility settings.
- Automatic replacement of em dashes with regular hyphens, plus validator
  enforcement.
- Privacy-safe visual audit instructions based only on PDF page images.

## Product files

- [Implementation plan](PLAN.md)
- [Installation and packaging](INSTALL.md)
- `skill-one/scripts/docx_brain.py` - dependency-free DocSpec-to-DOCX compiler
- `skill-one/references/` - model-facing schema and provider adapters
- `package_skill.py` - deterministic upload ZIP builder

## Completion checklist

- [x] DocSpec contract and provider adapters.
- [x] Compiler and deterministic package output.
- [x] OOXML, relationship, RTL, table, equation, numbering, and corruption
  validation.
- [x] Official skill validator and clean Python Docker verification.
- [x] Hebrew/mixed-BiDi PDF page-image benchmark.
- [ ] Optional publication in provider-specific skill marketplaces.
