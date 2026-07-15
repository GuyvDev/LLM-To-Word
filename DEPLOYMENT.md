# Deployment guide

## Docker API

```bash
docker build -t md2docx .
docker run --rm -p 8000:8000 md2docx
```

The API is stateless and has no database, account, payment, or secret configuration. `POST /convert` returns a DOCX; `POST /convert/base64` returns JSON for Office integrations.

## Production checklist

1. Serve the web UI and API over HTTPS.
2. Set request-size, concurrency, and rate-limit values from `.env.example`; use a reverse proxy for distributed rate limiting.
3. Set `CORS_ORIGINS` to an explicit allowlist for private deployments. Public deployments may use `*`.
4. Do not log Markdown bodies, generated DOCX content, or headers unnecessarily.
5. Run CI, dependency audit, and a staging conversion test before each release.
6. Host the static Office add-in assets and `/extension/md2docx.js` at the HTTPS locations described in its README, then validate with Microsoft before distribution. The add-in's document conversion remains local.
