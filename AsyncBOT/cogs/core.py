import discord, json, os
from discord.ext import commands
from discord import app_commands

COGS_FILE = "./config/cogs.json"
ADMIN_FILE = "./config/admin.json"

class Core(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ------------------------
    # Carregar / salvar config
    # ------------------------
    def load_data(self, file):
        with open(file, "r") as f:
            return json.load(f)

    def save_data(self, file, data):
        with open(file, "w") as f:
            json.dump(data, f, indent=4)

    # ------------------------
    # Verificar permissão
    # ------------------------
    def check_admin(self, user_id):
        admin_data = self.load_data(ADMIN_FILE)

        bot_owner = admin_data["bot_owner"]
        admins = admin_data["admins"]

        # Se bot_owner é lista → verifica se user_id está nela
        if isinstance(bot_owner, list):
            if user_id in bot_owner:
                return True
        else:
            # Se bot_owner é número → compara direto
            if user_id == bot_owner:
                return True

        # Verifica admins
        if user_id in admins:
            return True

        return False

    async def deny(self, interaction):
        await interaction.response.send_message("❌ Você não tem permissão para isso.", ephemeral=True)

    # ------------------------
    # /addadmin
    # ------------------------
    @app_commands.command(name="addadmin", description="Autoriza um usuário a gerenciar o bot.")
    async def addadmin(self, interaction: discord.Interaction, user: discord.Member):
        if not self.check_admin(interaction.user.id):
            return await self.deny(interaction)

        data = self.load_data(ADMIN_FILE)
        if user.id not in data["admins"]:
            data["admins"].append(user.id)
            self.save_data(ADMIN_FILE, data)
            await interaction.response.send_message(f"✅ `{user.display_name}` agora é admin do bot.")
        else:
            await interaction.response.send_message(f"⚠️ `{user.display_name}` já é admin.")

    # ------------------------
    # /rmvadmin
    # ------------------------
    @app_commands.command(name="rmvadmin", description="Remove permissão de administrador do bot.")
    async def rmvadmin(self, interaction: discord.Interaction, user: discord.Member):
        if not self.check_admin(interaction.user.id):
            return await self.deny(interaction)

        data = self.load_data(ADMIN_FILE)
        if user.id in data["admins"]:
            data["admins"].remove(user.id)
            self.save_data(ADMIN_FILE, data)
            await interaction.response.send_message(f"❎ `{user.display_name}` removido da lista de admins.")
        else:
            await interaction.response.send_message(f"⚠️ `{user.display_name}` não é admin.")

    # ------------------------
    # Comandos de cog (agora protegidos)
    # ------------------------
    @app_commands.command(name="load", description="Carrega uma cog.")
    async def load(self, interaction: discord.Interaction, cog: str):
        if not self.check_admin(interaction.user.id):
            return await self.deny(interaction)

        data = self.load_data(COGS_FILE)

        if cog in data["loaded"]:
            return await interaction.response.send_message(f"⚠️ `{cog}` já está carregada.")

        if not os.path.exists(f"./cogs/{cog}.py"):
            return await interaction.response.send_message(f"❌ Cog `{cog}` não existe.")

        await self.bot.load_extension(f"cogs.{cog}")
        data["loaded"].append(cog)
        if cog in data["unloaded"]:
            data["unloaded"].remove(cog)

        self.save_data(COGS_FILE, data)
        await interaction.response.send_message(f"✅ `{cog}` carregada e salva.")

    @app_commands.command(name="unload", description="Descarrega uma cog.")
    async def unload(self, interaction: discord.Interaction, cog: str):
        if not self.check_admin(interaction.user.id):
            return await self.deny(interaction)

        data = self.load_data(COGS_FILE)

        if cog not in data["loaded"]:
            return await interaction.response.send_message(f"⚠️ `{cog}` não está carregada.")

        await self.bot.unload_extension(f"cogs.{cog}")
        data["loaded"].remove(cog)
        data["unloaded"].append(cog)

        self.save_data(COGS_FILE, data)
        await interaction.response.send_message(f"❎ `{cog}` descarregada e salva.")

    @app_commands.command(name="reload", description="Recarrega uma cog.")
    async def reload(self, interaction: discord.Interaction, cog: str):
        if not self.check_admin(interaction.user.id):
            return await self.deny(interaction)

        try:
            await self.bot.reload_extension(f"cogs.{cog}")
            await interaction.response.send_message(f"🔄 `{cog}` recarregada.")
        except Exception as e:
            await interaction.response.send_message(f"❌ {e}")

async def setup(bot):
    await bot.add_cog(Core(bot))
