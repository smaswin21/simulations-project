---

## **Simplified Architecture Diagram**
```
┌─────────────────────────────────────────────────────────────┐
│  PERCEPTION (from environment)                              │
│  - Current location, agent positions                        │
│  - Visible actions, speech                                  │
│  - Health status (public), depot stock (location-based)     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1 — PERSONA (Big Five + CRT + Risk)                 │
│  Personality traits modulate decision weights               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 2 — EPISODIC MEMORY                                  │
│  - Store: What happened? Who did what?                      │
│  - Retrieve: Relevant past experiences                      │
│  - Detect: Contradictions, broken promises                  │
│  - Track: Simple behavioral patterns (hoarders vs. sharers) │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  LLM DECISION (Perception + Persona + Memory → Action)      │
│  Agent generates: Action + Expected Outcome                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  ACTION EXECUTION (Environment processes action)            │
│  Returns: Observed Outcome                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 4 — ACTION-PERCEPTION LOOP                           │
│  - Compare: Expected vs. Observed outcome                   │
│  - If mismatch: High-importance memory write                │
│  - Update: Behavioral priors (personality-calibrated)       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼ (feeds back to Layer 2)


React UI                    FastAPI Server              Python Sim Engine
   │                            │                            │
   ├── POST /simulation ───────>│                            │
   │                            ├── spawn sim task ─────────>│
   │                            │                            │
   │<── SSE: round 1 data ─────│<── round 1 complete ───────│
   │<── SSE: round 2 data ─────│<── round 2 complete ───────│
   │<── SSE: round 3 data ─────│<── round 3 complete ───────│
   │         ...                │         ...                │
   │<── SSE: status=complete ──│<── sim finished ───────────│
