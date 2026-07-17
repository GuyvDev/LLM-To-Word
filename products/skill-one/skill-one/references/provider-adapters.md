# Provider adapters

## Claude

Upload the `skill-one` folder as a custom skill ZIP or install it under the
provider's skills directory. Enable code execution and file creation. The
`SKILL.md` workflow invokes the bundled Python script directly.

## ChatGPT custom GPT

Copy the body of `SKILL.md` into GPT Instructions. Upload the entire `skill-one`
folder, including `scripts/docx_brain.py` and both reference files, as Knowledge
and enable Code Interpreter & Data Analysis. Instruct the GPT to create DocSpec
JSON in its working directory and execute the bundled script. Do not configure
an Action: Skill One does not require an API.

For both providers, return the `.docx` only after the build command reports
`valid: true`. Given identical UTF-8 DocSpec bytes, the script produces
identical DOCX bytes regardless of the provider that invoked it.
