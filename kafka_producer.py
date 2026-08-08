import json
import logging
import os
from kafka import KafkaProducer
from dotenv import load_dotenv

load_dotenv()

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
logger = logging.getLogger("KafkaProducer")

_producer = None

def get_producer():
    """Lazily initializes the Kafka Producer on demand."""
    global _producer
    if _producer is None:
        try:
            _producer = KafkaProducer(
                bootstrap_servers=[KAFKA_BOOTSTRAP],
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                request_timeout_ms=5000,
                max_block_ms=5000
            )
            logger.info("✅ Kafka Producer initialized successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Kafka broker at {KAFKA_BOOTSTRAP}: {e}")
            raise e
    return _producer


def send_message_to_kafka(guild_id: str, channel_id: str, message_id: str, content: str, timestamp: str):
    """Sends a message payload to Kafka topic."""
    producer = get_producer()
    payload = {
        "message_id": str(message_id),
        "guild_id": str(guild_id),
        "channel_id": str(channel_id),
        "content": content,
        "timestamp": timestamp
    }
    producer.send("discord_messages", value=payload)


def flush_kafka():
    if _producer is not None:
        _producer.flush()