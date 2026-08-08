# Kiri-bot

A feature-rich, interactive Discord bot built with Python 3.13 and discord.py 2.0+. 

Kiri-bot features multiple engaging trivia mini-games spanning cinema, world geography, and server activities—complete with auto-scoring, fuzzy-answer matching, and async API integrations.

## 🌟 Key Features🎬 

### Movie Quiz (/movie) : 

Scene Guessing: Identifies movie stills using high-res TMDB media assets.

Actor/Director Trivia: Tests film knowledge on cast and crew.

Voice Soundtracks: Plays movie themes live in Voice Channels (PyNaCl + FFmpeg). Not Working 

### 🌍 Geography Quiz (/geo)

Flag Quiz: Displays national flag images using official CDN sources.

Capital & Country Matching: Reciprocal quiz modes (Capital  Country).


## What I did

Dynamic Pagination: Automatically fetches and caches ~250 countries from REST Countries API v5 with fallback protection.

Fuzzy Answer Matching: Uses rapidfuzz string-matching so minor spelling typos don't penalize players.

💬 Interactive Triggers & Help SystemMention @Kiri-bot or type kiri for custom responses.

Dedicated /help slash command and kirihelp prefix support.Owner-only !sync command for instant slash command registration.

for kafka

docker run -d --name zookeeper -p 2181:2181 zookeeper
docker run -d --name kafka -p 9092:9092 \
  -e KAFKA_ZOOKEEPER_CONNECT=localhost:2181 \
  -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://localhost:9092 \
  -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 \
  confluentinc/cp-kafka:latest

source venv/bin/activate
python pipeline.py

source venv/bin/activate
python bot.py