import asyncio
import discord
from .phrase_builder import gerar_frase_status

async def cycle_status(bot):
    await bot.wait_until_ready()

    while not bot.is_closed():
        frase = gerar_frase_status()
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=frase
            )
        )
        await asyncio.sleep(35)  # tempo entre trocas
