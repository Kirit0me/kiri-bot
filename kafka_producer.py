import json
import logging
from kafka import KafkaProducer

logger = logging.getLogger("KafkaProducer")

producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    acks=1,
    retries=3
)

def send_message_to_kafka(guild_id, channel_id, message_id, author_id, author_name, content, timestamp):
    payload = {
        "guild_id": str(guild_id),
        "channel_id": str(channel_id),
        "message_id": str(message_id),
        "author_id": str(author_id),
        "author_name": str(author_name),
        "content": content,
        "timestamp": timestamp
    }
    producer.send('discord_messages', value=payload)

def flush_kafka():
    producer.flush()