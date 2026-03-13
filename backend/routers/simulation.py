"""
backend/routers/simulation.py — Simulation API: trigger run, optional SSE stream,
and replay stored runs from MongoDB.
"""

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Import runner after path is set (run from project root)
from backend.simulation_runner import run_simulation, build_payload_from_db_round
import config.db as db_module

router = APIRouter(prefix="/simulation", tags=["simulation"])

# In-memory store for SSE: run_id -> asyncio.Queue of round payloads
_run_queues: dict[str, asyncio.Queue] = {}


class RunRequestBody(BaseModel):
    memoryOn: bool = True
    rounds: int = 10
    seed: int | None = None
    scenario: str = "simulations/tragedy_of_commons"


@router.post("/run")
async def simulation_run(body: RunRequestBody):
    """
    Run simulation with given memoryOn, rounds, seed, scenario.
    Runs to completion and returns { run_id, summary, rounds }.
    """
    run_id = str(uuid.uuid4())
    result = await run_simulation(
        memory_on=body.memoryOn,
        num_rounds=body.rounds,
        scenario_dir=body.scenario,
        seed=body.seed,
        on_round_complete=None,
    )
    return {
        "run_id": run_id,
        "summary": result["summary"],
        "rounds": result["rounds"],
    }


async def _run_and_stream(run_id: str, body: RunRequestBody):
    """Background: run sim and push each round payload into run_id's queue."""
    q = _run_queues.get(run_id)
    if not q:
        return
    try:
        def on_round(payload: dict):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass
        result = await run_simulation(
            memory_on=body.memoryOn,
            num_rounds=body.rounds,
            scenario_dir=body.scenario,
            seed=body.seed,
            on_round_complete=on_round,
        )
        await q.put({"status": "complete", "summary": result["summary"]})
    except Exception as e:
        await q.put({"status": "error", "error": str(e)})
    # NOTE: Do NOT pop the queue here. The SSE consumer (_event_generator) owns
    # queue cleanup. If we pop here and the client hasn't connected yet, the
    # client gets "run_id not found" even though the run completed successfully.


@router.post("/run/stream")
async def simulation_run_stream(body: RunRequestBody, background_tasks: BackgroundTasks):
    """
    Start simulation in background; returns run_id. Client should GET
    /simulation/stream/{run_id} to receive SSE of round payloads.
    """
    run_id = str(uuid.uuid4())
    _run_queues[run_id] = asyncio.Queue()
    background_tasks.add_task(_run_and_stream, run_id, body)
    return {"run_id": run_id}


async def _event_generator(run_id: str):
    q = _run_queues.get(run_id)
    if not q:
        yield "data: {\"error\": \"run_id not found\"}\n\n"
        return
    try:
        while True:
            payload = await asyncio.wait_for(q.get(), timeout=300.0)
            if isinstance(payload, dict):
                if payload.get("status") == "complete":
                    import json
                    yield f"data: {json.dumps(payload)}\n\n"
                    return
                if payload.get("status") == "error":
                    import json
                    yield f"data: {json.dumps(payload)}\n\n"
                    return
            import json
            yield f"data: {json.dumps(payload)}\n\n"
    except asyncio.TimeoutError:
        yield "data: {\"error\": \"timeout\"}\n\n"
    finally:
        _run_queues.pop(run_id, None)


@router.get("/stream/{run_id}")
async def simulation_stream(run_id: str):
    """SSE endpoint: stream round payloads and final { status: complete, summary }."""
    return StreamingResponse(
        _event_generator(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/runs")
async def list_runs(limit: int = 20):
    """
    List recent simulation runs stored in MongoDB.
    Returns [ { run_id, timestamp, status, rounds_count, final_summary } ].
    Excludes the per-round data to keep the response small.
    """
    runs = db_module.get_all_simulations(limit=limit)
    result = []
    for run in runs:
        ts = run.get("timestamp")
        result.append({
            "run_id": run["_id"],
            "timestamp": ts.isoformat() if ts else None,
            "status": run.get("status", "unknown"),
            "rounds_count": run.get("config", {}).get("num_rounds")
                or len(run.get("rounds", [])),
            "final_summary": run.get("final_summary"),
        })
    return result


@router.get("/replay/{simulation_id}")
async def simulation_replay(simulation_id: str):
    """
    Stream a stored simulation run's rounds as SSE events.
    Produces the same event format as /simulation/stream/{run_id}.
    Client receives one data event per round, then { status: complete, summary }.
    """
    run = db_module.get_simulation(simulation_id)
    if not run:
        async def _not_found():
            yield 'data: {"error": "simulation not found"}\n\n'
        return StreamingResponse(_not_found(), media_type="text/event-stream")

    rounds = run.get("rounds", [])
    max_rounds = len(rounds)
    summary = run.get("final_summary") or {}

    async def _replay_generator():
        for db_round in sorted(rounds, key=lambda r: r.get("round", 0)):
            payload = build_payload_from_db_round(db_round, max_rounds, rounds)
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(0)  # yield control so the response can flush
        yield f"data: {json.dumps({'status': 'complete', 'summary': summary})}\n\n"

    return StreamingResponse(
        _replay_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )