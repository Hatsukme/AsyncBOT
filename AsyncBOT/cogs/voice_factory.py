import discord
from discord.ext import commands
from asyncio import Lock

from utils.channels import load_channels, save_channels


class PrivateRoom:
    def __init__(self, guild_id: int, owner_id: int, voice_id: int, text_id: int):
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.voice_id = voice_id
        self.text_id = text_id

        # NOVO: convidados registrados (IDs)
        self.invited: set[int] = set()


class VoiceFactory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.deleting = Lock()
        # voice_id -> PrivateRoom
        self.private_rooms: dict[int, PrivateRoom] = {}

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return

        data = load_channels()
        base_cfg = data.get("voice_base_configs", {})
        temps = data.setdefault("voice_temporary", [])

        # =========================================================
        # ENTRANDO EM CANAL-BASE PADRÃO
        # =========================================================
        if after.channel:
            cfg = base_cfg.get(str(after.channel.id))
            if cfg:
                await self._create_standard_temp(member, after, cfg, temps, data)

        # =========================================================
        # SAINDO de um canal temporário
        # =========================================================
        data = load_channels()
        temps = data.get("voice_temporary", [])

        if before.channel and before.channel.id in temps:
            if len(before.channel.members) > 0:
                return

            async with self.deleting:
                data = load_channels()
                temps = data.get("voice_temporary", [])

                if before.channel.id in temps and len(before.channel.members) == 0:
                    # deletar canal de voz
                    try:
                        await before.channel.delete()
                    except Exception:
                        pass
                    else:
                        temps.remove(before.channel.id)
                        data["voice_temporary"] = temps
                        save_channels(data)

                    # se for sala privada com painel, deletar o texto também
                    room = self.private_rooms.pop(before.channel.id, None)
                    if room:
                        guild = self.bot.get_guild(room.guild_id)
                        if guild:
                            text_ch = guild.get_channel(room.text_id)
                            if isinstance(text_ch, discord.TextChannel):
                                try:
                                    await text_ch.delete()
                                except Exception:
                                    pass

    # =========================================================
    # Encerrar manualmente uma sala privada (painel)
    # =========================================================
    async def end_private_room(self, room: PrivateRoom, guild: discord.Guild):
        data = load_channels()
        temps = data.get("voice_temporary", [])

        voice = guild.get_channel(room.voice_id)
        text = guild.get_channel(room.text_id)

        # remover dos temporários
        if room.voice_id in temps:
            temps.remove(room.voice_id)
            data["voice_temporary"] = temps
            save_channels(data)

        if isinstance(voice, discord.VoiceChannel):
            try:
                await voice.delete()
            except Exception:
                pass

        if isinstance(text, discord.TextChannel):
            try:
                await text.delete()
            except Exception:
                pass

        self.private_rooms.pop(room.voice_id, None)

    # =========================================================
    # Helper: aplicar permissão de acesso na sala privada
    # =========================================================
    async def grant_private_access(self, guild: discord.Guild, room: PrivateRoom, member: discord.Member):
        voice = guild.get_channel(room.voice_id)
        text = guild.get_channel(room.text_id)

        if not isinstance(voice, discord.VoiceChannel):
            return

        await voice.set_permissions(
            member,
            view_channel=True,
            connect=True,
            speak=True,
        )

        if isinstance(text, discord.TextChannel):
            await text.set_permissions(
                member,
                view_channel=True,
                send_messages=False,
                read_message_history=True,
            )

        room.invited.add(member.id)

    # =========================================================
    # criação de sala temporária padrão
    # =========================================================
    async def _create_standard_temp(self, member, after, cfg, temps, data):
        guild = member.guild
        category = guild.get_channel(cfg.get("category")) or after.channel.category

        template = cfg.get("temp_name") or after.channel.name
        temp_name = template.replace("{user}", member.display_name)

        slots = cfg.get("slots") or 0
        locked = bool(cfg.get("locked"))

        overwrites = None
        if locked:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
                member: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    connect=True,
                    speak=True,
                    move_members=True,
                ),
            }

        kwargs = {
            "name": temp_name,
            "user_limit": slots,
            "category": category,
        }
        if overwrites:
            kwargs["overwrites"] = overwrites

        try:
            new_channel = await guild.create_voice_channel(**kwargs)
        except Exception:
            return

        temps.append(new_channel.id)
        data["voice_temporary"] = temps
        save_channels(data)

        # se for privado (locked), criar painel em canal de texto
        if locked:
            txt_overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                ),
                member: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=False,  # não pode digitar
                    read_message_history=True,
                ),
            }

            text_channel = await guild.create_text_channel(
                name=f"painel-{member.name}".replace(" ", "-").lower(),
                category=category,
                overwrites=txt_overwrites,
            )

            room = PrivateRoom(
                guild_id=guild.id,
                owner_id=member.id,
                voice_id=new_channel.id,
                text_id=text_channel.id,
            )
            self.private_rooms[new_channel.id] = room

            view = PrivateRoomPanelView(self, room)
            embed = self.build_private_dashboard(member, new_channel)

            await text_channel.send(
                content=member.mention,
                embed=embed,
                view=view,
            )

        # mover user
        try:
            await member.move_to(new_channel)
        except Exception:
            pass

    def build_private_dashboard(self, owner: discord.Member, voice: discord.VoiceChannel) -> discord.Embed:
        embed = discord.Embed(
            title="🔒 Sala Privada",
            description="Painel de controle da sua sala privada.",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="👤 Dono", value=owner.mention, inline=True)
        embed.add_field(name="🔊 Canal", value=voice.mention, inline=True)
        embed.add_field(
            name="👥 Limite",
            value=str(voice.user_limit or "Ilimitado"),
            inline=True,
        )
        embed.set_footer(text="Use os botões abaixo para convidar, travar/destravar ou encerrar a sala.")
        return embed


# =========================================================
#   VIEW DO PAINEL DE SALA PRIVADA (padrão locked)
# =========================================================
class PrivateRoomPanelView(discord.ui.View):
    def __init__(self, cog: VoiceFactory, room: PrivateRoom):
        super().__init__(timeout=None)
        self.cog = cog
        self.room = room

        # select multi de usuários
        self.add_item(PrivateInviteMultiSelect(self))

    async def _check_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.room.owner_id:
            await interaction.response.send_message("Apenas o dono da sala pode usar este painel.", ephemeral=True)
            return False
        return True

    async def invite_members(self, interaction: discord.Interaction, members: list[discord.Member]):
        guild = interaction.guild
        if not guild:
            return

        for m in members:
            await self.cog.grant_private_access(guild, self.room, m)

    @discord.ui.button(label="Gerenciar convidados", style=discord.ButtonStyle.secondary, row=1)
    async def btn_manage_guests(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return

        guild = interaction.guild
        if not guild:
            return

        voice = guild.get_channel(self.room.voice_id)
        if not isinstance(voice, discord.VoiceChannel):
            return await interaction.response.send_message("Sala não encontrada.", ephemeral=True)

        desc = "Nenhum convidado ainda."
        if self.room.invited:
            linhas = []
            for uid in self.room.invited:
                m = guild.get_member(uid)
                if m:
                    linhas.append(m.mention)
            if linhas:
                desc = "\n".join(linhas)

        embed = discord.Embed(
            title="🎧 Convidados da sala",
            description=desc,
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="Selecione um ou mais convidados e use os botões abaixo.")

        view = PrivateGuestManagerView(self.cog, self.room)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Travar/Destravar sala", style=discord.ButtonStyle.secondary, row=1)
    async def btn_lock(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return

        guild = interaction.guild
        voice = guild.get_channel(self.room.voice_id)
        if not isinstance(voice, discord.VoiceChannel):
            return await interaction.response.send_message("Sala não encontrada.", ephemeral=True)

        default_role = guild.default_role
        perms = voice.overwrites_for(default_role)
        locked_now = (not perms.view_channel) or (perms.connect is False)

        if locked_now:
            await voice.set_permissions(default_role, view_channel=True, connect=True)
            msg = "Sala destravada."
        else:
            await voice.set_permissions(default_role, view_channel=False, connect=False)
            msg = "Sala travada."

        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(label="Encerrar sala", style=discord.ButtonStyle.danger, row=1)
    async def btn_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return

        guild = interaction.guild
        # responde antes de apagar, pra não dar Unknown Channel
        await interaction.response.send_message("Sala privada encerrada.", ephemeral=True)
        await self.cog.end_private_room(self.room, guild)


class PrivateInviteMultiSelect(discord.ui.UserSelect):
    def __init__(self, parent_view: PrivateRoomPanelView):
        self.parent_view = parent_view
        super().__init__(
            placeholder="Selecionar usuários para convidar…",
            min_values=1,
            max_values=10,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        if not await self.parent_view._check_owner(interaction):
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

        view = PrivateConfirmInviteView(self.parent_view, members)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class PrivateConfirmInviteView(discord.ui.View):
    def __init__(self, parent_panel: PrivateRoomPanelView, members: list[discord.Member]):
        super().__init__(timeout=60)
        self.parent_panel = parent_panel
        self.members = members

    @discord.ui.button(label="SIM", style=discord.ButtonStyle.success)
    async def btn_yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.parent_panel._check_owner(interaction):
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
        if not await self.parent_panel._check_owner(interaction):
            return

        await interaction.response.edit_message(
            content="Convite cancelado.",
            embed=None,
            view=None,
        )


class PrivateGuestManagerView(discord.ui.View):
    def __init__(self, cog: VoiceFactory, room: PrivateRoom):
        super().__init__(timeout=None)
        self.cog = cog
        self.room = room
        self.selected_ids: list[int] = []

        self.add_item(PrivateGuestSelect(self))

    async def _check_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.room.owner_id:
            await interaction.response.send_message(
                "Apenas o dono da sala pode gerenciar os convidados.",
                ephemeral=True,
            )
            return False
        return True

    async def _apply_to_selected(self, interaction: discord.Interaction, action: str):
        if not await self._check_owner(interaction):
            return

        guild = interaction.guild
        if not guild:
            return

        voice = guild.get_channel(self.room.voice_id)
        if not isinstance(voice, discord.VoiceChannel):
            return await interaction.response.send_message("Sala não encontrada.", ephemeral=True)

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
                ch = guild.get_channel(self.room.voice_id)
                if isinstance(ch, discord.VoiceChannel):
                    await ch.set_permissions(member, overwrite=None)
                if uid in self.room.invited:
                    self.room.invited.remove(uid)

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


class PrivateGuestSelect(discord.ui.Select):
    def __init__(self, parent_view: PrivateGuestManagerView):
        self.parent_view = parent_view
        room = parent_view.room
        cog = parent_view.cog
        guild = cog.bot.get_guild(room.guild_id)

        options: list[discord.SelectOption] = []
        if guild and room.invited:
            for uid in room.invited:
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


async def setup(bot):
    await bot.add_cog(VoiceFactory(bot))
