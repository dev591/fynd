# Engineering playbook: knowledge over blind prompting

Principle: **the LLM is the last resort, not the first.** Every request should pass through cheaper deterministic layers first.
Anything we claim in the pitch (cost, latency, scale) must be a number we measured, shown live in the trace rail.

## 1. Request pipeline (cheapest layer first)
```
request -> normalize -> exact cache (hash map)        ~0 cost
        -> rules / regex / trie / lookup tables        ~0 cost
        -> semantic cache (embedding + ANN)            embedding cost only
        -> small classifier / small model              cheap
        -> big model, with retrieved context only      expensive
        -> validate (schema) -> cache result -> respond
```
Each hop emits a trace event (`layer`, `hit/miss`, `ms`, `tokens`, `$`). The dashboard right rail renders these live. That is both the UI and the proof of cost reduction.

## 2. DSA that actually cuts cost
| Problem | Structure / algorithm | Effect |
|---|---|---|
| Repeated identical calls | Hash map on normalized key (lowercase, strip, sort params, hash of prompt+model+version); LRU/LFU with TTL | Skips LLM entirely |
| Paraphrased repeats | Embedding + ANN (HNSW / FAISS / pgvector), similarity threshold tuned on a labeled set | Semantic cache; tune threshold to avoid wrong hits |
| Duplicate catalog items / docs | MinHash + LSH or SimHash; Bloom filter for "seen before" | Dedup before paying to enrich |
| Extract known attributes (brand, size, colour) | Trie / Aho-Corasick multi-pattern match, regex | No LLM for the easy 70% |
| Long inputs | Chunk + BM25 + vector hybrid retrieval, top-k, rerank | Send 2k relevant tokens, not 50k |
| Many small calls | Micro-batching queue (flush on size N or T ms); batch API for offline work | Fewer round trips, lower unit cost |
| Spike protection | Token bucket / leaky bucket rate limit; priority queue (heap) so interactive beats bulk | Predictable spend and latency |
| Pipeline of dependent steps | DAG + topological sort; run independent nodes in parallel (`asyncio.gather`) | Latency = longest path, not sum |
| Which model to use | Cascade router: cheap model first, escalate when confidence < threshold (logprobs, self-check, schema failure) | Big model only on hard cases |
| Same long prefix every call | Prompt/prefix caching (stable system prompt + docs first, variable part last) | Cheaper input tokens, lower latency |
| Commerce allocation (order -> warehouse) | Min-cost flow / Hungarian / Dijkstra on a graph; knapsack for capacity | Deterministic optimizer, LLM only explains |
| Ranking / top-K | Heap (O(n log k)) instead of sorting everything | Cheap at scale |

Rule: if an algorithm can solve it exactly, use the algorithm and let the LLM handle only language, ambiguity and explanation.

## 3. Cost model (do this on paper, then measure)
`cost/request = P(miss exact) * [embed + P(miss semantic) * (P(small fails) * big_cost + small_cost)]`
- Track per request: input tokens, output tokens, cache layer that answered, model, latency, $.
- Set a **token budget** per request and per user; truncate retrieval, cap `max_tokens`, use structured output to avoid rambling.
- Pitch metric: "X% of requests answered before the big model, Y$ per 1k requests, p95 Z ms", from our own load test.

## 4. System design for scale
- **API** (FastAPI, async) -> **queue** (Redis streams / BullMQ / Celery) -> **stateless workers** -> **Postgres (+pgvector)** and **Redis** (cache, rate limits, pub/sub).
- **Live trace** to the UI via SSE (simpler than websockets, one-way is enough).
- **Reliability:** idempotency keys, retries with exponential backoff + jitter, timeouts on every call, circuit breaker + fallback model/provider, dead-letter queue, backpressure (reject/queue when full).
- **State:** keep the agent state serializable and checkpointed so a crashed worker resumes, not restarts.
- **Observability:** one trace id per request through every hop; log tokens and $; OpenTelemetry-compatible so any backend works.
- **Evals:** small labeled set + a script that scores accuracy, cache-hit precision and cost on every change. This is what separates engineering from prompting; show the table in the deck.
- **Security/ops basics:** secrets in env, input validation (Pydantic), PII never in cache keys or logs, per-tenant cache namespaces (Fynd is multi-tenant).
- **Honesty at demo scale:** we will not run 350K orders/hour. Show a small load test, the bottleneck we found, and what we'd shard (queue partitions by tenant, read replicas, ANN index sharding).

## 5. Libraries: use each for one job
| Need | Choice | Why / note |
|---|---|---|
| Multi-step agent with state, branching, loops, human approval, checkpoints | **LangGraph** | Explicit graph = our DAG; built-in persistence and streaming of steps (feeds the trace rail) |
| Simple single LLM call | **Provider SDK directly** (Anthropic) | Fewer layers, easier to cost-track and debug |
| Loaders, splitters, integrations | **LangChain**, only the pieces needed | Avoid its heavy chains/abstractions; keep prompts and flow visible in our code |
| Structured output / validation | **Pydantic** (+ tool/JSON-schema output) | Schema failures drive escalation in the cascade |
| Vector search | **pgvector** (one DB) or Qdrant/FAISS | Fewer moving parts wins in 26h |
| Cache / queue / rate limit | **Redis** | One dependency, three jobs |
| Tracing | **Langfuse** or OpenTelemetry | Per-call tokens, cost, latency |
| Curated domain knowledge | **OKF** (Markdown+YAML+links) behind a swappable interface | Hybrid with RAG, not a replacement; measure vs baseline |
| Fynd tie-in | Fynd Commerce APIs / extensions, docs.fynd.com | Show we plug into their platform, no rip-and-replace |

## 5b. OKF (Open Knowledge Format, Google Cloud, announced 2026-06-12)
What it is (per secondary sources; read the spec repo before relying on details): an open, vendor-neutral spec that packages curated knowledge as **Markdown files with YAML metadata and explicit links between concepts**. The agent follows author-defined links instead of retrieving similar chunks. It is a format, not a database, index or runtime. Repo carries a "not an official Google product" disclaimer; ecosystem is weeks old.

Honest take for the pitch:
- It does **not** replace RAG. One controlled study (SSRN, 623-page filing) found OKF beat a weak vector baseline but added nothing over a strong RAG pipeline. Blogs claiming it "replaces vector DBs" are overselling.
- Best use is a **hybrid**: curated, high-value, stable knowledge (Fynd domain rules, return/exchange policy, catalog taxonomy, SOPs) as OKF files the agent navigates via links; long-tail/unstructured data via hybrid retrieval (section 2).
- Cost angle: following a few explicit links loads a small, exact slice of context (fewer tokens, deterministic, auditable) versus top-k chunks that may be noisy. Treat as a hypothesis and **measure it** against our RAG baseline in the eval harness; show both numbers.
- Fit in the pipeline: it sits as a layer between rules and retrieval: `rules -> OKF graph lookup -> hybrid RAG -> LLM`. A concept graph is also a plain graph, so BFS/link-following with a depth cap bounds token spend.
- Risks: young spec, little tooling, curation effort. Do not make the whole solution depend on it; keep it swappable behind a `KnowledgeProvider` interface.
- Not to be confused with the unrelated Open Knowledge Foundation nonprofit.

Sources: Google Cloud OKF announcement coverage (GitBook, Analytics Vidhya, geotoolbox.ai, alphamatch.ai), SSRN "Does Google's Open Knowledge Format Improve RAG?" (Kumar Abhinav).

## 6. Decide after the PS drops
1. Which steps are deterministic (algorithm/lookup) vs genuinely language tasks?
2. What is the expected request volume and what dominates cost (input tokens, output tokens, call count)?
3. Which layer of section 1 do we implement first for the biggest saving? Build that, measure, then add the next.
4. What are the 3 numbers we will show on the Proof chapter, measured live from the backend?

## 7. Learn tonight (highest return)
Semantic caching + threshold tuning · hybrid retrieval (BM25 + vectors + rerank) · LangGraph state/checkpoint/streaming · model cascade routing · prompt caching · backoff/idempotency/circuit breaker · min-cost flow basics for order routing.
