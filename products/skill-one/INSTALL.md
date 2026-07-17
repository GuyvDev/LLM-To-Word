# Install Skill One

Skill One is local and self-contained. It needs Python 3 but no API, Docker,
account, hosted service, or third-party Python package.

## Build the upload package

From the repository root:

```bash
python products/skill-one/package_skill.py
```

This creates `products/skill-one/dist/skill-one.zip`. Generated ZIP files are
ignored by Git.

## Codex

Copy the `products/skill-one/skill-one` directory into the Codex skills
directory, then start a new session and invoke `$skill-one`.

## Claude

Upload the generated ZIP as a skill when that feature is available in the
selected Claude product. The session must have Python execution and file output
enabled. Follow `references/provider-adapters.md` in the package.

## ChatGPT

Create a custom GPT with Code Interpreter enabled. Add `SKILL.md` as its
instructions and upload the compiler, DocSpec reference, and example as
knowledge files. ChatGPT must execute the compiler; prompting alone cannot
guarantee valid OOXML. Follow `references/provider-adapters.md` in the package.

## Direct local use

```bash
python products/skill-one/skill-one/scripts/docx_brain.py build input.json output.docx --report report.json
python products/skill-one/skill-one/scripts/docx_brain.py validate output.docx --json
```
