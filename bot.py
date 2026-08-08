import asyncio
import logging
import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("KiriBot")

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

# Disable built-in help command so we can define our own custom help command
bot = commands.Bot(command_prefix=["kiri"], intents=intents, help_command=None)


def build_help_embed() -> discord.Embed:
    """Returns a nicely formatted Help Embed for slash and prefix commands."""
    embed = discord.Embed(
        title="🎮 Kiri-Bot Game Menu",
        description="Here are all the games and commands you can play in this server!",
        color=discord.Color.gold()
    )
    embed.add_field(
        name="🎬 Movie Quiz (`/movie`)",
        value=(
            "• `/movie scene` — Guess the movie from a screenshot\n"
            "• `/movie actor` — Guess who played the character\n"
            "• `/movie director` — Guess who directed the movie\n"
            "• `/movie music` — Guess the soundtrack playing in VC!"
        ),
        inline=False
    )
    embed.add_field(
        name="🌍 Geography Quiz (`/geo`)",
        value=(
            "• `/geo flag` — Guess the country from its flag\n"
            "• `/geo capital` — Guess country given its capital city\n"
            "• `/geo country` — Guess capital city given its country"
        ),
        inline=False
    )
    embed.add_field(
        name="ℹ️ Info & Utility",
        value="• `/help` or `kirihelp` — Shows this menu\n• `!sync` — Syncs slash commands (Owner only)",
        inline=False
    )
    embed.set_footer(text="Specify rounds (1-10) and difficulty when launching any game!")
    return embed


@bot.event
async def setup_hook():
    logger.info("⚙️ Loading Cogs...")
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            await bot.load_extension(f'cogs.{filename[:-3]}')
            logger.info(f"✅ Loaded Cog: {filename[:-3]}")


@bot.event
async def on_ready():
    logger.info(f"🤖 Bot is online! Logged in as {bot.user.name} ({bot.user.id})")


# -------------------------------------------------------------
# 1. Custom 'kiri' Message Trigger (Add your funny response here!)
# -------------------------------------------------------------
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    content_lower = message.content.strip().lower()

    # Match exact 'kiri' or messages starting with 'kiri ' (excluding 'kirihelp')
    is_kiri_trigger = (
        content_lower == "kiri" 
        or (content_lower.startswith("kiri ") and not content_lower.startswith("kirihelp"))
        or (bot.user.mentioned_in(message) and not message.content.startswith("!"))
    )

    if is_kiri_trigger:
        logger.info(f"💬 [Kiri Trigger] {message.author} in #{message.channel}: '{message.content}'")

        # 👇 YOUR CUSTOM FUNNY EMBED & TAGS HERE 👇
        embed = discord.Embed(
            title="👀 You called for Kiri?",
            description=f"Here is an auto generated message from the author of this bot. I am prolly playing games or reading books so leave me alone, {message.author.mention} eh?",
            color=discord.Color.magenta()
        )
        embed.set_thumbnail(url=message.author.display_avatar.url)
        embed.set_footer(text="Type /help or 'kirihelp' if you actually wanted the game menu!")

        await message.channel.send(content=f"Hey {message.author.mention}!", embed=embed)

    await bot.process_commands(message)


# -------------------------------------------------------------
# 2. /help Slash Command
# -------------------------------------------------------------
@bot.tree.command(name="help", description="Show all available games and commands!")
async def help_slash_command(interaction: discord.Interaction):
    logger.info(f"⚡ [Slash Command] /help executed by {interaction.user}")
    embed = build_help_embed()
    await interaction.response.send_message(embed=embed)


# -------------------------------------------------------------
# 3. kirihelp / !help Prefix Command
# -------------------------------------------------------------
@bot.command(name="kirihelp", aliases=["help"])
async def help_prefix_command(ctx):
    logger.info(f"💬 [Prefix Command] help/kirihelp executed by {ctx.author}")
    embed = build_help_embed()
    await ctx.send(embed=embed)


# -------------------------------------------------------------
# 4. Global Slash Command Execution Logging
# -------------------------------------------------------------
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.application_command:
        cmd_name = interaction.command.qualified_name if interaction.command else "Unknown"
        user = interaction.user
        guild = interaction.guild.name if interaction.guild else "DM"
        channel = interaction.channel.name if interaction.channel else "Unknown Channel"
        logger.info(f"⚡ [Slash Command] /{cmd_name} executed by {user} in [{guild} -> #{channel}]")


# -------------------------------------------------------------
# 5. Manual Sync Command
# -------------------------------------------------------------
@bot.command(name="sync")
@commands.is_owner()
async def sync(ctx):
    await ctx.send("Syncing slash commands to this server...")
    bot.tree.copy_global_to(guild=ctx.guild)
    synced = await bot.tree.sync(guild=ctx.guild)
    logger.info(f"⚡ Synced {len(synced)} slash commands directly to guild '{ctx.guild.name}'")
    await ctx.send(f"⚡ Done! Synced **{len(synced)}** slash commands directly to this server.")


async def main():
    async with bot:
        await bot.start(TOKEN)


if __name__ == '__main__':
    asyncio.run(main())