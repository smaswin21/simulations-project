"""
db.py — MongoDB connection for agent profiles.

Database: thesis-architecture
Collections: profiles, logs, agent_memories
"""

import json
import os
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection

load_dotenv()

_client: MongoClient | None = None
_db = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        uri = os.getenv("MONGODB_URI")
        if not uri:
            raise ValueError("MONGODB_URI not found in .env")
        _client = MongoClient(uri)
    return _client


def get_db():
    global _db
    if _db is None:
        _db = get_client()["thesis-architecture"]
    return _db


def get_profiles_collection() -> Collection:
    return get_db()["profiles"]


def load_profiles() -> list[dict[str, Any]]:
    """
    Load all agent profiles from MongoDB.
    Returns list of profile documents sorted by pid.
    """
    collection = get_profiles_collection()
    profiles = list(collection.find({}, {"_id": 0}).sort("pid", 1))
    return profiles


def load_profiles_from_json(json_path: str) -> list[dict[str, Any]]:
    """Load profile-like records from a local JSON file."""
    with open(json_path, encoding="utf-8") as handle:
        profiles = json.load(handle)
    if not isinstance(profiles, list):
        raise ValueError(f"Expected a list of profiles in {json_path}.")
    return profiles


def get_profile(pid: str) -> dict[str, Any] | None:
    """Get a single profile by pid."""
    collection = get_profiles_collection()
    return collection.find_one({"pid": pid}, {"_id": 0})


def seed_from_json(json_path: str) -> int:
    """
    Import profiles from JSON file to MongoDB.
    Adds created_at timestamp. Returns number of profiles imported.
    """
    import json

    with open(json_path) as f:
        profiles = json.load(f)

    collection = get_profiles_collection()

    for profile in profiles:
        profile["created_at"] = datetime.now(timezone.utc)
        profile["updated_at"] = datetime.now(timezone.utc)

    collection.delete_many({})
    result = collection.insert_many(profiles)

    return len(result.inserted_ids)


def save_profile(profile: dict[str, Any]) -> None:
    """Insert or update a single profile."""
    collection = get_profiles_collection()
    profile["updated_at"] = datetime.now(timezone.utc)

    collection.update_one(
        {"pid": profile["pid"]},
        {"$set": profile},
        upsert=True
    )


def close() -> None:
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None


# === Simulation Logging ===

def get_logs_collection() -> Collection:
    return get_db()["logs"]


def create_simulation(config: dict[str, Any], agent_profiles: list[dict[str, Any]]) -> str:
    """
    Create a new simulation document. Returns the simulation _id as string.
    """
    collection = get_logs_collection()
    doc = {
        "timestamp": datetime.now(timezone.utc),
        "status": "running",
        "config": config,
        "agent_profiles": agent_profiles,
        "rounds": [],
        "final_summary": None
    }
    result = collection.insert_one(doc)
    return str(result.inserted_id)


def append_round(simulation_id: str, round_data: dict[str, Any]) -> None:
    """
    Append a round to the simulation's rounds array.
    """
    from bson.objectid import ObjectId
    collection = get_logs_collection()
    collection.update_one(
        {"_id": ObjectId(simulation_id)},
        {"$push": {"rounds": round_data}}
    )


def complete_simulation(simulation_id: str, final_summary: dict[str, Any]) -> None:
    """
    Mark simulation as completed and save final summary.
    """
    from bson.objectid import ObjectId
    collection = get_logs_collection()
    collection.update_one(
        {"_id": ObjectId(simulation_id)},
        {
            "$set": {
                "status": "completed",
                "final_summary": final_summary
            }
        }
    )


def get_simulation(simulation_id: str) -> dict[str, Any] | None:
    """Get a simulation by its _id."""
    from bson.objectid import ObjectId
    collection = get_logs_collection()
    return collection.find_one({"_id": ObjectId(simulation_id)})


def get_simulation_rounds(simulation_id: str) -> list[dict[str, Any]]:
    """Load stored round documents for a simulation."""
    from bson.objectid import ObjectId

    if not ObjectId.is_valid(simulation_id):
        raise ValueError(f"Simulation id '{simulation_id}' is not a valid ObjectId.")

    collection = get_logs_collection()
    doc = collection.find_one(
        {"_id": ObjectId(simulation_id)},
        {"_id": 0, "rounds": 1},
    )
    if doc is None:
        raise ValueError(f"Simulation '{simulation_id}' was not found.")

    rounds = doc.get("rounds") or []
    if not rounds:
        raise ValueError(f"Simulation '{simulation_id}' has no rounds to replay.")

    return rounds


def get_all_simulations(limit: int = 10) -> list[dict[str, Any]]:
    """Get recent simulations, most recent first."""
    collection = get_logs_collection()
    docs = list(collection.find({}, {"rounds": 0}).sort("timestamp", -1).limit(limit))
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    return docs


# === Agent Memory Graphs ===

def get_memories_collection() -> Collection:
    """Get the agent_memories collection. Creates index on first access."""
    collection = get_db()["agent_memories"]
    # Ensure compound unique index for efficient upserts
    collection.create_index(
        [("simulation_id", 1), ("agent_name", 1)],
        unique=True,
        background=True,
    )
    return collection


def save_memory_graph(
    simulation_id: str,
    agent_name: str,
    graph_data: dict[str, Any],
    episode_count: int,
) -> None:
    """
    Upsert an agent's memory graph for a simulation.

    Called after each round to persist the latest state. Uses upsert so
    the first call creates the document and subsequent calls update it.

    Args:
        simulation_id: the simulation's _id string
        agent_name: the agent's name
        graph_data: serialized graph from EpisodicMemoryGraph.to_dict()
        episode_count: current number of episodes stored
    """
    collection = get_memories_collection()
    collection.update_one(
        {
            "simulation_id": simulation_id,
            "agent_name": agent_name,
        },
        {
            "$set": {
                "simulation_id": simulation_id,
                "agent_name": agent_name,
                "graph_data": graph_data,
                "episode_count": episode_count,
                "updated_at": datetime.now(timezone.utc),
            },
            "$setOnInsert": {
                "created_at": datetime.now(timezone.utc),
            },
        },
        upsert=True,
    )


def load_memory_graph(simulation_id: str, agent_name: str) -> dict[str, Any] | None:
    """
    Load a single agent's memory graph for a simulation.

    Returns the graph_data dict (suitable for EpisodicMemoryGraph.from_dict()),
    or None if not found.
    """
    collection = get_memories_collection()
    doc = collection.find_one(
        {
            "simulation_id": simulation_id,
            "agent_name": agent_name,
        },
        {"_id": 0, "graph_data": 1},
    )
    if doc and "graph_data" in doc:
        return doc["graph_data"]
    return None


def load_all_memory_graphs(simulation_id: str) -> list[dict[str, Any]]:
    """
    Load all agents' memory graphs for a simulation.

    Returns list of documents with agent_name, episode_count, and graph_data.
    """
    collection = get_memories_collection()
    docs = list(
        collection.find(
            {"simulation_id": simulation_id},
            {"_id": 0, "agent_name": 1, "episode_count": 1, "graph_data": 1},
        ).sort("agent_name", 1)
    )
    return docs
