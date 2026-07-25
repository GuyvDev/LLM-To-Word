# Privacy and data handling

LLM to Word is open-source software. The Chrome extension, clipboard helper,
and Skill One process documents locally and do not send them to an LLM or a
conversion service.

The Chrome extension performs capture and DOCX conversion locally. It reads the active page only after the user clicks **Capture latest response**, using Chrome's temporary `activeTab` permission. Captured content is shown for review and is not sent to md2docx or back to the LLM. The extension does not inject prompts or formatting guidance into AI conversations.

The untested Word add-in can send selected text and an instruction directly to
an AI provider selected by the user. Provider keys are held only in memory for
the current add-in session. The add-in does not implement provider OAuth.

Self-hosters are responsible for publishing privacy information that matches their deployment.

Development and release visual audits must convert generated documents to PDF
and inspect images rasterized from those PDF pages. Contributors and automated
agents must not capture or retain desktop or application-window screenshots.
Generated documents, PDFs, page images, and local audit directories are ignored
by Git and must not be committed.
