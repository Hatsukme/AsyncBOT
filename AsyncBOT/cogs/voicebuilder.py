import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, Dict

from utils.channels import load_channels, save_channels


# =========================================================
#   Sessão custom individual
# =========================================================
class CustomSession:
	def __init__(self, user: discord.abc.User, category: discord.CategoryChannel, text_channel: discord.TextChannel):
		self.user_id: int = user.id
		self.guild_id: int = category.guild.id
		self.category_id: int = category.id
		self.text_channel_id: int = text_channel.id
		self.voice_channel_id: Optional[int] = None

		self.name_template: str = f"Sala de {user.display_name}"
		self.slots: int = 0
		self.locked: bool = False

		# NOVO: lista de convidados
		self.invited: set[int] = set()


# =========================================================
#   COG PRINCIPAL
# =========================================================
class VoiceBuilder(commands.Cog):
	"""Painel para criar canais-base e sessões custom."""
	def __init__(self, bot: commands.Bot):
		self.bot = bot
		# Sessões abertas (user_id → session)
		self.custom_sessions: Dict[int, CustomSession] = {}

	# -----------------------------------------
	# PERMISSÕES
	# -----------------------------------------
	def check_perm(self, interaction: discord.Interaction) -> bool:
		core = self.bot.get_cog("Core")
		return core and core.check_admin(interaction.user.id)

	async def deny(self, interaction: discord.Interaction):
		core = self.bot.get_cog("Core")
		if core and hasattr(core, "deny"):
			return await core.deny(interaction)
		return await interaction.response.send_message("Sem permissão.", ephemeral=True)

	# -----------------------------------------
	# COMANDO PRINCIPAL
	# -----------------------------------------
	@app_commands.command(name="voicebuilder", description="Painel de gerenciamento de canais de voz.")
	async def voicebuilder(self, interaction: discord.Interaction):
		if not self.check_perm(interaction):
			return await self.deny(interaction)

		if not interaction.guild:
			return await interaction.response.send_message("Use no servidor.", ephemeral=True)

		view = VoiceBuilderMainView(self, interaction)
		embed = view.build_embed()

		await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

	# =====================================================
	#   PADRÃO — cria canal-base que gera temporários
	# =====================================================
	async def create_standard_template(
		self,
		interaction: discord.Interaction,
		category: discord.CategoryChannel,
		base_name: str,
		temp_name: str,
		slots: int,
		locked: bool,
	):
		guild = interaction.guild
		base_channel = await category.create_voice_channel(
			name=base_name,
			user_limit=0,
		)

		data = load_channels()
		base_cfg = data.setdefault("voice_base_configs", {})

		base_cfg[str(base_channel.id)] = {
			"category": category.id,
			"temp_name": temp_name,
			"slots": max(0, slots),
			"locked": bool(locked),
		}

		save_channels(data)

		await interaction.response.send_message(
			f"Canal-base criado: {base_channel.mention}",
			ephemeral=True,
		)

	# =====================================================
	#   CUSTOM — cria canal-base custom por categoria
	# =====================================================
	async def create_custom_base(self, interaction, category, base_name):
		guild = interaction.guild

		data = load_channels()
		custom_bases = data.setdefault("voice_custom_base", {})

		# não permitir mais de um canal custom por categoria
		if str(category.id) in custom_bases:
			return await interaction.response.send_message(
				"Esta categoria já possui um canal-base custom.",
				ephemeral=True,
			)

		base_channel = await category.create_voice_channel(
			name=base_name,
			user_limit=0,
		)

		custom_bases[str(category.id)] = {
			"base_id": base_channel.id,
			"category": category.id,
		}

		save_channels(data)

		await interaction.response.send_message(
			f"Canal-base custom criado: {base_channel.mention}",
			ephemeral=True,
		)

	# =====================================================
	#   DELETAR CANAL-BASE (padrão ou custom)
	# =====================================================
	async def delete_base_channel(self, interaction, category, base_id: int):
		data = load_channels()
		base_cfg = data.get("voice_base_configs", {})
		custom_cfg = data.get("voice_custom_base", {})

		# PADRÃO
		if str(base_id) in base_cfg:
			ch = interaction.guild.get_channel(base_id)
			if ch:
				try:
					await ch.delete()
				except Exception:
					pass

			base_cfg.pop(str(base_id), None)
			save_channels(data)

			return await interaction.response.send_message(
				f"Canal-base padrão `{base_id}` deletado.",
				ephemeral=True,
			)

		# CUSTOM
		for cat_id, info in list(custom_cfg.items()):
			if info.get("base_id") == base_id:
				ch = interaction.guild.get_channel(base_id)
				if ch:
					try:
						await ch.delete()
					except Exception:
						pass

				custom_cfg.pop(cat_id, None)
				save_channels(data)

				return await interaction.response.send_message(
					f"Canal-base custom `{base_id}` deletado.",
					ephemeral=True,
				)

		return await interaction.response.send_message(
			"Esse ID não corresponde a nenhum canal-base registrado.",
			ephemeral=True,
		)

	# =====================================================
	#   Quando o usuário entrar no canal-base custom
	# =====================================================
	async def start_custom_session(self, member: discord.Member, category: discord.CategoryChannel):
		guild = member.guild

		# se já tem sessão, encerra antes
		old = self.custom_sessions.pop(member.id, None)
		if old:
			await self.end_custom_session(old, reason="Iniciando nova sessão custom.")

		# canal de texto privado + somente leitura pro dono
		overwrites = {
			guild.default_role: discord.PermissionOverwrite(view_channel=False),
			guild.me: discord.PermissionOverwrite(
				view_channel=True,
				send_messages=True,
				read_message_history=True,
			),
			member: discord.PermissionOverwrite(
				view_channel=True,
				send_messages=False,          # não pode digitar
				read_message_history=True,
			),
		}

		text_channel = await guild.create_text_channel(
			name=f"config-voz-{member.name}".replace(" ", "-").lower(),
			category=category,
			overwrites=overwrites,
		)

		session = CustomSession(member, category, text_channel)
		self.custom_sessions[member.id] = session

		view = CustomPanelView(self, session)
		embed = self.build_custom_dashboard(member, session)

		await text_channel.send(
			content=member.mention,
			embed=embed,
			view=view,
		)

	def build_custom_dashboard(self, member: discord.Member, session: CustomSession) -> discord.Embed:
		embed = discord.Embed(
			title="🎧 Sala Custom",
			description="Painel de controle da sua sala personalizada.",
			color=discord.Color.blurple(),
		)
		embed.add_field(name="👤 Dono", value=member.mention, inline=True)
		embed.add_field(name="🔒 Status", value="Trancada" if session.locked else "Aberta", inline=True)
		embed.add_field(name="👥 Slots", value=str(session.slots or "Ilimitado"), inline=True)
		embed.add_field(
			name="📝 Nome da sala",
			value=session.name_template or "Sala de {user}",
			inline=False,
		)
		embed.set_footer(text="Use os botões abaixo para configurar, convidar e gerenciar sua sala.")
		return embed

	# =====================================================
	#   Criação/Atualização da sala custom
	# =====================================================
	async def apply_custom_config(
		self,
		interaction: discord.Interaction,
		session: CustomSession,
		name_template: Optional[str],
		slots: Optional[int],
		locked: Optional[bool],
	):
		guild = interaction.guild
		member = guild.get_member(session.user_id)
		category = guild.get_channel(session.category_id)

		if name_template:
			session.name_template = name_template

		if slots is not None:
			try:
				session.slots = max(0, int(slots))
			except Exception:
				session.slots = 0

		if locked is not None:
			session.locked = locked

		# nome final
		display_name = member.display_name if member else "Usuário"
		voice_name = session.name_template.replace("{user}", display_name)

		# permissões se trancada
		overwrites = None
		#if session.locked:
			#overwrites = {
				#guild.default_role: discord.PermissionOverwrite(
					#view_channel=False,
					#connect=False,
				#),
			#}
		if session.locked:
			overwrites = {
				guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
				member: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True),
				guild.me: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, move_members=True),
			}
		else:
			# sala aberta → deixa o discord usar as permissões da categoria
			overwrites = {}
		

			if member:
				overwrites[member] = discord.PermissionOverwrite(
					view_channel=True,
					connect=True,
					speak=True,
				)
			overwrites[guild.me] = discord.PermissionOverwrite(
				view_channel=True,
				connect=True,
				speak=True,
				move_members=True,
			)

		voice_channel: Optional[discord.VoiceChannel] = None

		if session.voice_channel_id:
			ch = guild.get_channel(session.voice_channel_id)
			if isinstance(ch, discord.VoiceChannel):
				voice_channel = ch
				try:
					if overwrites is None:
						overwrites = {}

					await voice_channel.edit(
						name=voice_name,
						user_limit=session.slots or 0,
						overwrites=overwrites,
					)
				except Exception:
					pass
			else:
				session.voice_channel_id = None
		
		if overwrites is None:
			overwrites = {}

		if not session.voice_channel_id:
			voice_channel = await category.create_voice_channel(
				name=voice_name,
				user_limit=session.slots or 0,
				overwrites=overwrites,
			)
			session.voice_channel_id = voice_channel.id

		# mover usuário
		if member and voice_channel:
			try:
				await member.move_to(voice_channel)
			except Exception:
				pass

		await interaction.response.send_message("Sala custom criada/atualizada.", ephemeral=True)

	# =====================================================
	#   Invites (Custom) — AGORA SEM MODAL, USADO PELO PAINEL
	# =====================================================
	async def invite_to_custom(self, interaction: discord.Interaction, session: CustomSession, target: discord.Member):
		guild = interaction.guild
		voice = guild.get_channel(session.voice_channel_id) if session.voice_channel_id else None
		text = guild.get_channel(session.text_channel_id)

		if not isinstance(voice, discord.VoiceChannel):
			# nada de response aqui, quem responde é o painel
			return

		await voice.set_permissions(
			target,
			view_channel=True,
			connect=True,
			speak=True,
		)

		if isinstance(text, discord.TextChannel):
			await text.set_permissions(
				target,
				view_channel=True,
				send_messages=False,
				read_message_history=True,
			)

		session.invited.add(target.id)

	# =====================================================
	#   Encerrar sessão custom
	# =====================================================
	async def end_custom_session(self, session: CustomSession, reason: str = ""):
		guild = self.bot.get_guild(session.guild_id)
		if guild is None:
			self.custom_sessions.pop(session.user_id, None)
			return

		text_ch = guild.get_channel(session.text_channel_id)
		if isinstance(text_ch, discord.TextChannel):
			try:
				await text_ch.delete(reason=reason or "Encerrando painel custom.")
			except discord.HTTPException:
				pass

		if session.voice_channel_id:
			voice_ch = guild.get_channel(session.voice_channel_id)
			if isinstance(voice_ch, discord.VoiceChannel):
				try:
					await voice_ch.delete(reason=reason or "Encerrando sala custom.")
				except discord.HTTPException:
					pass

		self.custom_sessions.pop(session.user_id, None)

	# =====================================================
	#   Listener: entrar em base custom + encerrar quando sala vazia
	# =====================================================
	@commands.Cog.listener()
	async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
		# 1) Entrou em algum canal?
		if after.channel:
			data = load_channels()
			custom_bases = data.get("voice_custom_base", {})

			for cat_id, info in custom_bases.items():
				if after.channel.id == info.get("base_id"):
					category = member.guild.get_channel(int(cat_id))
					if isinstance(category, discord.CategoryChannel):
						await self.start_custom_session(member, category)
					break

		# 2) Saiu de uma sala custom? Se esvaziou, encerra sessão (apaga voz + texto)
		if before.channel:
			# achar sessão ligada a esse canal de voz
			target_session = None
			for session in list(self.custom_sessions.values()):
				if session.voice_channel_id == before.channel.id:
					target_session = session
					break

			if target_session and len(before.channel.members) == 0:
				await self.end_custom_session(target_session, reason="Sala custom vazia.")


# =========================================================
#   VIEW PRINCIPAL
# =========================================================
class VoiceBuilderMainView(discord.ui.View):
	def __init__(self, cog: VoiceBuilder, interaction: discord.Interaction):
		super().__init__(timeout=300)
		self.cog = cog
		self.owner_id = interaction.user.id
		self.guild = interaction.guild

		self.selected_category: Optional[discord.CategoryChannel] = None
		self.selected_module: Optional[str] = None  # "padrao" ou "custom"

		self.add_item(CategorySelect(self))
		self.add_item(ModuleSelect(self))

	async def _check_user(self, interaction):
		if interaction.user.id != self.owner_id:
			await interaction.response.send_message("Este painel não é seu.", ephemeral=True)
			return False
		return True

	def build_embed(self):
		cat_name = self.selected_category.name if self.selected_category else "—"
		mod_label = {
			"custom": "Custom (salas privadas por usuário)",
			"padrao": "Padrão (templates de temporárias)",
		}.get(self.selected_module, "—")

		embed = discord.Embed(
			title="Voice Builder",
			description="Configuração de canais-base e sistemas personalizados.",
			color=discord.Color.blurple(),
		)

		embed.add_field(name="Categoria selecionada:", value=cat_name, inline=False)
		embed.add_field(name="Módulo:", value=mod_label, inline=False)
		embed.add_field(
			name="Informações:",
			value="Após clicar em **CRIAR**, um modal abrirá com as opções.\n"
				  "Use **DELETAR** para remover um canal-base já existente.",
			inline=False,
		)

		return embed

	async def refresh(self, interaction):
		await interaction.response.edit_message(embed=self.build_embed(), view=self)

	# -----------------------------------------
	# CRIAR
	# -----------------------------------------
	@discord.ui.button(label="CRIAR", style=discord.ButtonStyle.success, row=2)
	async def btn_criar(self, interaction, button):
		if not await self._check_user(interaction):
			return

		if not self.selected_category or not self.selected_module:
			return await interaction.response.send_message("Selecione categoria e módulo.", ephemeral=True)

		if self.selected_module == "padrao":
			modal = StandardConfigModal(self.cog, self.selected_category)
		else:
			modal = CustomBaseModal(self.cog, self.selected_category)

		await interaction.response.send_modal(modal)

	# -----------------------------------------
	# DELETAR
	# -----------------------------------------
	@discord.ui.button(label="DELETAR", style=discord.ButtonStyle.danger, row=2)
	async def btn_deletar(self, interaction, button):
		if not await self._check_user(interaction):
			return

		if not self.selected_category:
			return await interaction.response.send_message("Selecione uma categoria.", ephemeral=True)

		modal = DeleteBaseModal(self.cog, self.selected_category)
		await interaction.response.send_modal(modal)

	# -----------------------------------------
	# CANCELAR
	# -----------------------------------------
	@discord.ui.button(label="CANCELAR", style=discord.ButtonStyle.secondary, row=2)
	async def btn_cancelar(self, interaction, button):
		await interaction.response.edit_message(
			content="Operação cancelada.",
			embed=None,
			view=None,
		)


# =========================================================
#   SELECT DE CATEGORIA / MÓDULO
# =========================================================
class CategorySelect(discord.ui.Select):
	def __init__(self, parent_view: VoiceBuilderMainView):
		self.parent_view = parent_view
		guild = parent_view.guild

		options = [discord.SelectOption(label="🆕 Criar nova categoria", value="new")]
		options += [
			discord.SelectOption(label=c.name, value=str(c.id))
			for c in guild.categories
		]

		super().__init__(
			placeholder="Selecione a categoria",
			min_values=1,
			max_values=1,
			options=options,
		)

	async def callback(self, interaction):
		if not await self.parent_view._check_user(interaction):
			return

		value = self.values[0]

		if value == "new":
			modal = CreateCategoryModal(self.parent_view)
			return await interaction.response.send_modal(modal)

		ch = self.parent_view.guild.get_channel(int(value))
		if isinstance(ch, discord.CategoryChannel):
			self.parent_view.selected_category = ch

		await self.parent_view.refresh(interaction)


class ModuleSelect(discord.ui.Select):
	def __init__(self, parent_view: VoiceBuilderMainView):
		self.parent_view = parent_view
		options = [
			discord.SelectOption(label="Padrão", value="padrao"),
			discord.SelectOption(label="Custom", value="custom"),
		]
		super().__init__(
			placeholder="Selecione o módulo",
			min_values=1,
			max_values=1,
			options=options,
		)

	async def callback(self, interaction):
		if not await self.parent_view._check_user(interaction):
			return

		self.parent_view.selected_module = self.values[0]
		await self.parent_view.refresh(interaction)


# =========================================================
#   MODALS
# =========================================================
class CreateCategoryModal(discord.ui.Modal, title="Criar nova categoria"):
	def __init__(self, parent_view: VoiceBuilderMainView):
		super().__init__()
		self.parent_view = parent_view

		self.name = discord.ui.TextInput(
			label="Nome da categoria",
			placeholder="Ex: Salas de Voz",
		)
		self.add_item(self.name)

	async def on_submit(self, interaction: discord.Interaction):
		guild = interaction.guild
		new_cat = await guild.create_category(self.name.value.strip() or "Nova Categoria")

		self.parent_view.selected_category = new_cat
		await interaction.response.send_message(
			f"Categoria criada: {new_cat.mention}",
			ephemeral=True,
		)


class StandardConfigModal(discord.ui.Modal, title="Canal-base padrão"):
	def __init__(self, cog: VoiceBuilder, category: discord.CategoryChannel):
		super().__init__()
		self.cog = cog
		self.category = category

		self.base_name = discord.ui.TextInput(label="Nome do canal-base")
		self.temp_name = discord.ui.TextInput(
			label="Nome do canal temporário",
			placeholder="Use {user} para o nome do usuário.",
		)
		self.slots = discord.ui.TextInput(label="Slots (0 = ilimitado)", required=False)
		self.locked = discord.ui.TextInput(label="Trancado? (sim/nao)", required=False)

		self.add_item(self.base_name)
		self.add_item(self.temp_name)
		self.add_item(self.slots)
		self.add_item(self.locked)

	async def on_submit(self, interaction: discord.Interaction):
		try:
			slots = int(self.slots.value) if self.slots.value else 0
		except ValueError:
			slots = 0

		locked = (self.locked.value or "nao").strip().lower() in ("sim", "s", "yes", "y", "true", "1")

		await self.cog.create_standard_template(
			interaction=interaction,
			category=self.category,
			base_name=self.base_name.value.strip() or "➕ Criar sala",
			temp_name=self.temp_name.value.strip() or "🎤 Sala de {user}",
			slots=slots,
			locked=locked,
		)


class CustomBaseModal(discord.ui.Modal, title="Criar canal-base Custom"):
	def __init__(self, cog: VoiceBuilder, category: discord.CategoryChannel):
		super().__init__()
		self.cog = cog
		self.category = category

		self.base_name = discord.ui.TextInput(label="Nome do canal-base custom")
		self.add_item(self.base_name)

	async def on_submit(self, interaction: discord.Interaction):
		await self.cog.create_custom_base(
			interaction,
			self.category,
			self.base_name.value.strip() or "Custom",
		)


class DeleteBaseModal(discord.ui.Modal, title="Deletar Canal-Base"):
	def __init__(self, cog: VoiceBuilder, category: discord.CategoryChannel):
		super().__init__()
		self.cog = cog
		self.category = category

		self.channel_id = discord.ui.TextInput(
			label="ID do canal-base",
			placeholder="Cole o ID do canal-base",
		)
		self.add_item(self.channel_id)

	async def on_submit(self, interaction: discord.Interaction):
		try:
			base_id = int(self.channel_id.value.strip())
		except ValueError:
			return await interaction.response.send_message("ID inválido.", ephemeral=True)

		await self.cog.delete_base_channel(interaction, self.category, base_id)


class CustomConfigModal(discord.ui.Modal, title="Configurar sala custom"):
	def __init__(self, cog: VoiceBuilder, session: CustomSession):
		super().__init__()
		self.cog = cog
		self.session = session

		self.name = discord.ui.TextInput(
			label="Nome da sala",
			placeholder="Use {user} para o nome do usuário. Ex: 🎮 Sala de {user}",
			required=False,
			default=self.session.name_template,
		)
		self.slots = discord.ui.TextInput(
			label="Número de slots (0 = ilimitado)",
			required=False,
			placeholder=str(self.session.slots or 0),
		)
		self.locked = discord.ui.TextInput(
			label="Trancada? (sim/nao)",
			required=False,
			placeholder="sim" if self.session.locked else "nao",
		)

		self.add_item(self.name)
		self.add_item(self.slots)
		self.add_item(self.locked)

	async def on_submit(self, interaction: discord.Interaction):
		name_template = self.name.value.strip() or None

		slots: Optional[int] = None
		if self.slots.value:
			try:
				slots = int(self.slots.value)
			except ValueError:
				slots = 0

		locked: Optional[bool] = None
		if self.locked.value:
			locked_str = self.locked.value.strip().lower()
			locked = locked_str in ("sim", "s", "yes", "y", "true", "1")

		await self.cog.apply_custom_config(
			interaction,
			self.session,
			name_template=name_template,
			slots=slots,
			locked=locked,
		)


# =========================================================
#   PAINEL CUSTOM (convites, travar, encerrar)
# =========================================================
class CustomPanelView(discord.ui.View):
	def __init__(self, cog: VoiceBuilder, session: CustomSession):
		super().__init__(timeout=None)
		self.cog = cog
		self.session = session

		# NOVO: select multi de usuários
		self.add_item(CustomInviteMultiSelect(self))

	async def _check_user(self, interaction: discord.Interaction) -> bool:
		if interaction.user.id != self.session.user_id:
			await interaction.response.send_message("Este painel não é seu.", ephemeral=True)
			return False
		return True

	async def invite_members(self, interaction: discord.Interaction, members: list[discord.Member]):
		"""Convida múltiplos membros (aplica permissões) sem enviar resposta aqui."""
		guild = interaction.guild
		if not guild:
			return

		for m in members:
			await self.cog.invite_to_custom(interaction, self.session, m)

	@discord.ui.button(label="Configurar sala", style=discord.ButtonStyle.success, row=1)
	async def btn_config(self, interaction: discord.Interaction, button: discord.ui.Button):
		if not await self._check_user(interaction):
			return

		modal = CustomConfigModal(self.cog, self.session)
		await interaction.response.send_modal(modal)

	@discord.ui.button(label="Gerenciar convidados", style=discord.ButtonStyle.secondary, row=1)
	async def btn_manage_guests(self, interaction: discord.Interaction, button: discord.ui.Button):
		if not await self._check_user(interaction):
			return

		guild = interaction.guild
		if not guild:
			return

		voice = guild.get_channel(self.session.voice_channel_id) if self.session.voice_channel_id else None
		if not isinstance(voice, discord.VoiceChannel):
			return await interaction.response.send_message("Sala ainda não foi criada.", ephemeral=True)

		desc = "Nenhum convidado ainda."
		if self.session.invited:
			linhas = []
			for uid in self.session.invited:
				m = guild.get_member(uid)
				if m:
					linhas.append(m.mention)
			if linhas:
				desc = "\n".join(linhas)

		embed = discord.Embed(
			title="🎧 Convidados da sala custom",
			description=desc,
			color=discord.Color.blurple(),
		)
		embed.set_footer(text="Selecione convidados e use os botões para gerenciar.")

		view = CustomGuestManagerView(self.cog, self.session)
		await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

	@discord.ui.button(label="Travar/Destravar sala", style=discord.ButtonStyle.secondary, row=1)
	async def btn_lock(self, interaction: discord.Interaction, button: discord.ui.Button):
		if not await self._check_user(interaction):
			return

		guild = interaction.guild
		voice = guild.get_channel(self.session.voice_channel_id) if self.session.voice_channel_id else None
		if not isinstance(voice, discord.VoiceChannel):
			return await interaction.response.send_message("Sala ainda não criada.", ephemeral=True)

		default_role = guild.default_role
		perms = voice.overwrites_for(default_role)
		locked_now = (not perms.view_channel) or (perms.connect is False)

		if locked_now:
			await voice.set_permissions(default_role, view_channel=True, connect=True)
			self.session.locked = False
			msg = "Sala destravada."
		else:
			await voice.set_permissions(default_role, view_channel=False, connect=False)
			self.session.locked = True
			msg = "Sala travada."

		await interaction.response.send_message(msg, ephemeral=True)

	@discord.ui.button(label="Encerrar sala", style=discord.ButtonStyle.danger, row=1)
	async def btn_close(self, interaction: discord.Interaction, button: discord.ui.Button):
		if not await self._check_user(interaction):
			return

		await interaction.response.send_message("Sala custom encerrada.", ephemeral=True)
		await self.cog.end_custom_session(self.session, reason="Encerrada pelo usuário.")


class CustomInviteMultiSelect(discord.ui.UserSelect):
	def __init__(self, parent_view: CustomPanelView):
		self.parent_view = parent_view
		super().__init__(
			placeholder="Selecionar usuários para convidar…",
			min_values=1,
			max_values=10,
			row=0,
		)

	async def callback(self, interaction: discord.Interaction):
		if not await self.parent_view._check_user(interaction):
			return

		members = [m for m in self.values if isinstance(m, discord.Member)]
		if not members:
			return await interaction.response.send_message("Seleção inválida.", ephemeral=True)

		lista = "\n".join(m.mention for m in members)
		embed = discord.Embed(
			title="👤 Confirmar convite",
			description=f"Usuários selecionados:\n{lista}\n\nDeseja permitir entrada nessa sala?",
			color=discord.Color.blurple(),
		)

		view = CustomConfirmInviteView(self.parent_view, members)
		await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class CustomConfirmInviteView(discord.ui.View):
	def __init__(self, parent_panel: CustomPanelView, members: list[discord.Member]):
		super().__init__(timeout=60)
		self.parent_panel = parent_panel
		self.members = members

	@discord.ui.button(label="SIM", style=discord.ButtonStyle.success)
	async def btn_yes(self, interaction: discord.Interaction, button: discord.ui.Button):
		if not await self.parent_panel._check_user(interaction):
			return

		await self.parent_panel.invite_members(interaction, self.members)
		lista = ", ".join(m.mention for m in self.members)
		await interaction.response.edit_message(
			content=f"✅ Convite enviado para: {lista}",
			embed=None,
			view=None,
		)

	@discord.ui.button(label="NÃO", style=discord.ButtonStyle.danger)
	async def btn_no(self, interaction: discord.Interaction, button: discord.ui.Button):
		if not await self.parent_panel._check_user(interaction):
			return

		await interaction.response.edit_message(
			content="Convite cancelado.",
			embed=None,
			view=None,
		)


class CustomGuestManagerView(discord.ui.View):
	def __init__(self, cog: VoiceBuilder, session: CustomSession):
		super().__init__(timeout=None)
		self.cog = cog
		self.session = session
		self.selected_ids: list[int] = []

		self.add_item(CustomGuestSelect(self))

	async def _check_user(self, interaction: discord.Interaction) -> bool:
		if interaction.user.id != self.session.user_id:
			await interaction.response.send_message(
				"Apenas o dono da sala pode gerenciar os convidados.",
				ephemeral=True,
			)
			return False
		return True

	async def _apply_to_selected(self, interaction: discord.Interaction, action: str):
		if not await self._check_user(interaction):
			return

		guild = interaction.guild
		if not guild:
			return

		voice = guild.get_channel(self.session.voice_channel_id) if self.session.voice_channel_id else None
		if not isinstance(voice, discord.VoiceChannel):
			return await interaction.response.send_message("Sala não criada.", ephemeral=True)

		if not self.selected_ids:
			return await interaction.response.send_message("Nenhum convidado selecionado.", ephemeral=True)

		afetados = []
		for uid in self.selected_ids:
			member = guild.get_member(uid)
			if not member:
				continue

			if action == "mute":
				await member.edit(mute=True)
			elif action == "unmute":
				await member.edit(mute=False)
			elif action == "deaf":
				await member.edit(deafen=True)
			elif action == "undeaf":
				await member.edit(deafen=False)
			elif action == "kick":
				await member.move_to(None)
				ch = guild.get_channel(self.session.voice_channel_id) if self.session.voice_channel_id else None
				if isinstance(ch, discord.VoiceChannel):
					await ch.set_permissions(member, overwrite=None)
				if uid in self.session.invited:
					self.session.invited.remove(uid)

			afetados.append(member.mention)

		if not afetados:
			return await interaction.response.send_message("Nenhum usuário afetado.", ephemeral=True)

		await interaction.response.send_message(
			f"Ação `{action}` aplicada em: {', '.join(afetados)}",
			ephemeral=True,
		)

	@discord.ui.button(label="Mute", style=discord.ButtonStyle.secondary, row=1)
	async def btn_mute(self, interaction: discord.Interaction, button: discord.ui.Button):
		await self._apply_to_selected(interaction, "mute")

	@discord.ui.button(label="Unmute", style=discord.ButtonStyle.secondary, row=1)
	async def btn_unmute(self, interaction: discord.Interaction, button: discord.ui.Button):
		await self._apply_to_selected(interaction, "unmute")

	@discord.ui.button(label="Ensurdecer", style=discord.ButtonStyle.secondary, row=2)
	async def btn_deaf(self, interaction: discord.Interaction, button: discord.ui.Button):
		await self._apply_to_selected(interaction, "deaf")

	@discord.ui.button(label="Desensurdecer", style=discord.ButtonStyle.secondary, row=2)
	async def btn_undeaf(self, interaction: discord.Interaction, button: discord.ui.Button):
		await self._apply_to_selected(interaction, "undeaf")

	@discord.ui.button(label="Expulsar", style=discord.ButtonStyle.danger, row=3)
	async def btn_kick(self, interaction: discord.Interaction, button: discord.ui.Button):
		await self._apply_to_selected(interaction, "kick")


class CustomGuestSelect(discord.ui.Select):
	def __init__(self, parent_view: CustomGuestManagerView):
		self.parent_view = parent_view
		session = parent_view.session
		cog = parent_view.cog
		guild = cog.bot.get_guild(session.guild_id)

		options: list[discord.SelectOption] = []
		if guild and session.invited:
			for uid in session.invited:
				m = guild.get_member(uid)
				if m:
					options.append(discord.SelectOption(label=m.display_name, value=str(m.id)))

		if not options:
			options = [discord.SelectOption(label="Nenhum convidado", value="0")]

		super().__init__(
			placeholder="Selecione convidados…",
			min_values=1,
			max_values=max(1, len(options)),
			options=options,
			row=0,
		)

	async def callback(self, interaction: discord.Interaction):
		if self.values == ["0"]:
			self.parent_view.selected_ids = []
		else:
			self.parent_view.selected_ids = [int(v) for v in self.values]

		await interaction.response.send_message(
			f"{len(self.parent_view.selected_ids)} convidado(s) selecionado(s).",
			ephemeral=True,
		)


async def setup(bot: commands.Bot):
	await bot.add_cog(VoiceBuilder(bot))
