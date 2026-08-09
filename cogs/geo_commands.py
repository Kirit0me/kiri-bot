import asyncio
import random
import re
import discord
from discord import app_commands
from discord.ext import commands
from rapidfuzz import fuzz
import geo_api
import database


def normalize_text(text: str) -> str:
    """Strips punctuation, symbols, and extra spaces for matching."""
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower()


def is_similar_enough(guess: str, actual: str, threshold: float = 75.0) -> bool:
    """Handles minor typos and spelling differences (e.g. Washington DC vs Washington)."""
    norm_guess = normalize_text(guess)
    norm_actual = normalize_text(actual)

    if not norm_guess:
        return False

    if norm_guess == norm_actual or norm_guess in norm_actual or norm_actual in norm_guess:
        return True

    return fuzz.token_sort_ratio(guess.lower(), actual.lower()) >= threshold


class GeoQuizCog(commands.GroupCog, name="geo"):
    def __init__(self, bot):
        self.bot = bot
        self.countries = []
        super().__init__()

    async def cog_load(self):
        """Fetch countries database into memory when cog loads."""
        self.countries = await geo_api.fetch_all_countries()

    # 1. /geo flag
    @app_commands.command(name="flag", description="Guess the country from its flag picture!")
    @app_commands.describe(rounds="Number of rounds (1-10)")
    async def guess_flag(
        self, 
        interaction: discord.Interaction, 
        rounds: app_commands.Range[int, 1, 10] = 3
    ):
        await interaction.response.defer()
        if not self.countries:
            self.countries = await geo_api.fetch_all_countries()

        scores = {}
        await interaction.followup.send(
            f"🌍 **Starting Flag Quiz!** ({rounds} Rounds)\n"
            f"*Round 1 starts in 3 seconds...*"
        )
        await asyncio.sleep(3)

        for current_round in range(1, rounds + 1):
            country = random.choice(self.countries)
            country_name = country["name"]

            embed = discord.Embed(
                title=f"🚩 Round {current_round}/{rounds} — Which country's flag is this?",
                description="Type your guess in text within **15 seconds**!",
                color=discord.Color.green()
            )
            embed.set_image(url=country["flag"])
            await interaction.channel.send(embed=embed)

            def check(msg):
                if msg.channel != interaction.channel or msg.author.bot:
                    return False
                return is_similar_enough(msg.content, country_name)

            try:
                winner = await self.bot.wait_for("message", timeout=15.0, check=check)
                earned = database.add_quiz_score(
                    guild_id=str(interaction.guild_id),
                    user_id=str(winner.author.id),
                    username=winner.author.display_name,
                    difficulty="easy"  # Geo defaults to 1 pt
                )
                scores[winner.author] = scores.get(winner.author, 0) + earned
                await interaction.channel.send(
                    f"🎉 **Correct {winner.author.mention}!** It is **{country_name}**! *(+1 pt)*\n"
                )
            except asyncio.TimeoutError:
                await interaction.channel.send(
                    f"⏰ **Time's up!** The country was **{country_name}**."
                )

            if current_round < rounds:
                await asyncio.sleep(2)

        summary = "🏆 **Final Scoreboard:**\n"
        if not scores:
            summary += "No points scored this game!"
        else:
            for rank, (player, score) in enumerate(
                sorted(scores.items(), key=lambda x: x[1], reverse=True), start=1
            ):
                summary += f"{rank}. {player.mention} — **{score} pt(s)**\n"
        await interaction.channel.send(summary)

    # 2. /geo capital (Given Capital -> Guess Country)
    @app_commands.command(name="capital", description="Guess the country given its capital city!")
    @app_commands.describe(rounds="Number of rounds (1-10)")
    async def guess_country_from_capital(
        self, 
        interaction: discord.Interaction, 
        rounds: app_commands.Range[int, 1, 10] = 3
    ):
        await interaction.response.defer()
        if not self.countries:
            self.countries = await geo_api.fetch_all_countries()

        scores = {}
        await interaction.followup.send(
            f"🏛️ **Guess the Country from its Capital!** ({rounds} Rounds)\n"
            f"*Round 1 starts in 3 seconds...*"
        )
        await asyncio.sleep(3)

        for current_round in range(1, rounds + 1):
            country = random.choice(self.countries)
            capital_name = country["capital"]
            country_name = country["name"]

            await interaction.channel.send(
                f"🏛️ **Round {current_round}/{rounds}:** **`{capital_name}`** is the capital of which country?\n"
                f"*15 seconds to guess!*"
            )

            def check(msg):
                if msg.channel != interaction.channel or msg.author.bot:
                    return False
                return is_similar_enough(msg.content, country_name)

            try:
                winner = await self.bot.wait_for("message", timeout=15.0, check=check)
                earned = database.add_quiz_score(
                    guild_id=str(interaction.guild_id),
                    user_id=str(winner.author.id),
                    username=winner.author.display_name,
                    difficulty="easy"
                )
                scores[winner.author] = scores.get(winner.author, 0) + earned
                await interaction.channel.send(
                    f"🎉 **Correct {winner.author.mention}!** **{capital_name}** is the capital of **{country_name}**! *(+1 pt)*"
                )
            except asyncio.TimeoutError:
                await interaction.channel.send(
                    f"⏰ **Time's up!** The country was **{country_name}**."
                )

            if current_round < rounds:
                await asyncio.sleep(2)

        summary = "🏆 **Final Scoreboard:**\n"
        if not scores:
            summary += "No points scored this game!"
        else:
            for rank, (player, score) in enumerate(
                sorted(scores.items(), key=lambda x: x[1], reverse=True), start=1
            ):
                summary += f"{rank}. {player.mention} — **{score} pt(s)**\n"
        await interaction.channel.send(summary)

    # 3. /geo country (Given Country -> Guess Capital)
    @app_commands.command(name="country", description="Guess the capital city of a given country!")
    @app_commands.describe(rounds="Number of rounds (1-10)")
    async def guess_capital_from_country(
        self, 
        interaction: discord.Interaction, 
        rounds: app_commands.Range[int, 1, 10] = 3
    ):
        await interaction.response.defer()
        if not self.countries:
            self.countries = await geo_api.fetch_all_countries()

        scores = {}
        await interaction.followup.send(
            f"📍 **Guess the Capital City!** ({rounds} Rounds)\n"
            f"*Round 1 starts in 3 seconds...*"
        )
        await asyncio.sleep(3)

        for current_round in range(1, rounds + 1):
            country = random.choice(self.countries)
            capital_name = country["capital"]
            country_name = country["name"]

            await interaction.channel.send(
                f"📍 **Round {current_round}/{rounds}:** What is the capital city of **`{country_name}`**?\n"
                f"*15 seconds to guess!*"
            )

            def check(msg):
                if msg.channel != interaction.channel or msg.author.bot:
                    return False
                return is_similar_enough(msg.content, capital_name)

            try:
                winner = await self.bot.wait_for("message", timeout=15.0, check=check)
                earned = database.add_quiz_score(
                    guild_id=str(interaction.guild_id),
                    user_id=str(winner.author.id),
                    username=winner.author.display_name,
                    difficulty="easy"
                )
                scores[winner.author] = scores.get(winner.author, 0) + earned
                await interaction.channel.send(
                    f"🎉 **Correct {winner.author.mention}!** The capital of **{country_name}** is **{capital_name}**! *(+1 pt)*"
                )
            except asyncio.TimeoutError:
                await interaction.channel.send(
                    f"⏰ **Time's up!** The capital was **{capital_name}**."
                )

            if current_round < rounds:
                await asyncio.sleep(2)

        summary = "🏆 **Final Scoreboard:**\n"
        if not scores:
            summary += "No points scored this game!"
        else:
            for rank, (player, score) in enumerate(
                sorted(scores.items(), key=lambda x: x[1], reverse=True), start=1
            ):
                summary += f"{rank}. {player.mention} — **{score} pt(s)**\n"
        await interaction.channel.send(summary)

    # 4. /geo leaderboard
    @app_commands.command(name="leaderboard", description="View the server quiz leaderboard!")
    async def quiz_leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        scores = database.get_quiz_leaderboard(str(interaction.guild_id), limit=10)

        if not scores:
            await interaction.followup.send("🏆 No quiz scores recorded yet! Play `/geo` or `/movie` games to earn points.")
            return

        desc = ""
        for idx, user in enumerate(scores, 1):
            desc += f"**{idx}.** `{user['username']}` — **{user['points']:,}** pts *(Correct: {user['correct_answers']:,})*\n"

        embed = discord.Embed(
            title=f"🏆 Server Quiz Leaderboard — {interaction.guild.name}",
            description=desc,
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(GeoQuizCog(bot))