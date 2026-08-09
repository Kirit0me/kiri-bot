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

import nltk
from nltk.corpus import stopwords

# Download standard NLTK stopwords set on pipeline startup
nltk.download('stopwords', quiet=True)

# Build set of common stopwords
STOPWORDS = set(stopwords.words('english'))

# Add custom Discord/Chat specific filler words
CHAT_FILLER = {
  "http",
  "https",
  "com", "www",
  "yeah",
  "think",
  "dont",
  "cant",
  "like",
  "know",
  "thats",
  "im",
  "lol",
  "lmao",
}
STOPWORDS.update(CHAT_FILLER)

spark = SparkSession.builder \
    .appName("DiscordChannelAnalyticsPipeline") \
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
    
    # Channel-wise structures
    channel_words = {}
    channel_stats = {}

    for row in records:
        guild_id = row["guild_id"]
        channel_id = row["channel_id"]
        content = row["content"]
        ts_str = row["timestamp"]
        author_id = row["author_id"]
        author_name = row["author_name"]

        if not guild_id or not channel_id:
            continue

        if guild_id not in guild_words:
            guild_words[guild_id] = {}
            guild_activity[guild_id] = {}
            guild_users[guild_id] = {}
            channel_words[guild_id] = {}
            channel_stats[guild_id] = {}

        if channel_id not in channel_words[guild_id]:
            channel_words[guild_id][channel_id] = {}
            channel_stats[guild_id][channel_id] = {"messages": 0, "chars": 0}

        # Track Channel Message Volume
        channel_stats[guild_id][channel_id]["messages"] += 1
        channel_stats[guild_id][channel_id]["chars"] += len(content or "")

        # 1. Clean Content & Extract Keywords (Server + Channel Level)
        if content:
            clean_text = re.sub(r"<a?:[a-zA-Z0-9_]+:[0-9]+>", "", content)
            clean_text = re.sub(r"https?://\S+", "", clean_text)
            clean_text = re.sub(r"[^a-zA-Z\s]", "", clean_text).lower()
            
            words = [w for w in clean_text.split() if len(w) >= 3 and w not in STOPWORDS]
            for w in words:
                guild_words[guild_id][w] = guild_words[guild_id].get(w, 0) + 1
                channel_words[guild_id][channel_id][w] = channel_words[guild_id][channel_id].get(w, 0) + 1

        # 2. Activity Heatmap Parsing
        if ts_str:
            try:
                dt = datetime.fromisoformat(ts_str)
                day_name = dt.strftime("%A")
                hour_str = f"{dt.hour:02d}:00 UTC"
                key = f"{day_name} {hour_str}"
                guild_activity[guild_id][key] = guild_activity[guild_id].get(key, 0) + 1
            except Exception:
                pass

        # 3. User Analytics
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
            guild_users[g_id],
            channel_words[g_id],
            channel_stats[g_id]
        )

def run_pipeline():
    print("⚡ High-Performance PySpark Stream Processor (Server + Channel Analytics) Online!")
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