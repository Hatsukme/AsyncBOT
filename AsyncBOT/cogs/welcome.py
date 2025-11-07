import discord
from discord.ext import commands

from utils.welcome import send_welcome


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        # Chama a função que envia a mensagem
        await send_welcome(self.bot, member)


async def setup(bot):
    await bot.add_cog(Welcome(bot))
