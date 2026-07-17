# Skill One implementation plan

## Product promise

Create the same validated Microsoft Word document from GPT, Claude, or any
agent that can run Python 3. The product must remain local and self-contained:
no hosted conversion API, Docker runtime, account, or provider credential.

## Architecture

1. The model writes a strict provider-neutral DocSpec JSON document.
2. The installed skill invokes one dependency-free Python compiler.
3. The compiler owns all Word-specific behavior: OOXML packaging, RTL runs,
   mixed-BiDi boundary spacing, OMML equations, tables, styles, and numbering.
4. The compiler validates the generated package before returning it.
5. GPT and Claude distribute different instruction adapters but execute the
   same script and schema; output is deterministic for identical DocSpec input.

## Delivery stages

- [x] Establish an organized `products/` and `shared/` repository layout.
- [x] Initialize a standards-compliant installable skill package.
- [x] Define the DocSpec contract and deterministic workflow.
- [x] Implement every supported block and inline structure.
- [x] Implement structural OOXML self-validation and JSON reports.
- [x] Add cross-provider adapters and representative fixtures.
- [x] Add byte-determinism, RTL, math, table, and corruption tests.
- [x] Package the skill as an uploadable ZIP after all gates pass.

## Acceptance gates

- Dependency-free Python 3 runtime.
- Deterministic DOCX bytes for identical input.
- Valid ZIP and XML package with all required relationships.
- Hebrew and Arabic runs receive native Word RTL properties.
- Mixed RTL/LTR boundaries use Word-stable spacing.
- Supported LaTeX becomes native OMML with no raw command leakage.
- RTL tables retain logical source order and use Word visual RTL behavior.
- Every table cell is horizontally and vertically centered.
- Build fails rather than returning a document that fails validation.
