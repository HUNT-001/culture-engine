# Frontend

React + Vite + TypeScript. It calls FastAPI through `VITE_API_BASE_URL`, the backend URL **including `/api`** (e.g. `https://<backend-host>/api`); the value is baked in at build time, so rebuild after changing it. For deployment (static site, `npm ci && npm run build`, publish `dist`) see the root `README.md`.

```bash
npm ci
cp .env.example .env.local
npm run dev
npm run build
```

Only public frontend configuration belongs in Vite environment variables. **Never put Qloo or LLM API keys in `VITE_*` variables.** Vite embeds those values in the browser bundle.
