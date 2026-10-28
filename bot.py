import discord
from discord.ext import bridge
from loguru import logger as log
intents = discord.Intents.all()
bot = bridge.Bot(command_prefix="!", intents=intents)

@bot.event 
async def on_ready():
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    log.info("------")

@bot.bridge_command(name="ping", description="Check the bot's latency.")
async def ping(ctx: bridge.BridgeContext):
    latency = round(bot.latency * 1000)  # Convert to milliseconds
    await ctx.respond(embed=discord.Embed(
        title="Pong! 🏓",
        description=f"Latency: `{latency}ms`",
        color=discord.Color.red()
    ))

if __name__ == "__main__":
    from dotenv import get_key

    cogs = [
        "cogs.blackjack_cog"
    ]
    
    for cog in cogs:
        bot.load_extension(cog)
        
    TOKEN = get_key(".env", "DISCORD_BOT_TOKEN")
    bot.run(TOKEN)