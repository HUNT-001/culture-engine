# Frontend

React + Vite + TypeScript. It calls FastAPI through `VITE_API_BASE_URL`.

```bash
npm install
cp .env.example .env.local
npm run dev
npm run build
```

Only public frontend configuration belongs in Vite environment variables. **Never put Qloo or LLM API keys in `VITE_*` variables.** Vite embeds those values in the browser bundle.
