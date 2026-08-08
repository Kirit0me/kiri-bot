import os
import logging
from pymongo import MongoClient, UpdateOne, ASCENDING, DESCENDING
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "kiri_bot_db")

logger = logging.getLogger("Database")
_db = None

def get_db():
    global _db
    if _db is None:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        _db = client[DB_NAME]
        
        # Indexes for fast aggregations
        _db["server_topics"].create_index([("guild_id", ASCENDING), ("word", ASCENDING)], unique=True)
        _db["server_topics"].create_index([("guild_id", ASCENDING), ("count", DESCENDING)])
        
        _db["server_activity"].create_index([("guild_id", ASCENDING), ("day_hour", ASCENDING)], unique=True)
        _db["server_activity"].create_index([("guild_id", ASCENDING), ("count", DESCENDING)])
        
        _db["user_analytics"].create_index([("guild_id", ASCENDING), ("user_id", ASCENDING)], unique=True)
        _db["user_analytics"].create_index([("guild_id", ASCENDING), ("message_count", DESCENDING)])
        
    return _db

def bulk_upsert_pipeline_data(guild_id: str, word_counts: dict, activity_counts: dict, user_stats: dict):
    db = get_db()

    # 1. Topic Keyword Upserts
    if word_counts:
        ops = [
            UpdateOne(
                {"guild_id": str(guild_id), "word": word},
                {"$inc": {"count": count}},
                upsert=True
            )
            for word, count in word_counts.items()
        ]
        db["server_topics"].bulk_write(ops)

    # 2. Activity Heatmap Upserts (e.g. "Monday 14:00")
    if activity_counts:
        ops = [
            UpdateOne(
                {"guild_id": str(guild_id), "day_hour": key},
                {"$inc": {"count": count}},
                upsert=True
            )
            for key, count in activity_counts.items()
        ]
        db["server_activity"].bulk_write(ops)

    # 3. User Engagement Leaderboard
    if user_stats:
        ops = [
            UpdateOne(
                {"guild_id": str(guild_id), "user_id": uid},
                {
                    "$inc": {
                        "message_count": stats["messages"],
                        "total_chars": stats["chars"]
                    },
                    "$setOnInsert": {"username": stats["username"]}
                },
                upsert=True
            )
            for uid, stats in user_stats.items()
        ]
        db["user_analytics"].bulk_write(ops)

# Retrieval Functions
def get_top_topics(guild_id: str, limit: int = 15):
    db = get_db()
    return list(db["server_topics"].find({"guild_id": str(guild_id)}).sort("count", -1).limit(limit))

def get_peak_activity(guild_id: str, limit: int = 7):
    db = get_db()
    return list(db["server_activity"].find({"guild_id": str(guild_id)}).sort("count", -1).limit(limit))

def get_top_users(guild_id: str, limit: int = 10):
    db = get_db()
    return list(db["user_analytics"].find({"guild_id": str(guild_id)}).sort("message_count", -1).limit(limit))