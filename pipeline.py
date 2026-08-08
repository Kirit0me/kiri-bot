import os
import re
import pyspark
from datetime import datetime

SPARK_VERSION = pyspark.__version__
KAFKA_PACKAGE = f"org.apache.spark:spark-sql-kafka-0-10_2.13:{SPARK_VERSION}"

os.environ['PYSPARK_SUBMIT_ARGS'] = f'--packages {KAFKA_PACKAGE} pyspark-shell'
if os.path.exists("/usr/lib/jvm/java-21-openjdk"):
    os.environ["JAVA_HOME"] = "/usr/lib/jvm/java-21-openjdk"

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
    "when", "where", "which", "while", "who", "whom", "why", "will", "with", "would", "you", "your",
    "http", "https", "com", "www", "like", "know", "yeah", "think", "dont", "cant", "that's", "this"
}

spark = SparkSession.builder \
    .appName("DiscordHighPerfPipeline") \
    .config("spark.jars.packages", KAFKA_PACKAGE) \
    .config("spark.sql.shuffle.partitions", "8") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

schema = StructType([
    StructField("message_id", StringType()),
    StructField("guild_id", StringType()),
    StructField("channel_id", StringType()),
    StructField("author_id", StringType()),
    StructField("author_name", StringType()),
    StructField("content", StringType()),
    StructField("timestamp", StringType())
])

def process_batch(df, batch_id):
    records = df.collect()
    if not records:
        return

    guild_words = {}
    guild_activity = {}
    guild_users = {}

    for row in records:
        guild_id = row["guild_id"]
        content = row["content"]
        ts_str = row["timestamp"]
        author_id = row["author_id"]
        author_name = row["author_name"]

        if not guild_id:
            continue

        if guild_id not in guild_words:
            guild_words[guild_id] = {}
            guild_activity[guild_id] = {}
            guild_users[guild_id] = {}

        # 1. Clean Content & Extract Keywords
        if content:
            clean_text = re.sub(r"<a?:[a-zA-Z0-9_]+:[0-9]+>", "", content) # Remove Discord Emojis
            clean_text = re.sub(r"https?://\S+", "", clean_text)          # Remove URLs
            clean_text = re.sub(r"[^a-zA-Z\s]", "", clean_text).lower()   # Strip Punctuation
            
            words = [w for w in clean_text.split() if len(w) > 3 and w not in STOPWORDS]
            for w in words:
                guild_words[guild_id][w] = guild_words[guild_id].get(w, 0) + 1

        # 2. Activity Heatmap Parsing (Day of Week + Hour UTC)
        if ts_str:
            dt = datetime.fromisoformat(ts_str)
            day_name = dt.strftime("%A")
            hour_str = f"{dt.hour:02d}:00 UTC"
            key = f"{day_name} {hour_str}"
            guild_activity[guild_id][key] = guild_activity[guild_id].get(key, 0) + 1

        # 3. User Analytics Tracking
        if author_id:
            if author_id not in guild_users[guild_id]:
                guild_users[guild_id][author_id] = {"username": author_name, "messages": 0, "chars": 0}
            guild_users[guild_id][author_id]["messages"] += 1
            guild_users[guild_id][author_id]["chars"] += len(content or "")

    # Execute DB Upserts per Guild
    for g_id in guild_words:
        database.bulk_upsert_pipeline_data(
            g_id, 
            guild_words[g_id], 
            guild_activity[g_id], 
            guild_users[g_id]
        )

def run_pipeline():
    print("⚡ High-Performance PySpark Stream Processor Online!")
    kafka_stream = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "localhost:9092") \
        .option("subscribe", "discord_messages") \
        .option("startingOffsets", "earliest") \
        .option("failOnDataLoss", "false") \
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