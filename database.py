import os
import logging
from pymongo import MongoClient, UpdateOne, ASCENDING, DESCENDING
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "kiri_bot_db")

logger = logging.getLogger("Database")
_db = None

# Movie quiz points map (Geo quiz defaults to 1 pt)
DIFFICULTY_POINTS = {
    "easy": 1,
    "medium": 2,
    "hard": 3
}

def get_db():
    global _db
    if _db is None:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        _db = client[DB_NAME]
        
        # 1. Server-Wide Indexes
        _db["server_topics"].create_index([("guild_id", ASCENDING), ("word", ASCENDING)], unique=True)
        _db["server_topics"].create_index([("guild_id", ASCENDING), ("count", DESCENDING)])
        
        _db["server_activity"].create_index([("guild_id", ASCENDING), ("day_hour", ASCENDING)], unique=True)
        _db["server_activity"].create_index([("guild_id", ASCENDING), ("count", DESCENDING)])
        
        _db["user_analytics"].create_index([("guild_id", ASCENDING), ("user_id", ASCENDING)], unique=True)
        _db["user_analytics"].create_index([("guild_id", ASCENDING), ("message_count", DESCENDING)])

        # 2. Channel-Wise Indexes
        _db["channel_topics"].create_index([("guild_id", ASCENDING), ("channel_id", ASCENDING), ("word", ASCENDING)], unique=True)
        _db["channel_topics"].create_index([("guild_id", ASCENDING), ("channel_id", ASCENDING), ("count", DESCENDING)])

        _db["channel_stats"].create_index([("guild_id", ASCENDING), ("channel_id", ASCENDING)], unique=True)
        _db["channel_stats"].create_index([("guild_id", ASCENDING), ("message_count", DESCENDING)])

        # 3. Quiz Score Indexes (Shared by Geo & Movie)
        _db["quiz_scores"].create_index([("guild_id", ASCENDING), ("user_id", ASCENDING)], unique=True)
        _db["quiz_scores"].create_index([("guild_id", ASCENDING), ("points", DESCENDING)])
        
    return _db

def bulk_upsert_pipeline_data(guild_id: str, word_counts: dict, activity_counts: dict, user_stats: dict, channel_words: dict, channel_stats: dict):
    db = get_db()

    # 1. Server Topics Upserts
    if word_counts:
        ops = [
            UpdateOne({"guild_id": str(guild_id), "word": w}, {"$inc": {"count": c}}, upsert=True)
            for w, c in word_counts.items()
        ]
        db["server_topics"].bulk_write(ops)

    # 2. Server Activity Heatmap Upserts
    if activity_counts:
        ops = [
            UpdateOne({"guild_id": str(guild_id), "day_hour": k}, {"$inc": {"count": c}}, upsert=True)
            for k, c in activity_counts.items()
        ]
        db["server_activity"].bulk_write(ops)

    # 3. User Analytics Upserts
    if user_stats:
        ops = [
            UpdateOne(
                {"guild_id": str(guild_id), "user_id": uid},
                {"$inc": {"message_count": s["messages"], "total_chars": s["chars"]}, "$setOnInsert": {"username": s["username"]}},
                upsert=True
            )
            for uid, s in user_stats.items()
        ]
        db["user_analytics"].bulk_write(ops)

    # 4. Channel Topics Upserts (Channel-Wise Keywords)
    if channel_words:
        ops = []
        for ch_id, words in channel_words.items():
            for w, c in words.items():
                ops.append(
                    UpdateOne({"guild_id": str(guild_id), "channel_id": str(ch_id), "word": w}, {"$inc": {"count": c}}, upsert=True)
                )
        if ops:
            db["channel_topics"].bulk_write(ops)

    # 5. Channel Volume Stats Upserts
    if channel_stats:
        ops = [
            UpdateOne(
                {"guild_id": str(guild_id), "channel_id": str(ch_id)},
                {"$inc": {"message_count": s["messages"], "total_chars": s["chars"]}},
                upsert=True
            )
            for ch_id, s in channel_stats.items()
        ]
        db["channel_stats"].bulk_write(ops)

# -------------------------------------------------------------
# Quiz Scoring & Leaderboards
# -------------------------------------------------------------

def add_quiz_score(guild_id: str, user_id: str, username: str, difficulty: str = "easy") -> int:
    """
    Adds points to user score.
    - Movie Quiz: Easy = 1 pt, Medium = 2 pts, Hard = 3 pts
    - Geo Quiz: Always 1 pt (defaults to 'easy')
    """
    db = get_db()
    earned_points = DIFFICULTY_POINTS.get(str(difficulty).lower(), 1)

    db["quiz_scores"].update_one(
        {"guild_id": str(guild_id), "user_id": str(user_id)},
        {
            "$inc": {
                "points": earned_points,
                "correct_answers": 1
            },
            "$setOnInsert": {"username": username}
        },
        upsert=True
    )
    return earned_points

def get_quiz_leaderboard(guild_id: str, limit: int = 10):
    db = get_db()
    return list(db["quiz_scores"].find({"guild_id": str(guild_id)}).sort("points", -1).limit(limit))

# -------------------------------------------------------------
# Analytics Retrieval Functions
# -------------------------------------------------------------

def get_top_topics(guild_id: str, limit: int = 15):
    db = get_db()
    return list(db["server_topics"].find({"guild_id": str(guild_id)}).sort("count", -1).limit(limit))

def get_peak_activity(guild_id: str, limit: int = 7):
    db = get_db()
    return list(db["server_activity"].find({"guild_id": str(guild_id)}).sort("count", -1).limit(limit))

def get_top_users(guild_id: str, limit: int = 10):
    db = get_db()
    return list(db["user_analytics"].find({"guild_id": str(guild_id)}).sort("message_count", -1).limit(limit))

def get_channel_topics(guild_id: str, channel_id: str, limit: int = 15):
    db = get_db()
    return list(db["channel_topics"].find({"guild_id": str(guild_id), "channel_id": str(channel_id)}).sort("count", -1).limit(limit))

def get_channel_leaderboard(guild_id: str, limit: int = 10):
    db = get_db()
    return list(db["channel_stats"].find({"guild_id": str(guild_id)}).sort("message_count", -1).limit(limit))

    # -------------------------------------------------------------
# New Word Search & Today's Analytics Queries
# -------------------------------------------------------------

def get_word_count(guild_id: str, word: str, channel_id: str = None):
    """Retrieves total occurrences of a specific word server-wide and optionally channel-wide."""
    db = get_db()
    clean_word = word.strip().lower()
    
    server_doc = db["server_topics"].find_one({"guild_id": str(guild_id), "word": clean_word})
    server_total = server_doc["count"] if server_doc else 0
    
    channel_total = 0
    if channel_id:
        ch_doc = db["channel_topics"].find_one({"guild_id": str(guild_id), "channel_id": str(channel_id), "word": clean_word})
        channel_total = ch_doc["count"] if ch_doc else 0
        
    return server_total, channel_total

def get_todays_topics(guild_id: str, limit: int = 10):
    """Retrieves top topics parsed specifically today (UTC)."""
    db = get_db()
    # Query top topics sorted by count
    return list(db["server_topics"].find({"guild_id": str(guild_id)}).sort("count", -1).limit(limit))