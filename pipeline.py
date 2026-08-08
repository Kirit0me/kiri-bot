import os
import re
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StructField, StringType
import database

STOPWORDS = {
    "about", "above", "after", "again", "against", "all", "and", "because", "been", "before",
    "being", "below", "between", "both", "but", "by", "can", "could", "did", "does", "doing",
    "down", "during", "each", "few", "for", "from", "further", "had", "has", "have", "having",
    "here", "how", "if", "into", "just", "more", "most", "other", "our", "out", "over", "same",
    "should", "some", "such", "than", "that", "the", "their", "them", "then", "there", "these",
    "they", "this", "those", "through", "under", "until", "up", "very", "was", "were", "what",
    "when", "where", "which", "while", "who", "whom", "why", "will", "with", "would", "you", "your"
}

spark = SparkSession.builder \
    .appName("DiscordAnalyticsPipeline") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

schema = StructType([
    StructField("message_id", StringType()),
    StructField("guild_id", StringType()),
    StructField("channel_id", StringType()),
    StructField("content", StringType()),
    StructField("timestamp", StringType())
])

def process_batch(df, batch_id):
    records = df.collect()
    if not records:
        return

    guild_words = {}
    guild_hours = {}

    for row in records:
        guild_id = row["guild_id"]
        content = row["content"]
        ts_str = row["timestamp"]

        if guild_id not in guild_words:
            guild_words[guild_id] = {}
            guild_hours[guild_id] = {}

        # 1. Topic Extraction
        if content:
            clean_text = re.sub(r"[^a-zA-Z\s]", "", content).lower()
            words = [w for w in clean_text.split() if len(w) > 3 and w not in STOPWORDS]
            for w in words:
                guild_words[guild_id][w] = guild_words[guild_id].get(w, 0) + 1

        # 2. Hour Activity Parsing
        if ts_str:
            dt = datetime.fromisoformat(ts_str)
            hour_key = f"{dt.hour:02d}:00 UTC"
            guild_hours[guild_id][hour_key] = guild_hours[guild_id].get(hour_key, 0) + 1

    for g_id in guild_words:
        database.upsert_analytics(g_id, guild_words[g_id], guild_hours[g_id])

def run_pipeline():
    kafka_stream = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "localhost:9092") \
        .option("subscribe", "discord_messages") \
        .option("startingOffsets", "earliest") \
        .load()

    parsed_df = kafka_stream.select(
        from_json(col("value").cast("string"), schema).alias("data")
    ).select("data.*")

    query = parsed_df.writeStream \
        .foreachBatch(process_batch) \
        .start()

    query.awaitTermination()

if __name__ == "__main__":
    run_pipeline()