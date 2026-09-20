# SMS Web — React Frontend

Web client for the Student Management System, consuming the FastAPI backend
(`api.py` in the main repository). Same service-layer rules as the desktop app:
validation, authorization, and duplicate-prevention all happen server-side.

## Stack

- React 19 + Vite (plain JavaScript, no UI framework)
- React Router for navigation
- Hand-written CSS (`src/index.css`) — small design system, no dependencies

## Pages

| Route | Access | Contents |
|---|---|---|
| `/login` | public | JWT sign-in |
| `/` | any signed-in | Dashboard: totals, course overview (admin), recent enrollments, grade distribution |
| `/courses` | any signed-in | List + search; admins manage courses; everyone opens rosters/analytics and grades (server-scoped for teachers) |
| `/students` | admin | CRUD, search, profile, enrollment manager with grade entry |
| `/teachers` | admin | CRUD + search |
| `/users` | admin | Create users, activate/deactivate |

Teachers see only their own courses everywhere — enforced by the API, the UI
simply hides admin controls.

## Run locally

1. Start the backend (main repo): `uvicorn api:app --reload`
2. Start the dev server here:

```bash
npm install
npm run dev
```

3. Open http://localhost:5173

The API base URL defaults to `http://127.0.0.1:8000`. Override it with an
environment variable for builds:

```
VITE_API_URL=https://your-api-host
```

## Deploy (static hosting)

```bash
npm run build      # outputs dist/
```

Host `dist/` on any static server (Vercel, Netlify, GitHub Pages, nginx).
Set `VITE_API_URL` at build time to point at your deployed API, and add the
site's origin to `CORS_ORIGINS` in `api.py`. For SPA routing, configure the
host to serve `index.html` for unknown paths (Vercel/Netlify do this
automatically; on nginx use `try_files $uri /index.html;`).
