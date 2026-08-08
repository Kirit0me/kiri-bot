import asyncio
import logging
import discord
from discord import app_commands
from discord.ext import commands
import kafka_producer
import database

logger = logging.getLogger("AnalyticsCog")

class AnalyticsCog(commands.GroupCog, name="analytics"):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    # 1. High-Volume Message Ingestion Command
    @app_commands.command(name="ingest", description="Stream channel history to Kafka pipeline.")
    @app_commands.describe(limit="Number of recent messages to scan (Max 1,000,000)")
    @app_commands.checks.has_permissions(administrator=True)
    async def ingest_history(self, interaction: discord.Interaction, limit: app_commands.Range[int, 10, 1000000] = 50000):
        await interaction.response.defer()

        count = 0
        try:
            async for message in interaction.channel.history(limit=limit, oldest_first=False):
                if message.author.bot or not message.content:
                    continue

                kafka_producer.send_message_to_kafka(
                    guild_id=str(interaction.guild_id),
                    channel_id=str(interaction.channel_id),
                    message_id=str(message.id),
                    author_id=str(message.author.id),
                    author_name=str(message.author.display_name),
                    content=message.content,
                    timestamp=message.created_at.isoformat()
                )
                count += 1

                if count % 1000 == 0:
                    await asyncio.sleep(0.01)

            kafka_producer.flush_kafka()
            await interaction.followup.send(
                f"✅ **Ingestion Complete!** Streamed **{count:,}** messages to Kafka.\n"
                f"⚡ PySpark is processing topics, activity heatmaps & user statistics."
            )
        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            await interaction.followup.send("❌ Failed streaming messages to Kafka.", ephemeral=True)

    # 2. Trending Topics Command
    @app_commands.command(name="topics", description="Display top discussion topics in this server.")
    async def show_topics(self, interaction: discord.Interaction):
        await interaction.response.defer()
        results = database.get_top_topics(str(interaction.guild_id), limit=15)
        
        if not results:
            await interaction.followup.send("❌ No topic data found. Run `/analytics ingest` first!")
            return

        desc = ""
        for idx, item in enumerate(results, 1):
            desc += f"**{idx}.** `{item['word']}` — **{item['count']:,}** mentions\n"

        embed = discord.Embed(
            title=f"🗣️ Top Server Topics — {interaction.guild.name}",
            description=desc,
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed)

    # 3. Peak Activity Heatmap Command
    @app_commands.command(name="activity", description="Display peak activity windows in this server.")
    async def show_activity(self, interaction: discord.Interaction):
        await interaction.response.defer()
        results = database.get_peak_activity(str(interaction.guild_id), limit=7)
        
        if not results:
            await interaction.followup.send("❌ No activity data found. Run `/analytics ingest` first!")
            return

        desc = ""
        for idx, item in enumerate(results, 1):
            desc += f"**{idx}.** `{item['day_hour']}` — **{item['count']:,}** messages\n"

        embed = discord.Embed(
            title=f"📈 Peak Chat Activity Heatmap — {interaction.guild.name}",
            description=desc,
            color=discord.Color.gold()
        )
        await interaction.followup.send(embed=embed)

    # 4. User Leaderboard Command
    @app_commands.command(name="leaderboard", description="Display top most active chatters in this server.")
    async def show_leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        results = database.get_top_users(str(interaction.guild_id), limit=10)
        
        if not results:
            await interaction.followup.send("❌ No user analytics found. Run `/analytics ingest` first!")
            return

        desc = ""
        for idx, user in enumerate(results, 1):
            avg_len = round(user['total_chars'] / max(1, user['message_count']), 1)
            desc += f"**{idx}.** `{user['username']}` — **{user['message_count']:,}** msgs *(avg {avg_len} chars)*\n"

        embed = discord.Embed(
            title=f"🏆 Top Chatter Leaderboard — {interaction.guild.name}",
            description=desc,
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AnalyticsCog(bot))