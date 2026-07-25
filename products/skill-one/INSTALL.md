# Install Skill One

Download the ready-to-upload package:

[`skill-one.zip`](https://github.com/GuyvDev/LLM-To-Word/releases/latest/download/skill-one.zip)

The ZIP contains the instructions, formatting guide, validators, and native
Windows/Linux compiler. No conversion API, Docker runtime, or AI credential is
required.

## ChatGPT web

1. Open **Plugins -> Skills -> Create -> Upload from computer**.
2. Upload `skill-one.zip` and install it.
3. Ask: `Use Skill One to create a polished Word document from this content.`

Skills availability depends on the ChatGPT plan and workspace settings. See
OpenAI's [Skills in ChatGPT](https://help.openai.com/en/articles/20001066).

## Claude web

1. Enable **Code execution and file creation**.
2. Open **Customize -> Skills -> + -> Create skill -> Upload a skill**.
3. Upload `skill-one.zip`, enable it, and ask:
   `Use Skill One to create a polished Word document from this content.`

See Anthropic's
[Use skills in Claude](https://support.claude.com/en/articles/12512180-use-skills-in-claude).

## Codex

Paste this prompt into Codex:

```text
Install Skill One from the latest GitHub Release of
https://github.com/GuyvDev/LLM-To-Word. Download skill-one.zip and
SHA256SUMS.txt, verify the checksum, install it as a Codex skill, run its
doctor check, and tell me when I should start a new session.
```

Then start a new session and ask:

```text
Use $skill-one to turn this Markdown into a polished Word document.
```

## Maintainer packaging

```powershell
.\scripts\build_converter_core.ps1
.\scripts\build_linux_core.ps1
python products\skill-one\package_skill.py
```

The deterministic package is written to `dist/skill-one.zip` unless another
output path is supplied.
