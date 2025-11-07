import discord
from discord.ext import commands
from dotenv import load_dotenv
import json, os
from utils.status_cycle import cycle_status

load_dotenv("./config/.env")
TOKEN = os.getenv("TOKEN")

COGS_FILE = "./config/cogs.json"

class AsyncBOT(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(
            command_prefix=".",  # prefixo fantasma (nunca será usado)
            intents=intents
        )

    async def on_message(self, message: discord.Message):
        # Ignora completamente mensagens de texto
        return

    async def setup_hook(self):
        with open(COGS_FILE, "r") as f:
            data = json.load(f)

        loaded = data["loaded"]
        unloaded = data["unloaded"]

        all_cogs = [
            file[:-3] for file in os.listdir("./cogs")
            if file.endswith(".py") and file not in ("__init__.py", "core.py")
        ]

        # Se existe cog na pasta que não está nem em loaded nem unloaded → ela é nova → adiciona como loaded
        for cog in all_cogs:
            if cog not in loaded and cog not in unloaded:
                loaded.append(cog)

        with open(COGS_FILE, "w") as f:
            json.dump({"loaded": loaded, "unloaded": unloaded}, f, indent=4)

        # Carregar cogs
        for cog in loaded:
            try:
                await self.load_extension(f"cogs.{cog}")
                print(f"🔹 Cog carregada: {cog}")
            except Exception as e:
                print(f"❌ Falha ao carregar {cog}: {e}")

        await self.load_extension("cogs.core")

        synced = await self.tree.sync()
        print(f"✅ Slash Commands sincronizados GLOBALMENTE ({len(synced)} comandos).")

    async def on_ready(self):
        print(f"🤖 {self.user} está online!")
        self.loop.create_task(cycle_status(self))


bot = AsyncBOT()
bot.run(TOKEN)
