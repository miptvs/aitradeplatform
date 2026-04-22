export default function ApiDocsLinkPage() {
  return (
    <div className="space-y-6">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">API Docs</div>
        <h1 className="mt-1 text-2xl font-semibold text-slate-100">Backend documentation and operator endpoints</h1>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer" className="rounded-2xl border border-border bg-panel/90 p-5 shadow-panel hover:bg-white/5">
          <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">OpenAPI Docs</div>
          <div className="mt-2 text-slate-100">http://localhost:8000/docs</div>
          <div className="mt-2 text-sm text-slate-400">Interactive REST docs for all `/api/v1` route groups.</div>
        </a>
        <a href="http://localhost:8000/redoc" target="_blank" rel="noreferrer" className="rounded-2xl border border-border bg-panel/90 p-5 shadow-panel hover:bg-white/5">
          <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">ReDoc</div>
          <div className="mt-2 text-slate-100">http://localhost:8000/redoc</div>
          <div className="mt-2 text-sm text-slate-400">Alternative API reference view for routes and schemas.</div>
        </a>
      </div>
      <div className="rounded-2xl border border-border bg-panel/90 p-5 shadow-panel">
        <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Useful endpoints</div>
        <div className="mt-3 space-y-2 text-sm text-slate-300">
          <div>`GET /api/v1/portfolio/summary` for dashboard totals</div>
          <div>`GET /api/v1/stream/events` for SSE updates</div>
          <div>`POST /api/v1/simulation/orders` for manual simulated orders</div>
          <div>`POST /api/v1/providers/{'{provider_type}'}/test` for provider health checks</div>
        </div>
      </div>
    </div>
  );
}
