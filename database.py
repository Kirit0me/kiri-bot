import os
import logging
from pymongo import MongoClient, UpdateOne, ASCENDING
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "kiri_bot_db")

logger = logging.getLogger("Database")
_topics_col = None
_activity_col = None

def get_collections():
    global _topics_col, _activity_col
    if _topics_col is None:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client[DB_NAME]
        _topics_col = db["server_topics"]
        _activity_col = db["server_activity"]
        
        _topics_col.create_index([("guild_id", ASCENDING), ("word", ASCENDING)], unique=True)
        _activity_col.create_index([("guild_id", ASCENDING), ("hour", ASCENDING)], unique=True)
    return _topics_col, _activity_col

def upsert_analytics(guild_id: str, word_counts: dict, hour_counts: dict):
    if not word_counts and not hour_counts:
        return

    topics_col, activity_col = get_collections()
    
    # Batch update word counts
    if word_counts:
        topic_ops = [
            UpdateOne(
                {"guild_id": str(guild_id), "word": word},
                {"$inc": {"count": count}},
                upsert=True
            )
            for word, count in word_counts.items()
        ]
        topics_col.bulk_write(topic_ops)

    # Batch update hourly message distribution
    if hour_counts:
        activity_ops = [
            UpdateOne(
                {"guild_id": str(guild_id), "hour": hour},
                {"$inc": {"count": count}},
                upsert=True
            )
            for hour, count in hour_counts.items()
        ]
        activity_col.bulk_write(activity_ops)

def get_peak_activity(guild_id: str):
    _, activity_col = get_collections()
    return list(activity_col.find({"guild_id": str(guild_id)}).sort("count", -1))