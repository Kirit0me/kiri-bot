import discord
from discord.ext import commands
from blacktea import BlackteaGame


class BlackteaLobbyView(discord.ui.View):
    def __init__(self, host: discord.Member):
        super().__init__(timeout=120.0)  # Lobby expires after 2 minutes if idle
        self.host = host
        self.players = [host]
        self.started = False

    @discord.ui.button(label="Join Game", style=discord.ButtonStyle.green, emoji="✋")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.players:
            await interaction.response.send_message("You are already in the lobby!", ephemeral=True)
            return

        self.players.append(interaction.user)
        player_list_str = ", ".join([p.display_name for p in self.players])
        await interaction.response.send_message(f"✅ {interaction.user.mention} joined!", ephemeral=False)
        
        # Update original lobby message text
        await interaction.message.edit(
            content=f"🎮 **Blacktea Lobby** (Created by {self.host.mention})\n"
                    f"**Players ({len(self.players)}):** {player_list_str}"
        )

    @discord.ui.button(label="Start Game", style=discord.ButtonStyle.blurple, emoji="▶️")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Only the host who created the lobby can click Start
        if interaction.user != self.host:
            await interaction.response.send_message("❌ Only the lobby host can start the game!", ephemeral=True)
            return

        self.started = True
        self.stop()  # Stop listening for button clicks
        
        # Disable buttons once game starts
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        
        await interaction.response.send_message("🚀 Starting Blacktea!", ephemeral=False)


class WordGamesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}

    @commands.command(name="blacktea")
    async def blacktea_cmd(self, ctx):
        channel_id = ctx.channel.id

        if channel_id in self.active_games:
            await ctx.send("⚠️ A game is already in progress in this channel!")
            return

        # Create lobby View with Join and Start buttons
        view = BlackteaLobbyView(host=ctx.author)
        lobby_msg = await ctx.send(
            f"🎮 **Blacktea Lobby** (Created by {ctx.author.mention})\n"
            f"**Players (1):** {ctx.author.display_name}\n"
            f"*Click 'Join Game' to enter or 'Start Game' (Host only).*",
            view=view
        )

        # Wait for the host to click Start Game (or lobby to time out)
        await view.wait()

        if not view.started:
            await ctx.send("⏳ Lobby timed out because the game wasn't started.")
            return

        # Initialize & start game session
        game = BlackteaGame(self.bot, ctx, view.players)
        self.active_games[channel_id] = game

        try:
            await game.start()
        finally:
            if channel_id in self.active_games:
                del self.active_games[channel_id]


async def setup(bot):
    await bot.add_cog(WordGamesCog(bot))