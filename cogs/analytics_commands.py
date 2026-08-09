import asyncio
import logging
from datetime import datetime, timezone
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

    # 1. Bulk Ingestion Command
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
                f"✅ **Ingestion Complete!** Streamed **{count:,}** messages from #{interaction.channel.name} to Kafka.\n"
                f"⚡ PySpark is processing server and channel analytics."
            )
        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            await interaction.followup.send("❌ Failed streaming messages to Kafka.", ephemeral=True)

    # 2. Server Top Topics
    @app_commands.command(name="topics", description="Display top overall discussion topics in the server.")
    async def show_topics(self, interaction: discord.Interaction):
        await interaction.response.defer()
        results = database.get_top_topics(str(interaction.guild_id), limit=15)
        
        if not results:
            await interaction.followup.send("❌ No topic data found. Send messages or run `/analytics ingest` first!")
            return

        desc = "".join([f"**{i}.** `{item['word']}` — **{item['count']:,}** mentions\n" for i, item in enumerate(results, 1)])
        embed = discord.Embed(title=f"🗣️ Top Server Topics — {interaction.guild.name}", description=desc, color=discord.Color.blue())
        await interaction.followup.send(embed=embed)

    # 3. NEW: Specific Word Frequency Search Command
    @app_commands.command(name="word_count", description="Check how many times a specific word has been mentioned.")
    @app_commands.describe(word="The word or term to look up in the server database")
    async def check_word_count(self, interaction: discord.Interaction, word: str):
        await interaction.response.defer()
        clean_word = word.strip().lower()

        server_count, channel_count = database.get_word_count(
            guild_id=str(interaction.guild_id),
            word=clean_word,
            channel_id=str(interaction.channel_id)
        )

        embed = discord.Embed(
            title=f"🔍 Word Frequency Analysis — `{clean_word}`",
            color=discord.Color.teal()
        )
        embed.add_field(name="🌐 Server-wide Total", value=f"**{server_count:,}** times", inline=False)
        embed.add_field(name=f"💬 #{interaction.channel.name} Total", value=f"**{channel_count:,}** times", inline=False)
        embed.set_footer(text="Counts updated in real-time by PySpark streaming pipeline.")

        await interaction.followup.send(embed=embed)

    # 4. NEW: Today's Most Discussed Topics Command
    @app_commands.command(name="today", description="Displays the most discussed topics in the server today.")
    async def show_today_topics(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        today_date = datetime.now(timezone.utc).strftime("%B %d, %Y")
        results = database.get_todays_topics(str(interaction.guild_id), limit=10)

        if not results:
            await interaction.followup.send("❌ No activity recorded today yet! Send some messages to build stats.")
            return

        desc = ""
        for idx, item in enumerate(results, 1):
            desc += f"**{idx}.** `{item['word']}` — **{item['count']:,}** mentions today\n"

        embed = discord.Embed(
            title=f"📅 Today's Top Discussed Topics — {today_date}",
            description=desc,
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Server: {interaction.guild.name} (UTC Timeframe)")
        await interaction.followup.send(embed=embed)

    # 5. Channel-Specific Topics Command
    @app_commands.command(name="channel_topics", description="Display top discussion topics for a specific channel.")
    @app_commands.describe(channel="Target channel to inspect (Defaults to current channel)")
    async def show_channel_topics(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        await interaction.response.defer()
        target_channel = channel or interaction.channel
        results = database.get_channel_topics(str(interaction.guild_id), str(target_channel.id), limit=15)

        if not results:
            await interaction.followup.send(f"❌ No topic data found for {target_channel.mention}.")
            return

        desc = "".join([f"**{i}.** `{item['word']}` — **{item['count']:,}** mentions\n" for i, item in enumerate(results, 1)])
        embed = discord.Embed(title=f"💬 Top Topics — #{target_channel.name}", description=desc, color=discord.Color.purple())
        await interaction.followup.send(embed=embed)

    # 6. Active Channels Leaderboard
    @app_commands.command(name="channels", description="Display the most active channels in this server.")
    async def show_active_channels(self, interaction: discord.Interaction):
        await interaction.response.defer()
        results = database.get_channel_leaderboard(str(interaction.guild_id), limit=10)

        if not results:
            await interaction.followup.send("❌ No channel analytics found. Run `/analytics ingest` first!")
            return

        desc = ""
        for idx, item in enumerate(results, 1):
            ch = interaction.guild.get_channel(int(item['channel_id']))
            ch_mention = ch.mention if ch else f"<#{item['channel_id']}>"
            avg_len = round(item['total_chars'] / max(1, item['message_count']), 1)
            desc += f"**{idx}.** {ch_mention} — **{item['message_count']:,}** msgs *(avg {avg_len} chars)*\n"

        embed = discord.Embed(title=f"📊 Most Active Channels — {interaction.guild.name}", description=desc, color=discord.Color.teal())
        await interaction.followup.send(embed=embed)

    # 7. Activity Heatmap
    @app_commands.command(name="activity", description="Display peak activity windows in this server.")
    async def show_activity(self, interaction: discord.Interaction):
        await interaction.response.defer()
        results = database.get_peak_activity(str(interaction.guild_id), limit=7)
        
        if not results:
            await interaction.followup.send("❌ No activity data found.")
            return

        desc = "".join([f"**{i}.** `{item['day_hour']}` — **{item['count']:,}** messages\n" for i, item in enumerate(results, 1)])
        embed = discord.Embed(title=f"📈 Peak Chat Activity — {interaction.guild.name}", description=desc, color=discord.Color.gold())
        await interaction.followup.send(embed=embed)

    # 8. User Leaderboard
    @app_commands.command(name="leaderboard", description="Display top active chatters in this server.")
    async def show_leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        results = database.get_top_users(str(interaction.guild_id), limit=10)
        
        if not results:
            await interaction.followup.send("❌ No user analytics found.")
            return

        desc = ""
        for idx, user in enumerate(results, 1):
            avg_len = round(user['total_chars'] / max(1, user['message_count']), 1)
            desc += f"**{idx}.** `{user['username']}` — **{user['message_count']:,}** msgs *(avg {avg_len} chars)*\n"

        embed = discord.Embed(title=f"🏆 Top Chatter Leaderboard — {interaction.guild.name}", description=desc, color=discord.Color.green())
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AnalyticsCog(bot))