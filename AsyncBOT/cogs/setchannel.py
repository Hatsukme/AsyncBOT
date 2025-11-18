import discord
from discord.ext import commands
from discord import app_commands

from utils.channels import load_channels, save_channels


class SetChannel(
    commands.GroupCog,
    group_name="setchannel",
    group_description="Configura canais de texto como welcome, logs e outros."
):

    """
    Versão limpa do comando setchannel.
    Agora serve APENAS para configurar canais de TEXTO,
    como welcome / logs / warnings.
    """

    def __init__(self, bot):
        self.bot = bot

    # ======================================
    #           PERMISSÃO
    # ======================================
    def check_perm(self, interaction: discord.Interaction) -> bool:
        core = self.bot.get_cog("Core")
        return core and core.check_admin(interaction.user.id)

    async def deny(self, interaction: discord.Interaction):
        core = self.bot.get_cog("Core")
        if core:
            return await core.deny(interaction)

        return await interaction.response.send_message(
            "Você não tem permissão para usar este comando.",
            ephemeral=True
        )

    # ======================================
    #           AUTOCOMPLETE
    # ======================================
    async def tipo_autocomplete(self, interaction: discord.Interaction, current: str):
        data = load_channels()
        tipos = data.get("types", [])

        # filtra APENAS tipos que NÃO são voice_
        tipos_filtrados = [t for t in tipos if not t.startswith("voice_")]

        return [
            app_commands.Choice(name=t, value=t)
            for t in tipos_filtrados
            if current.lower() in t.lower()
        ][:25]

    async def canal_autocomplete(self, interaction: discord.Interaction, current: str):
        guild = interaction.guild

        # lista apenas canais de texto
        return [
            app_commands.Choice(name=f"#{c.name}", value=str(c.id))
            for c in guild.text_channels
            if current.lower() in c.name.lower()
        ][:25]

    # ======================================
    #              ADD
    # ======================================
    @app_commands.command(name="add", description="Configura um canal de texto (ex: welcome).")
    @app_commands.autocomplete(tipo=tipo_autocomplete, canal=canal_autocomplete)
    async def add(self, interaction: discord.Interaction, tipo: str, canal: str):

        if not self.check_perm(interaction):
            return await self.deny(interaction)

        guild = interaction.guild
        data = load_channels()

        ch = guild.get_channel(int(canal))

        if not isinstance(ch, discord.TextChannel):
            return await interaction.response.send_message(
                "⚠️ Este comando só aceita **canais de texto**.",
                ephemeral=True
            )

        data[tipo] = ch.id
        save_channels(data)

        await interaction.response.send_message(
            f"✅ `{tipo}` configurado como → {ch.mention}",
            ephemeral=True
        )

    # ======================================
    #              EDIT
    # ======================================
    @app_commands.command(name="edit", description="Edita um canal de texto já configurado.")
    @app_commands.autocomplete(tipo=tipo_autocomplete, canal=canal_autocomplete)
    async def edit(self, interaction: discord.Interaction, tipo: str, canal: str):

        if not self.check_perm(interaction):
            return await self.deny(interaction)

        guild = interaction.guild
        data = load_channels()

        ch = guild.get_channel(int(canal))

        if not isinstance(ch, discord.TextChannel):
            return await interaction.response.send_message(
                "⚠️ Este comando só aceita **canais de texto**.",
                ephemeral=True
            )

        data[tipo] = ch.id
        save_channels(data)

        await interaction.response.send_message(
            f"✏️ `{tipo}` atualizado para → {ch.mention}",
            ephemeral=True
        )

    # ======================================
    #            REMOVE
    # ======================================
    @app_commands.command(name="rmv", description="Remove um canal de texto configurado.")
    @app_commands.autocomplete(tipo=tipo_autocomplete)
    async def rmv(self, interaction: discord.Interaction, tipo: str):

        if not self.check_perm(interaction):
            return await self.deny(interaction)

        data = load_channels()

        if tipo not in data:
            return await interaction.response.send_message(
                "⚠️ Este tipo não está configurado.",
                ephemeral=True
            )

        data.pop(tipo)
        save_channels(data)

        await interaction.response.send_message(
            f"🗑️ `{tipo}` removido da configuração.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(SetChannel(bot))
