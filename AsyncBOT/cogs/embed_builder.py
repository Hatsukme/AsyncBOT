import discord
from discord.ext import commands
from discord import app_commands
import json, asyncio, time
from pathlib import Path

ADMIN_FILE = Path("./config/admin.json")
ACTIVE_EMBEDS = {}


def check_admin(uid: int) -> bool:
    """Verifica se o usuário está no admin.json"""
    with open(ADMIN_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if uid in data.get("admins", []):
        return True
    owners = data.get("bot_owner", [])
    return uid in owners if isinstance(owners, list) else uid == owners


async def cleanup_cache():
    """Remove sessões antigas (timeout de 10min)"""
    while True:
        now = time.time()
        for uid in list(ACTIVE_EMBEDS.keys()):
            if now - ACTIVE_EMBEDS[uid]["timestamp"] > 600:
                del ACTIVE_EMBEDS[uid]
        await asyncio.sleep(300)


class EmbedBuilder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(cleanup_cache())

    @app_commands.command(name="embed", description="Cria e envia um embed personalizado.")
    async def embed(self, interaction: discord.Interaction, canal: discord.TextChannel):
        if not check_admin(interaction.user.id):
            return await interaction.response.send_message("❌ Você não tem permissão pra isso.", ephemeral=True)

        if interaction.user.id in ACTIVE_EMBEDS:
            return await interaction.response.send_message("⚠️ Você já está editando um embed!", ephemeral=True)

        modal = EmbedModal(interaction.user, canal)
        await interaction.response.send_modal(modal)


class EmbedModal(discord.ui.Modal, title="🧱 Criador de Embed"):
    def __init__(self, autor: discord.Member, canal: discord.TextChannel):
        super().__init__()
        self.autor = autor
        self.canal = canal

        self.titulo = discord.ui.TextInput(label="Título", required=False)
        self.descricao = discord.ui.TextInput(label="Descrição", style=discord.TextStyle.paragraph, required=False)
        self.cor = discord.ui.TextInput(label="Cor (hex)", placeholder="#00A2FF", required=False)
        self.add_item(self.titulo)
        self.add_item(self.descricao)
        self.add_item(self.cor)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            color = int(self.cor.value.strip("#"), 16) if self.cor.value else 0x00A2FF
        except:
            color = 0x00A2FF

        embed = discord.Embed(
            title=self.titulo.value or "Sem título",
            description=self.descricao.value or "",
            color=color
        )
        embed.set_author(name=self.autor.display_name, icon_url=self.autor.display_avatar.url)

        ACTIVE_EMBEDS[self.autor.id] = {
            "embed": embed.to_dict(),
            "buttons": [],
            "canal_id": self.canal.id,
            "timestamp": time.time()
        }

        view = EmbedBuilderView(self.autor)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)



# ======================= VIEW BUILDER ========================


class EmbedBuilderView(discord.ui.View):
    def __init__(self, autor: discord.Member):
        super().__init__(timeout=None)
        self.autor = autor

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.autor.id

    @discord.ui.button(label="🖼 Imagem", style=discord.ButtonStyle.primary)
    async def image(self, interaction: discord.Interaction, _):
        await interaction.response.send_modal(ImageModal(interaction.user, "Imagem", "image"))

    @discord.ui.button(label="🧩 Thumbnail", style=discord.ButtonStyle.primary)
    async def thumb(self, interaction: discord.Interaction, _):
        await interaction.response.send_modal(ImageModal(interaction.user, "Thumbnail", "thumbnail"))

    @discord.ui.button(label="🔗 Link", style=discord.ButtonStyle.success)
    async def link(self, interaction: discord.Interaction, _):
        await interaction.response.send_modal(LinkModal(interaction.user))

    @discord.ui.button(label="📍 Canal", style=discord.ButtonStyle.success)
    async def channel(self, interaction: discord.Interaction, _):
        await interaction.response.send_message(
            view=ChannelSelectView(interaction.user, interaction.guild),
            ephemeral=True
        )

    @discord.ui.button(label="🦶 Footer", style=discord.ButtonStyle.secondary)
    async def footer(self, interaction: discord.Interaction, _):
        await interaction.response.send_modal(FooterModal(interaction.user))

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _):
        user_id = interaction.user.id
        if user_id in ACTIVE_EMBEDS:
            del ACTIVE_EMBEDS[user_id]
        await interaction.response.edit_message(content="🚫 Edição cancelada.", embed=None, view=None)

    @discord.ui.button(label="✅ Enviar", style=discord.ButtonStyle.danger)
    async def send(self, interaction: discord.Interaction, _):
        data = ACTIVE_EMBEDS.get(interaction.user.id)
        if not data:
            return await interaction.response.send_message("❌ Nenhum embed ativo.", ephemeral=True)

        embed = discord.Embed.from_dict(data["embed"])
        view = discord.ui.View()
        for b in data["buttons"]:
            view.add_item(b)

        canal = interaction.guild.get_channel(data["canal_id"])
        await canal.send(embed=embed, view=view)

        del ACTIVE_EMBEDS[interaction.user.id]
        await interaction.response.edit_message(content="✅ Embed enviado com sucesso!", embed=None, view=None)



# ======================== MODAIS =============================


class ImageModal(discord.ui.Modal):
    def __init__(self, user: discord.Member, tipo: str, target: str):
        super().__init__(title=f"📤 Adicionar {tipo}")
        self.user = user
        self.target = target
        self.url = discord.ui.TextInput(label=f"URL da {tipo}", required=True)
        self.add_item(self.url)

    async def on_submit(self, interaction: discord.Interaction):
        data = ACTIVE_EMBEDS.get(interaction.user.id)
        if not data: return
        embed = discord.Embed.from_dict(data["embed"])
        url = self.url.value.strip()
        if self.target == "image": embed.set_image(url=url)
        else: embed.set_thumbnail(url=url)
        ACTIVE_EMBEDS[interaction.user.id]["embed"] = embed.to_dict()
        await interaction.response.edit_message(embed=embed, view=EmbedBuilderView(interaction.user))


class FooterModal(discord.ui.Modal, title="🦶 Editar Footer"):
    def __init__(self, user: discord.Member):
        super().__init__()
        self.user = user
        self.text = discord.ui.TextInput(label="Texto", required=False)
        self.icon = discord.ui.TextInput(label="Ícone (URL)", required=False)
        self.add_item(self.text)
        self.add_item(self.icon)

    async def on_submit(self, interaction: discord.Interaction):
        data = ACTIVE_EMBEDS.get(interaction.user.id)
        if not data: return
        embed = discord.Embed.from_dict(data["embed"])
        embed.set_footer(text=self.text.value or "", icon_url=self.icon.value or None)
        ACTIVE_EMBEDS[interaction.user.id]["embed"] = embed.to_dict()
        await interaction.response.edit_message(embed=embed, view=EmbedBuilderView(interaction.user))


class LinkModal(discord.ui.Modal, title="🔗 Adicionar Link"):
    def __init__(self, user: discord.Member):
        super().__init__()
        self.user = user
        self.label = discord.ui.TextInput(label="Texto do botão", required=True)
        self.url = discord.ui.TextInput(label="URL", required=True)
        self.add_item(self.label)
        self.add_item(self.url)

    async def on_submit(self, interaction: discord.Interaction):
        data = ACTIVE_EMBEDS.get(interaction.user.id)
        if not data: return
        btn = discord.ui.Button(label=self.label.value.strip(), url=self.url.value.strip())
        data["buttons"].append(btn)
        ACTIVE_EMBEDS[interaction.user.id]["timestamp"] = time.time()
        await interaction.response.edit_message(embed=discord.Embed.from_dict(data["embed"]), view=EmbedBuilderView(interaction.user))



# ===================== SELETOR DE CANAL ======================

class ChannelSelect(discord.ui.Select):
    def __init__(self, user: discord.Member, guild: discord.Guild):
        options = [discord.SelectOption(label=c.name, value=str(c.id)) for c in guild.text_channels]
        super().__init__(placeholder="Selecione um canal...", options=options, min_values=1, max_values=1)
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        data = ACTIVE_EMBEDS.get(interaction.user.id)
        if not data: return
        canal_id = int(self.values[0])
        canal = interaction.guild.get_channel(canal_id)
        btn = discord.ui.Button(label=f"#{canal.name}", style=discord.ButtonStyle.link,
                                url=f"https://discord.com/channels/{canal.guild.id}/{canal.id}")
        data["buttons"].append(btn)
        ACTIVE_EMBEDS[interaction.user.id]["timestamp"] = time.time()
        await interaction.response.edit_message(embed=discord.Embed.from_dict(data["embed"]), view=EmbedBuilderView(interaction.user))


class ChannelSelectView(discord.ui.View):
    def __init__(self, user: discord.Member, guild: discord.Guild):
        super().__init__(timeout=60)
        self.add_item(ChannelSelect(user, guild))


async def setup(bot):
    await bot.add_cog(EmbedBuilder(bot))
