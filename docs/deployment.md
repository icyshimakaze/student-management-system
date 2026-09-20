# Deployment

This project has three deployable pieces. Nothing below is claimed to be
already deployed — these are the tested, reproducible paths.

## Frontend (sms-web) — static hosting

```bash
cd sms-web
VITE_API_URL=https://your-api.example.com npm run build
```

Deploy the `dist/` folder to Vercel, Netlify, GitHub Pages, or any static
host. `VITE_API_URL` is read **at build time**; check the built bundle
contains your API URL, not the dev fallback.

## API (api.py) — Python host

Any host that runs uvicorn works (Render, Railway, a VPS):

```
build:  pip install -r requirements.txt -r requirements-api.txt
start:  uvicorn api:app --host 0.0.0.0 --port $PORT
```

Environment variables to set in the host dashboard (never commit them):

- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` — the production MySQL
- `API_JWT_SECRET` — long random string (`python -c "import secrets; print(secrets.token_urlsafe(48))"`)
- `CORS_ORIGINS` — your frontend origin, e.g. `https://your-frontend.vercel.app`

## Database — managed MySQL

Use a managed MySQL 8 (Aiven, PlanetScale-style, or a cloud provider's
managed service). Apply `database/schema.sql` (minus the `CREATE DATABASE`/
`USE` lines if the provider pre-creates the database) and `seed_data.sql`
optionally. Create the first admin from a machine that can reach the
database: `python scripts/create_user.py` with `DB_*` pointed at production.

## Desktop EXE

Not deployed — distributed. See `BUILD_WINDOWS.md`; CI produces the
executable artifact on every push to `main`.

## Checklist for a real deployment

- [ ] HTTPS on both frontend and API (browsers block mixed content)
- [ ] `CORS_ORIGINS` includes the exact frontend origin
- [ ] Strong `API_JWT_SECRET`, rotated if ever leaked
- [ ] Dedicated least-privilege MySQL user (not root)
- [ ] `GET /health` wired to the host's health check
