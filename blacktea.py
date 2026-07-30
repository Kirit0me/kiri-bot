import asyncio
import random
import discord

# Load dictionary
with open("words.txt", "r") as f:
    VALID_WORDS = set(word.strip().lower() for word in f if len(word.strip()) >= 3)

SYLLABLES = ["tea", "ing", "str", "con", "pre", "act", "ver", "ous", "ion", "cat", "pro"]

def render_progress_bar(remaining: float, total: float = 12.0) -> str:
    """Generates a visual progress bar string representing time left."""
    length = 10
    ratio = max(0.0, min(1.0, remaining / total))
    filled = int(round(ratio * length))
    bar = "█" * filled + "░" * (length - filled)
    return f"`[{bar}]` **{int(remaining)}s**"

class BlackteaGame:
    def __init__(self, bot, ctx, players):
        self.bot = bot
        self.ctx = ctx
        self.players = players
        self.used_words = set()
        self.lives = {p: 2 for p in players}
        self.current_idx = 0
        self.is_active = True
        self.single_player = len(players) == 1

    async def start(self):
        mode_text = "Solo Survival Mode" if self.single_player else "Multiplayer Battle"
        await self.ctx.send(
            f"🎮 **Blacktea Game Started!** ({mode_text})\n"
            f"Players: {', '.join([p.mention for p in self.players])}"
        )
        
        # Game loop continues until active flag cleared or no players left
        while self.is_active and len(self.players) > 0:
            current_player = self.players[self.current_idx]
            syllable = random.choice(SYLLABLES)
            
            # Send initial prompt message
            prompt_msg = await self.ctx.send(
                f"\n👉 {current_player.mention}'s turn! Type a word containing: **`{syllable.upper()}`**\n"
                f"Lives: {'❤️' * self.lives[current_player]}\n"
                f"Time Left: {render_progress_bar(12.0)}"
            )

            def check(msg):
                return (
                    msg.author == current_player and
                    msg.channel == self.ctx.channel and
                    syllable in msg.content.lower() and
                    msg.content.lower() in VALID_WORDS and
                    msg.content.lower() not in self.used_words
                )

            # Timer loop with visual updates
            word_found = False
            total_time = 12.0
            time_remaining = total_time
            tick_rate = 2.0  # Update progress bar every 2 seconds

            while time_remaining > 0:
                try:
                    # Wait for message in small intervals so we can update timer UI
                    msg = await self.bot.wait_for('message', timeout=tick_rate, check=check)
                    word = msg.content.lower()
                    self.used_words.add(word)
                    await msg.add_reaction("✅")
                    word_found = True
                    break  # Correct word guessed!
                except asyncio.TimeoutError:
                    time_remaining -= tick_rate
                    if time_remaining > 0:
                        # Update progress bar in Discord message
                        await prompt_msg.edit(
                            content=(
                                f"👉 {current_player.mention}'s turn! Type a word containing: **`{syllable.upper()}`**\n"
                                f"Lives: {'❤️' * self.lives[current_player]}\n"
                                f"Time Left: {render_progress_bar(time_remaining)}"
                            )
                        )

            # Handle timeout/failure
            if not word_found:
                self.lives[current_player] -= 1
                await prompt_msg.edit(
                    content=(
                        f"👉 {current_player.mention}'s turn! Type a word containing: **`{syllable.upper()}`**\n"
                        f"Lives: {'❤️' * self.lives[current_player]}\n"
                        f"Time Left: `[░░░░░░░░░░]` **0s** ⏰ **TIME UP!**"
                    )
                )

                if self.lives[current_player] <= 0:
                    await self.ctx.send(f"💀 {current_player.mention} has run out of lives and is eliminated!")
                    self.players.remove(current_player)
                    
                    if self.single_player or len(self.players) == 0:
                        break

                    if self.current_idx >= len(self.players):
                        self.current_idx = 0
                    continue

            # Move to next turn
            if not self.single_player and len(self.players) > 1:
                self.current_idx = (self.current_idx + 1) % len(self.players)

        # Game Over logic
        if self.single_player:
            words_count = len(self.used_words)
            await self.ctx.send(f"\n🏁 **Game Over!** You survived for **{words_count}** words! 🎉")
        else:
            if len(self.players) == 1:
                winner = self.players[0]
                await self.ctx.send(f"\n🏆 **{winner.mention} wins the game!** 🎉")
            else:
                await self.ctx.send("\n🏁 **Game Over!**")