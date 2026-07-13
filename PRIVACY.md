# Privacy and data handling

md2docx is open-source software. The included API processes Markdown in memory to return a DOCX response and does not intentionally persist submitted documents or generated files.

The built-in one-minute abuse guard retains IP-derived identifiers only in process memory. Self-hosters should document any reverse-proxy, analytics, logging, or hosting-provider retention they configure.

The optional Word add-in can send selected text and an instruction directly to an AI provider selected by the user. Provider API keys are held only in memory for the current add-in session. The add-in does not implement provider OAuth; use a server-side OAuth broker for managed OAuth access.

Self-hosters are responsible for publishing privacy information that matches their deployment.
