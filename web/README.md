# macrodesk web

The research desk front end: Next.js 16, the LangGraph SDK's `useStream`, Recharts.
See the [root README](../README.md) for the whole project.

```bash
npm install
cp .env.example .env.local   # LANGGRAPH_API_URL (local: http://127.0.0.1:2024), FRED_API_KEY for the live dashboard
npm run dev                  # http://localhost:3000 ; ?demo=1 forces the recorded replay, &autoplay=0 keeps the landing state
```

Deploys to Vercel as is. Without a reachable `LANGGRAPH_API_URL` the page runs in demo mode.
