# Office Word Add-in (beta)

The optional Word task-pane add-in lets a user generate Markdown with their own OpenAI, Anthropic, or Gemini API key, then converts and inserts it as native Word content through a public or self-hosted `md2docx` API.

## Authentication modes

- **User API key (implemented):** The key is supplied by the user for the current add-in session only. It is never written to local storage by this add-in. The selected Word text and instruction are sent directly to the provider when the user requests AI.
- **OAuth (broker required):** OAuth needs a provider-specific registered client, redirect URI, and server-side token exchange. Do not place OAuth client secrets or provider keys in this add-in. A self-hosted OAuth broker may be added behind this UI; its deployment and privacy policy are the operator's responsibility.

For OpenAI specifically, the official API guidance says API keys are secrets and should not be exposed in client-side code. Use a broker for organization-managed OpenAI access. [OpenAI API authentication guidance](https://platform.openai.com/docs/api-reference/backward-compatibility?lang=ruby)

## Deployment

1. Host `office-addin/` at the HTTPS paths referenced in `manifest.xml`.
2. Host the public `md2docx` API, or enter a self-hosted API URL in the add-in.
3. Validate `manifest.xml` with Microsoft’s add-in validator before sideloading or Store submission.
