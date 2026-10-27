# Design history

Early planning material, kept for context. **It is not the current specification**: where it disagrees
with the code or the main README, the code and README win.

| File | What it is |
|---|---|
| `COMMON_THREAD_PRODUCT_AND_RESEARCH_BRIEF.md` / `.docx` | The original product, architecture and research brief (v0.2). Vision, open questions and evaluation plan written before implementation. |
| `initial-system-architecture.png` | First system sketch. It predates the build: it shows Next.js (the app uses React + Vite), a place-verification adapter and a server-side cache, none of which exist. |
| `agent-internal-architecture.png` | First agent-flow sketch, with retry and tool-registry ideas that were not built. The implemented workflow is a fixed 8-node graph; see the README and `docs/AGENT_WORKFLOW.md`. |
| `INITIAL_IMPLEMENTATION_PLAN.md` | The first milestone checklist. Most items have since been built; it is not a status tracker. |

Current architecture diagrams live in the root [`README.md`](../../README.md).
