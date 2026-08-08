#!/bin/bash
set -e

echo "🚀 Starting Fedora Environment Setup for Kiri-Bot Pipeline..."

# 1. Update system and install required system packages
echo "📦 Installing System Packages (Python 3.12, Java 17, Docker, MongoDB, FFmpeg)..."
sudo dnf update -y
sudo dnf install -y python3 python3-pip python3-devel java-17-openjdk-devel docker docker-compose ffmpeg git

# 2. Setup Docker and enable systemd service
echo "🐳 Configuring Docker..."
sudo systemctl enable --now docker
sudo usermod -aG docker $USER

# 3. Add MongoDB Official Repository & Install MongoDB
echo "🍃 Installing MongoDB Community Server..."
cat <<'EOF' | sudo tee /etc/yum.repos.d/mongodb-org-7.0.repo
[mongodb-org-7.0]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/redhat/9/mongodb-org/7.0/x86_64/
gpgcheck=1
enabled=1
gpgkey=https://www.mongodb.org/static/pgp/server-7.0.asc
EOF

sudo dnf install -y mongodb-org
sudo systemctl enable --now mongod

# 4. Create Virtual Environment and Install Python Packages
echo "🐍 Setting up Python Virtual Environment..."
python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install "discord.py[voice]" PyNaCl rapidfuzz aiohttp python-dotenv yt-dlp pymongo kafka-python pyspark

# 5. Export Java & PySpark Environment Variables in ~/.bashrc
echo "⚙️ Configuring Environment Variables..."
JAVA_PATH=$(readlink -f /usr/bin/java | sed "s:/bin/java::")

if ! grep -q "JAVA_HOME" ~/.bashrc; then
    echo "export JAVA_HOME=$JAVA_PATH" >> ~/.bashrc
    echo 'export PYSPARK_SUBMIT_ARGS="--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 pyspark-shell"' >> ~/.bashrc
fi

echo "=========================================================="
echo "✅ Setup Complete!"
echo "⚠️  Run 'newgrp docker' or log out/in to refresh Docker permissions."
echo "=========================================================="