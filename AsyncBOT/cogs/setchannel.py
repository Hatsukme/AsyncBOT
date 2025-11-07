import discord
from discord.ext import commands
from discord import app_commands

from utils.channels import load_channels, save_channels


class SetChannel(commands.GroupCog, group_name="setchannel"):
	def __init__(self, bot):
		self.bot = bot

	def check_perm(self, interaction):
		core = self.bot.get_cog("Core")
		return core and core.check_admin(interaction.user.id)

	async def tipo_autocomplete(self, interaction: discord.Interaction, current: str):
		data = load_channels()
		tipos = data.get("types", [])

		return [
			app_commands.Choice(name=t, value=t)
			for t in tipos
			if current.lower() in t.lower()
		][:25]

	async def canal_autocomplete(self, interaction, current: str):
		data = load_channels()
		tipo = interaction.namespace.tipo
		guild = interaction.guild
	
		# estamos no comando ADD → queremos CRIAR canal base → mostrar CATEGORIAS
		if interaction.command.name == "add" and tipo.startswith("voice_"):
			return [
				app_commands.Choice(name=f"📂 {c.name}", value=str(c.id))
				for c in guild.categories
				if current.lower() in c.name.lower()
			][:25]
	
		# estamos no comando EDIT/RMV para voz → mostrar canais-base existentes
		if tipo.startswith("voice_"):
			ids = data.get("voice_templates", {}).get(tipo, [])
			canais = []
			for cid in ids:
				ch = guild.get_channel(cid)
				if ch:
					canais.append(ch)
			return [
				app_commands.Choice(name=f"🎙️ {c.name}", value=str(c.id))
				for c in canais if current.lower() in c.name.lower()
			][:25]
	
		# fallback para tipos normais → canais de texto
		return [
			app_commands.Choice(name=f"#{c.name}", value=str(c.id))
			for c in guild.text_channels
			if current.lower() in c.name.lower()
		][:25]
	
	

	@app_commands.command(name="add", description="Adiciona um canal ou template de voz.")
	@app_commands.autocomplete(tipo=tipo_autocomplete, canal=canal_autocomplete)
	async def add(self, interaction, tipo: str, canal: str):

		if not self.check_perm(interaction):
			core = self.bot.get_cog("Core")
			return await core.deny(interaction)

		data = load_channels()

		# ✅ Converte ID em objeto de canal real
		canal = interaction.guild.get_channel(int(canal))

		# Se for VOZ → criamos canal base e adicionamos à lista
		if tipo.startswith("voice_"):
		
			if not isinstance(canal, discord.CategoryChannel):
				return await interaction.response.send_message(
					"⚠️ Este tipo requer que você selecione **uma categoria**.",
					ephemeral=True
				)

			nomes = {
				"voice_duo": "➕ Criar Duo",
				"voice_esquadrao": "➕ Criar Esquadrão",
				"voice_geral": "➕ Criar Geral"
			}

			nome_canal = nomes.get(tipo, "➕ Criar Sala")
			base_channel = await canal.create_voice_channel(name=nome_canal)

			data.setdefault("voice_templates", {})
			data["voice_templates"].setdefault(tipo, [])
			data["voice_templates"][tipo].append(base_channel.id)


		# Se NÃO for voz → é canal normal de texto
		else:
			if not isinstance(canal, discord.TextChannel):
				return await interaction.response.send_message(
					"⚠️ Este tipo requer um **canal de texto**, não uma categoria.",
					ephemeral=True
				)
			data[tipo] = canal.id

		save_channels(data)

		await interaction.response.send_message(
			f"✅ `{tipo}` configurado como → {canal.mention}",
			ephemeral=True
		)

	@app_commands.command(name="edit", description="Edita um item já configurado no channels.json.")
	@app_commands.autocomplete(tipo=tipo_autocomplete, canal=canal_autocomplete)
	async def edit(self, interaction: discord.Interaction, tipo: str, canal: str):

		if not self.check_perm(interaction):
			core = self.bot.get_cog("Core")
			return await core.deny(interaction)

		data = load_channels()
		canal = interaction.guild.get_channel(int(canal))

		if tipo.startswith("voice_"):
			# Atualiza o canal-base diretamente no JSON
			data.setdefault("voice_templates", {})
			data["voice_templates"][tipo] = canal.id

		else:
			data[tipo] = canal.id

		save_channels(data)

		await interaction.response.send_message(
			f"✏️ `{tipo}` agora está configurado como → {canal.mention}",
			ephemeral=True
		)

	@app_commands.command(name="rmv", description="Remove um canal-base de voz específico.")
	@app_commands.autocomplete(tipo=tipo_autocomplete, canal=canal_autocomplete)
	async def rmv(self, interaction: discord.Interaction, tipo: str, canal: str):

		if not self.check_perm(interaction):
			core = self.bot.get_cog("Core")
			return await core.deny(interaction)

		canal_id = int(canal)
		data = load_channels()

		if tipo.startswith("voice_"):
			lista = data["voice_templates"].get(tipo, [])

			if canal_id in lista:
				lista.remove(canal_id)

				ch = interaction.guild.get_channel(canal_id)
				if ch:
					await ch.delete()

				save_channels(data)
				return await interaction.response.send_message(
					f"🗑️ Canal-base removido e apagado.",
					ephemeral=True
				)

		await interaction.response.send_message(
			"⚠️ Não encontrei esse canal na configuração.",
			ephemeral=True
		)



async def setup(bot):
	await bot.add_cog(SetChannel(bot))
