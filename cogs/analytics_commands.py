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

    # Ingest up to 1,000,000 messages
    @app_commands.command(name="ingest", description="Stream channel message history to Kafka (Up to 1,000,000).")
    @app_commands.describe(limit="Number of recent messages to scan (Max 1,000,000)")
    @app_commands.checks.has_permissions(administrator=True)
    async def ingest_history(self, interaction: discord.Interaction, limit: app_commands.Range[int, 10, 1000000] = 10000):
        await interaction.response.defer()

        count = 0
        logger.info(f"📥 High-volume ingestion started ({limit} max) for #{interaction.channel.name}...")

        try:
            async for message in interaction.channel.history(limit=limit, oldest_first=False):
                if message.author.bot or not message.content:
                    continue

                kafka_producer.send_message_to_kafka(
                    guild_id=str(interaction.guild_id),
                    channel_id=str(interaction.channel_id),
                    message_id=str(message.id),
                    content=message.content,
                    timestamp=message.created_at.isoformat()
                )
                count += 1

                # Yield control every 500 messages to prevent blocking the async loop
                if count % 500 == 0:
                    await asyncio.sleep(0.05)

            kafka_producer.flush_kafka()
            await interaction.followup.send(
                f"✅ **Ingestion Complete!** Streamed **{count:,}** messages to Kafka.\n"
                f"⚡ PySpark is processing topics & peak activity hours in real time!"
            )
        except Exception as e:
            logger.error(f"❌ Ingestion failed: {e}")
            await interaction.followup.send("❌ Error streaming messages to Kafka.", ephemeral=True)

    # Command: Show Peak Active Hours
    @app_commands.command(name="activity", description="Display peak active hours in this server!")
    async def show_activity(self, interaction: discord.Interaction):
        await interaction.response.defer()

        results = database.get_peak_activity(str(interaction.guild_id))
        if not results:
            await interaction.followup.send("❌ No activity data logged yet! Run `/analytics ingest` first.")
            return

        top_hours = results[:5]
        description = "🔥 **Most Active Hours (UTC):**\n\n"
        for rank, item in enumerate(top_hours, start=1):
            description += f"**{rank}.** `{item['hour']}` — **{item['count']:,}** messages\n"

        embed = discord.Embed(
            title=f"📈 Peak Chat Activity — {interaction.guild.name}",
            description=description,
            color=discord.Color.gold()
        )
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AnalyticsCog(bot))