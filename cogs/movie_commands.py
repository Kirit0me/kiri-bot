import asyncio
import re
import random
import discord
from discord import app_commands
from discord.ext import commands
from rapidfuzz import fuzz
import movie_api
import database


def normalize_text(text: str) -> str:
    """Removes spaces, punctuation, symbols, and converts to lowercase."""
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower()


def is_similar_enough(guess: str, actual: str, threshold: float = 75.0) -> bool:
    """Flexible matching allowing normalized substrings, missing hyphens/colons, and typos."""
    norm_guess = normalize_text(guess)
    norm_actual = normalize_text(actual)

    if not norm_guess:
        return False

    if norm_guess == norm_actual:
        return True

    main_title = actual.split(':')[0].split('-')[0].strip()
    norm_main = normalize_text(main_title)
    if norm_guess == norm_main or norm_main in norm_guess or norm_guess in norm_main:
        return True

    if norm_guess in norm_actual or norm_actual in norm_guess:
        return True

    return fuzz.token_sort_ratio(guess.lower(), actual.lower()) >= threshold


class MovieQuizCog(commands.GroupCog, name="movie"):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    # 1. /movie scene
    @app_commands.command(name="scene", description="Guess movies from 3 scene pictures revealed every 5 seconds!")
    @app_commands.choices(difficulty=[
        app_commands.Choice(name="Easy (1 pt)", value="easy"),
        app_commands.Choice(name="Medium (2 pts)", value="medium"),
        app_commands.Choice(name="Hard (3 pts)", value="hard")
    ])
    @app_commands.describe(rounds="Number of rounds to play (1-10)", difficulty="Difficulty level")
    async def guess_scene(
        self, 
        interaction: discord.Interaction, 
        rounds: app_commands.Range[int, 1, 10] = 3, 
        difficulty: app_commands.Choice[str] = None
    ):
        diff_value = difficulty.value if difficulty else "easy"
        await interaction.response.defer()

        scores = {}
        await interaction.followup.send(
            f"🎬 **Starting Movie Scene Quiz!**\n"
            f"📊 **Rounds:** {rounds} | ⚡ **Difficulty:** {diff_value.capitalize()}\n"
            f"*Get ready! Round 1 starts in 3 seconds...*"
        )
        await asyncio.sleep(3)

        for current_round in range(1, rounds + 1):
            movie_data = await movie_api.fetch_random_popular_movie(difficulty=diff_value)
            details = await movie_api.get_movie_details(movie_data['id'])
            
            backdrops = details.get('clean_backdrops', [])
            if not backdrops:
                continue

            num_scenes = min(3, len(backdrops))
            selected_scenes = random.sample(backdrops, k=num_scenes)
            movie_title = details['title']

            await interaction.channel.send(
                f"🎬 **Round {current_round}/{rounds} — Guess the Movie!**\n"
                f"⏱️ You have **20 seconds**! New scenes reveal every 5 seconds..."
            )

            scene1_url = f"https://image.tmdb.org/t/p/w780{selected_scenes[0]['file_path']}"
            embed1 = discord.Embed(title="📸 Scene 1/3", color=discord.Color.blue())
            embed1.set_image(url=scene1_url)
            await interaction.channel.send(embed=embed1)

            def check(msg):
                if msg.channel != interaction.channel or msg.author.bot:
                    return False
                return is_similar_enough(msg.content, movie_title)

            guess_task = asyncio.create_task(self.bot.wait_for('message', check=check))
            winner = None
            
            # Segment 1: Wait 5s
            done, _ = await asyncio.wait([guess_task], timeout=5.0)
            if done:
                winner = guess_task.result()

            # Segment 2: Send Scene 2 & Wait 5s
            if not winner and len(selected_scenes) > 1:
                scene2_url = f"https://image.tmdb.org/t/p/w780{selected_scenes[1]['file_path']}"
                embed2 = discord.Embed(title="📸 Scene 2/3 (Clue Revealed!)", color=discord.Color.gold())
                embed2.set_image(url=scene2_url)
                await interaction.channel.send(embed=embed2)

                done, _ = await asyncio.wait([guess_task], timeout=5.0)
                if done:
                    winner = guess_task.result()

            # Segment 3: Send Scene 3 & Wait 10s
            if not winner and len(selected_scenes) > 2:
                scene3_url = f"https://image.tmdb.org/t/p/w780{selected_scenes[2]['file_path']}"
                embed3 = discord.Embed(title="📸 Scene 3/3 (Final Clue!)", color=discord.Color.orange())
                embed3.set_image(url=scene3_url)
                await interaction.channel.send(embed=embed3)

                done, _ = await asyncio.wait([guess_task], timeout=10.0)
                if done:
                    winner = guess_task.result()

            if not winner and not guess_task.done():
                guess_task.cancel()

            if winner:
                earned = database.add_quiz_score(
                    guild_id=str(interaction.guild_id),
                    user_id=str(winner.author.id),
                    username=winner.author.display_name,
                    difficulty=diff_value
                )
                scores[winner.author] = scores.get(winner.author, 0) + earned
                await interaction.channel.send(
                    f"🎉 **Correct {winner.author.mention}!** The movie is **{movie_title}**! *(+{earned} pts)*\n"
                )
            else:
                await interaction.channel.send(f"⏰ **Time's up!** The movie was **{movie_title}**.")

            if current_round < rounds:
                await asyncio.sleep(3)

        summary = "🏆 **Final Scoreboard:**\n"
        if not scores:
            summary += "No points scored this game!"
        else:
            sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
            for rank, (player, score) in enumerate(sorted_scores, start=1):
                summary += f"{rank}. {player.mention} — **{score} pt(s)**\n"

        await interaction.channel.send(summary)

    # 2. /movie actor
    @app_commands.command(name="actor", description="Guess actors from character roles across multiple rounds!")
    @app_commands.choices(difficulty=[
        app_commands.Choice(name="Easy (1 pt)", value="easy"),
        app_commands.Choice(name="Medium (2 pts)", value="medium"),
        app_commands.Choice(name="Hard (3 pts)", value="hard")
    ])
    @app_commands.describe(rounds="Number of rounds to play (1-10)", difficulty="Difficulty level")
    async def guess_actor(
        self, 
        interaction: discord.Interaction, 
        rounds: app_commands.Range[int, 1, 10] = 3, 
        difficulty: app_commands.Choice[str] = None
    ):
        diff_value = difficulty.value if difficulty else "easy"
        await interaction.response.defer()

        scores = {}
        await interaction.followup.send(
            f"🎭 **Starting Actor Quiz!**\n"
            f"📊 **Rounds:** {rounds} | ⚡ **Difficulty:** {diff_value.capitalize()}\n"
            f"*Get ready! Round 1 starts in 3 seconds...*"
        )
        await asyncio.sleep(3)

        for current_round in range(1, rounds + 1):
            movie_data = await movie_api.fetch_random_popular_movie(difficulty=diff_value)
            details = await movie_api.get_movie_details(movie_data['id'])
            
            cast = details.get('credits', {}).get('cast', [])
            if not cast:
                continue

            actor = cast[0]
            actor_name = actor['name']
            character_name = actor['character']
            movie_title = details['title']

            await interaction.channel.send(
                f"🎭 **Round {current_round}/{rounds}:** Who played the character `{character_name}` in *\"{movie_title}\"*?\n"
                f"*Type your guess in text within 15 seconds!*"
            )

            def check(msg):
                if msg.channel != interaction.channel or msg.author.bot:
                    return False
                return is_similar_enough(msg.content, actor_name)

            try:
                winner = await self.bot.wait_for('message', timeout=15.0, check=check)
                earned = database.add_quiz_score(
                    guild_id=str(interaction.guild_id),
                    user_id=str(winner.author.id),
                    username=winner.author.display_name,
                    difficulty=diff_value
                )
                scores[winner.author] = scores.get(winner.author, 0) + earned
                await interaction.channel.send(f"🎉 **Correct {winner.author.mention}!** It was **{actor_name}**! *(+{earned} pts)*")
            except asyncio.TimeoutError:
                await interaction.channel.send(f"⏰ **Time's up!** The actor was **{actor_name}**.")

            if current_round < rounds:
                await asyncio.sleep(3)

        summary = "🏆 **Final Scoreboard:**\n"
        if not scores:
            summary += "No points scored this game!"
        else:
            sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
            for rank, (player, score) in enumerate(sorted_scores, start=1):
                summary += f"{rank}. {player.mention} — **{score} pt(s)**\n"

        await interaction.channel.send(summary)

    # 3. /movie director
    @app_commands.command(name="director", description="Guess directors of popular movies across multiple rounds!")
    @app_commands.choices(difficulty=[
        app_commands.Choice(name="Easy (1 pt)", value="easy"),
        app_commands.Choice(name="Medium (2 pts)", value="medium"),
        app_commands.Choice(name="Hard (3 pts)", value="hard")
    ])
    @app_commands.describe(rounds="Number of rounds to play (1-10)", difficulty="Difficulty level")
    async def guess_director(
        self, 
        interaction: discord.Interaction, 
        rounds: app_commands.Range[int, 1, 10] = 3, 
        difficulty: app_commands.Choice[str] = None
    ):
        diff_value = difficulty.value if difficulty else "easy"
        await interaction.response.defer()

        scores = {}
        await interaction.followup.send(
            f"🎬 **Starting Director Quiz!**\n"
            f"📊 **Rounds:** {rounds} | ⚡ **Difficulty:** {diff_value.capitalize()}\n"
            f"*Get ready! Round 1 starts in 3 seconds...*"
        )
        await asyncio.sleep(3)

        for current_round in range(1, rounds + 1):
            movie_data = await movie_api.fetch_random_popular_movie(difficulty=diff_value)
            details = await movie_api.get_movie_details(movie_data['id'])
            
            crew = details.get('credits', {}).get('crew', [])
            directors = [member['name'] for member in crew if member['job'] == 'Director']
            
            if not directors:
                continue

            director_name = directors[0]
            movie_title = details['title']
            release_year = details.get('release_date', '')[:4]

            await interaction.channel.send(
                f"🎬 **Round {current_round}/{rounds}:** Who directed *\"{movie_title}\"* ({release_year})?\n"
                f"*Type your guess in text within 15 seconds!*"
            )

            def check(msg):
                if msg.channel != interaction.channel or msg.author.bot:
                    return False
                return is_similar_enough(msg.content, director_name)

            try:
                winner = await self.bot.wait_for('message', timeout=15.0, check=check)
                earned = database.add_quiz_score(
                    guild_id=str(interaction.guild_id),
                    user_id=str(winner.author.id),
                    username=winner.author.display_name,
                    difficulty=diff_value
                )
                scores[winner.author] = scores.get(winner.author, 0) + earned
                await interaction.channel.send(f"🎉 **Correct {winner.author.mention}!** Directed by **{director_name}**! *(+{earned} pts)*")
            except asyncio.TimeoutError:
                await interaction.channel.send(f"⏰ **Time's up!** The director was **{director_name}**.")

            if current_round < rounds:
                await asyncio.sleep(3)

        summary = "🏆 **Final Scoreboard:**\n"
        if not scores:
            summary += "No points scored this game!"
        else:
            sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
            for rank, (player, score) in enumerate(sorted_scores, start=1):
                summary += f"{rank}. {player.mention} — **{score} pt(s)**\n"

        await interaction.channel.send(summary)

    # 4. /movie music
    @app_commands.command(name="music", description="Guess movies from soundtrack audio playing in VC!")
    @app_commands.choices(difficulty=[
        app_commands.Choice(name="Easy (1 pt)", value="easy"),
        app_commands.Choice(name="Medium (2 pts)", value="medium"),
        app_commands.Choice(name="Hard (3 pts)", value="hard")
    ])
    @app_commands.describe(rounds="Number of rounds to play (1-10)", difficulty="Difficulty level")
    async def guess_music(
        self, 
        interaction: discord.Interaction, 
        rounds: app_commands.Range[int, 1, 10] = 3, 
        difficulty: app_commands.Choice[str] = None
    ):
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ You must join a Voice Channel first!", ephemeral=True)
            return

        diff_value = difficulty.value if difficulty else "easy"
        await interaction.response.defer()

        voice_channel = interaction.user.voice.channel
        vc = await voice_channel.connect()
        scores = {}

        await interaction.followup.send(
            f"🎵 **Starting Movie Music Quiz in Voice Channel!**\n"
            f"📊 **Rounds:** {rounds} | ⚡ **Difficulty:** {diff_value.capitalize()}\n"
            f"*Get ready! Round 1 starts in 3 seconds...*"
        )
        await asyncio.sleep(3)

        try:
            for current_round in range(1, rounds + 1):
                movie_data = await movie_api.fetch_random_popular_movie(difficulty=diff_value)
                movie_title = movie_data['title']

                await interaction.channel.send(f"🔍 **Round {current_round}/{rounds}:** Fetching soundtrack stream...")
                stream_url = movie_api.get_youtube_audio_stream(f"{movie_title} official theme song audio")

                vc.play(discord.FFmpegPCMAudio(stream_url))
                await interaction.channel.send("🎵 **Playing soundtrack in VC!** Guess the movie title in text within 20s!")

                def check(msg):
                    if msg.channel != interaction.channel or msg.author.bot:
                        return False
                    return is_similar_enough(msg.content, movie_title)

                try:
                    winner = await self.bot.wait_for('message', timeout=20.0, check=check)
                    vc.stop()
                    earned = database.add_quiz_score(
                        guild_id=str(interaction.guild_id),
                        user_id=str(winner.author.id),
                        username=winner.author.display_name,
                        difficulty=diff_value
                    )
                    scores[winner.author] = scores.get(winner.author, 0) + earned
                    await interaction.channel.send(f"🎉 **Correct {winner.author.mention}!** The movie is **{movie_title}**! *(+{earned} pts)*")
                except asyncio.TimeoutError:
                    vc.stop()
                    await interaction.channel.send(f"⏰ **Time's up!** The movie was **{movie_title}**.")

                if current_round < rounds:
                    await asyncio.sleep(3)

        finally:
            await vc.disconnect()

        summary = "🏆 **Final Scoreboard:**\n"
        if not scores:
            summary += "No points scored this game!"
        else:
            sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
            for rank, (player, score) in enumerate(sorted_scores, start=1):
                summary += f"{rank}. {player.mention} — **{score} pt(s)**\n"

        await interaction.channel.send(summary)

    # 5. /movie leaderboard
    @app_commands.command(name="leaderboard", description="View the server quiz leaderboard!")
    async def quiz_leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        scores = database.get_quiz_leaderboard(str(interaction.guild_id), limit=10)

        if not scores:
            await interaction.followup.send("🏆 No quiz scores recorded yet! Play `/movie` or `/geo` games to earn points.")
            return

        desc = ""
        for idx, user in enumerate(scores, 1):
            desc += f"**{idx}.** `{user['username']}` — **{user['points']:,}** pts *(Correct: {user['correct_answers']:,})*\n"

        embed = discord.Embed(
            title=f"🏆 Cinema & Quiz Leaderboard — {interaction.guild.name}",
            description=desc,
            color=discord.Color.gold()
        )
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(MovieQuizCog(bot))