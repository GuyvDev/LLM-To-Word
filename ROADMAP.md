# md2docx Roadmap

> Open-source, no-login, no-charge release plan.

## What it provides

| Component | Status |
|---|---|
| Python Markdown → DOCX library and CLI | ✅ Ready |
| Hebrew/Arabic RTL, mixed BiDi, and native LaTex/OMML math | ✅ Ready |
| Stateless FastAPI conversion API | ✅ Ready |
| Browser web client | ✅ Ready for same-origin or configured API deployment |
| Chrome extension for GitHub and HackMD | 🔄 Needs browser E2E and Store validation |
| Word add-in + optional user AI provider | 🔄 BYOK restored; needs hosted assets, provider review, and Microsoft validation |
| Windows clipboard helper | 🟡 Optional local tool |

## Release checklist

- [x] MIT license, public README, Docker image, CI, tests, dependency audit, and secret-literal gate.
- [x] No md2docx account, payment, quota database, conversion API key, watermark, or telemetry requirement.
- [x] Optional Office BYOK AI integration keeps user provider keys session-only; managed OAuth requires a self-hosted broker.
- [x] Public API resource controls: request size, concurrency cap, and in-memory burst guard.
- [ ] Run Word visual regression checks from `AGENTS.md` on a Windows host.
- [ ] Test the extension in Chrome developer mode and validate the Office manifest.
- [ ] Create a GitHub release, enable branch protection, and publish the repository.

## Future contributions

Potential community work: broader Markdown support, integration tests for browser/Office clients, additional document themes, self-hosting examples, and provider-specific OAuth broker implementations. The core converter must remain usable without an account or payment.
