import traceback
from discord.ext import commands
from discord import app_commands
import discord, random, asyncio

# ============================================================
# CONFIG / HELPERS
# ============================================================

is_roleta_running = False
duelo_em_andamento = False

PROVOCACOES_DESISTENCIA = [
    "Correu mais rápido que a própria sombra!",
    "Nem sacou o revólver, covarde!",
    "O vento soprou mais forte que sua coragem!",
    "Ouvi dizer que o gatilho era pesado demais…",
    "Se proteja! O faroeste é perigoso… para sua autoestima. 😏",
]


async def safe_edit(msg, **kwargs):
    if not msg:
        return
    try:
        await msg.edit(**kwargs)
    except Exception:
        pass


async def safe_delete(msg):
    if not msg:
        return
    try:
        await msg.delete()
    except Exception:
        pass


# ============================================================
# FUN COG
# ============================================================

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ============================================================
    #                        COMANDO DUELO
    # ============================================================

    @app_commands.command(name="duelo", description="Inicia um duelo de faroeste entre dois jogadores.")
    async def duelo(self, interaction: discord.Interaction, alvo: discord.Member):
        autor = interaction.user

        if not alvo or alvo == autor:
            return await interaction.response.send_message(
                "💥 Você precisa desafiar alguém válido! Use: `/duelo @alguem`",
                ephemeral=True
            )

        await interaction.response.send_message("🤠 Preparando o cenário do duelo...")
        msg_loading = await interaction.original_response()

        try:
            view = self.DueloLayout(interaction, autor, alvo)
            view.message = await msg_loading.edit(content=None, view=view)

            print(f"[DUELO] {autor} desafiou {alvo} para um duelo!")
            asyncio.create_task(view._timeout_confirmacao())

        except Exception as e:
            traceback.print_exc()
            await msg_loading.edit(content=f"❌ Erro ao iniciar o duelo: {e}")

    # ============================================================
    #                   LAYOUT (INTERFACE DE DUELO)
    # ============================================================
    class DueloLayout(discord.ui.LayoutView):
        EMOJIS = {"P": "⚜️", "O": "♦️", "E": "⚔️", "C": "❤️"}
        NIPES = ["P", "O", "E", "C"]

        def __init__(self, interaction, desafiante, desafiado):
            super().__init__(timeout=None)
            self.interaction = interaction
            self.desafiante = desafiante
            self.desafiado = desafiado
            self.message: discord.Message | None = None

            # aceitação
            self.aceitou = set()

            # escolhas por jogador (listas de 0..4 letras)
            self.escolhas = {self.desafiante.id: [], self.desafiado.id: []}

            # sequência do bot (pode repetir nipe!)
            self.bot_seq: list[str] = []

            self.rodada = 0
            self.finalizado = False

            # HEADER → mostra o desafiante
            self.header_text = discord.ui.TextDisplay(
                content=f"🤠 **Duelo**\nDesafiante: {desafiante.display_name}")
            self.header_thumb = discord.ui.Thumbnail(media=desafiante.display_avatar.url)
            self.header = discord.ui.Section(self.header_text, accessory=self.header_thumb)

            # CARD → mostra o desafiado
            self.card_text = discord.ui.TextDisplay(
                content=(
                    f"Desafiado: **{desafiado.display_name}**\n\n"
                    f"**{desafiante.display_name}** desafiou **{desafiado.display_name}** para um duelo!\n"
                    "Aguardando a confirmação do dois participantes..."
                )
            )
            self.card_thumb = discord.ui.Thumbnail(media=desafiado.display_avatar.url)
            self.card = discord.ui.Section(self.card_text, accessory=self.card_thumb)

            # BOTÕES (fase 1 - aceitar/recusar)
            self.btn_aceitar = discord.ui.Button(label="🤝 Aceitar", style=discord.ButtonStyle.success)
            self.btn_recusar = discord.ui.Button(label="❌ Recusar", style=discord.ButtonStyle.danger)
            self.btn_aceitar.callback = self._on_aceitar
            self.btn_recusar.callback = self._on_recusar

            self.container = discord.ui.Container(
                self.header,
                self.card,
                discord.ui.ActionRow(self.btn_aceitar, self.btn_recusar)
            )
            self.add_item(self.container)

        # ============================== HELPERS ==============================
        def _fmt_barra_seq(self, uid: int) -> str:
            """Exibe a sequência escolhida por um jogador com placeholders."""
            seq = self.escolhas[uid]
            mostrados = [self.EMOJIS[c] for c in seq]
            while len(mostrados) < 4:
                mostrados.append("▫️")  # placeholder
            return " ".join(mostrados)

        async def _refresh_message(self):
            try:
                if self.message:
                    await self.message.edit(view=self)
            except Exception:
                pass

        def _is_player(self, user: discord.abc.User) -> bool:
            return user.id in (self.desafiante.id, self.desafiado.id)

        # ============================ FASE 1: A/R ============================
        async def _on_aceitar(self, interaction: discord.Interaction):
            user = interaction.user
            if not self._is_player(user):
                return await interaction.response.send_message("Este duelo não é seu, cowboy!", ephemeral=True)

            if user.id in self.aceitou:
                return await interaction.response.send_message("Você já aceitou o duelo!", ephemeral=True)

            self.aceitou.add(user.id)

            # usa response.send_message pra manter a interação válida
            await interaction.response.send_message(f"🤝 {user.display_name} aceitou o duelo!", ephemeral=True)

            if len(self.aceitou) == 2:
                # atualiza visualmente e agenda a próxima fase sem travar a interação
                self.card_text.content = "🔥 Ambos aceitaram o duelo! Preparem-se..."
                await self._refresh_message()
                asyncio.create_task(self._preparar_escolhas())
            else:
                self.card_text.content = f"🤝 {user.display_name} aceitou o duelo!\nAguardando o outro jogador..."
                await self._refresh_message()

        async def _timeout_confirmacao(self):
            """Provocações se alguém não confirmar o duelo a tempo."""
            await asyncio.sleep(30)  # tempo de confirmação

            if self.finalizado or len(self.aceitou) == 2:
                return  # já começou o duelo

            desafiante_aceitou = self.desafiante.id in self.aceitou
            desafiado_aceitou = self.desafiado.id in self.aceitou

            if desafiante_aceitou and not desafiado_aceitou:
                frases = [
                    f"😏 {self.desafiado.display_name} arregou... parece que o barulho do gatilho assustou.",
                    f"💨 {self.desafiado.display_name} desapareceu mais rápido que uma bala perdida.",
                    f"😴 {self.desafiado.display_name} ficou pensando demais... e perdeu a coragem."
                ]
                provocacao = random.choice(frases)

            elif desafiado_aceitou and not desafiante_aceitou:
                frases = [
                    f"😏 {self.desafiante.display_name} convidou pro duelo e fugiu? Que vergonha...",
                    f"💨 {self.desafiante.display_name} sumiu na poeira antes de puxar o gatilho.",
                    f"😴 {self.desafiante.display_name} prometeu um show... mas só entregou silêncio."
                ]
                provocacao = random.choice(frases)

            else:
                frases = [
                    "🐔 Dois covardes... nem pra morrer juntos tiveram coragem.",
                    "😴 O saloon inteiro esperou... e ninguém puxou o gatilho.",
                    "💤 O faroeste ficou entediado. Nenhum dos dois teve coragem de começar."
                ]
                provocacao = random.choice(frases)

            # mostra provocação por 30s
            self.card_text.content = provocacao
            await self._refresh_message()
            await asyncio.sleep(30)

            # apaga mensagem final
            try:
                await self.message.delete()
            except:
                pass

        async def _on_recusar(self, interaction: discord.Interaction):
            user = interaction.user
            if not self._is_player(user):
                return await interaction.response.send_message("Você nem está nesse duelo, curioso.", ephemeral=True)

            PROVOCACOES_DESISTENCIA = [
                "Correu mais rápido que a própria sombra!💨",
                "Nem sacou o revólver, covarde!",
                "O vento soprou mais forte que sua coragem!",
                "Ouvi dizer que o gatilho era pesado demais…",
                "Se proteja! O faroeste é perigoso… para sua autoestima. 😏",
            ]

            await interaction.response.defer()
            self.card_text.content = f" {user.display_name} {random.choice(PROVOCACOES_DESISTENCIA)}"
            self.btn_aceitar.disabled = True
            self.btn_recusar.disabled = True
            await self._refresh_message()

        # ======================== FASE 2: ESCOLHER SEQ =======================
        async def _preparar_escolhas(self):
            """Troca a UI para botões de naipes e caixas de progresso dos dois jogadores."""
            self.card_text.content = (
                f"🔥 O duelo entre **{self.desafiante.display_name}** e **{self.desafiado.display_name}** vai começar!\n\n"
                "Escolha sua sequência de nipes. Exemplo: ⚜️, ♦️, ⚔️, ❤️."
            )
            self.btn_aceitar.disabled = True
            self.btn_recusar.disabled = True

            # remove todos os componentes antigos da view
            self.clear_items()

            # HEADER + CARD
            self.container = discord.ui.Container(
                self.header,
                self.card
            )

            self.sec_prog = discord.ui.Section(
                discord.ui.TextDisplay(
                    content=(
                        f"**{self.desafiante.display_name}**: {self._fmt_barra_seq(self.desafiante.id)}\n"
                        f"**{self.desafiado.display_name}**: {self._fmt_barra_seq(self.desafiado.id)}"
                    )
                ),
                accessory=discord.ui.Thumbnail(media=self.desafiado.display_avatar.url)
            )

            # botões de escolha (compartilhados)
            self.btn_p = discord.ui.Button(emoji=self.EMOJIS["P"], style=discord.ButtonStyle.secondary)
            self.btn_o = discord.ui.Button(emoji=self.EMOJIS["O"], style=discord.ButtonStyle.secondary)
            self.btn_e = discord.ui.Button(emoji=self.EMOJIS["E"], style=discord.ButtonStyle.secondary)
            self.btn_c = discord.ui.Button(emoji=self.EMOJIS["C"], style=discord.ButtonStyle.secondary)

            self.btn_p.callback = lambda i: self._on_pick(i, "P")
            self.btn_o.callback = lambda i: self._on_pick(i, "O")
            self.btn_e.callback = lambda i: self._on_pick(i, "E")
            self.btn_c.callback = lambda i: self._on_pick(i, "C")

            # adiciona container + nova linha de botões
            self.container.add_item(discord.ui.ActionRow(self.btn_p, self.btn_o, self.btn_e, self.btn_c))
            self.add_item(self.container)

            await self._refresh_message()

        async def _on_pick(self, interaction: discord.Interaction, letra: str):
            """Jogador clica em um dos botões de naipe para montar sua sequência."""
            user = interaction.user
            if not self._is_player(user):
                return await interaction.response.send_message("Xiii… não mete a mão nesse baralho, parceiro.",
                                                               ephemeral=True)

            atual = self.escolhas[user.id]

            # impede o jogador de repetir um naipe já usado
            if letra in atual:
                return await interaction.response.send_message("Você já escolheu esse naipe, cowboy!", ephemeral=True)

            if len(atual) == 4:
                try:
                    await interaction.followup.send("✅ Sequência registrada com sucesso!", ephemeral=True)
                except:
                    pass
            atual.append(letra)
            await interaction.response.defer()

            # Confirmacao da sequencia finalizada
            if len(atual) == 4:
                try:
                    await interaction.followup.send("✅ Sequência registrada com sucesso!", ephemeral=True)
                except:
                    pass

            # Atualiza barra dos dois
            self.txt_prog = discord.ui.TextDisplay(
                content=(
                    f"**{self.desafiante.display_name}**: {self._fmt_barra_seq(self.desafiante.id)}\n"
                    f"**{self.desafiado.display_name}**: {self._fmt_barra_seq(self.desafiado.id)}"
                )
            )
            self.sec_prog = discord.ui.Section(
                self.txt_prog,
                accessory=discord.ui.Thumbnail(media=self.desafiado.display_avatar.url)
            )

            # Se ambos terminaram, segue o jogo
            if len(self.escolhas[self.desafiante.id]) == 4 and len(self.escolhas[self.desafiado.id]) == 4:
                # trava botões pra ambos
                for btn in (self.btn_p, self.btn_o, self.btn_e, self.btn_c):
                    btn.disabled = True
                await self._refresh_message()
                # inicia o duelo em segundo plano
                asyncio.create_task(self._iniciar_duelo())

            else:
                await self._refresh_message()

        # ===================== FASE 3: REVELAÇÃO PROGRESSIVA =================
        async def _iniciar_duelo(self):
            """Revela as cartas rodada a rodada, mostrando também escolhas de cada jogador."""
            # sequência do bot com possibilidade de repetir nipe
            self.bot_seq = random.sample(self.NIPES, k=4)
            print(f"[BOT] Sequência oculta: {self.bot_seq}")

            # contagem rápida
            self.card_text.content = "🎲 Sequências definidas! Preparar..."
            await self._refresh_message()
            await asyncio.sleep(1)
            for n in range(3, 0, -1):
                self.card_text.content = f"⏳ {n}..."
                await self._refresh_message()
                await asyncio.sleep(1)

            vencedor = None
            empate_total = False

            # rodada a rodada
            for i, carta in enumerate(self.bot_seq):
                self.rodada = i + 1
                emoji_carta = self.EMOJIS[carta]

                # escolhas da rodada dos jogadores
                esc_desafiante = self.escolhas[self.desafiante.id][i]
                esc_desafiado = self.escolhas[self.desafiado.id][i]
                emoji_desa = self.EMOJIS[esc_desafiante]
                emoji_deso = self.EMOJIS[esc_desafiado]

                # mostra carta revelada
                self.card_text.content = f"🃏 **Rodada {self.rodada}**\nCarta revelada: {emoji_carta}"
                await self._refresh_message()
                await asyncio.sleep(1)

                # mostra escolhas dos dois
                self.card_text.content = (
                    f"🃏 **Rodada {self.rodada}**\n"
                    f"Carta revelada: {emoji_carta}\n\n"
                    f"**{self.desafiante.display_name}** \n {emoji_desa}\n"
                    f"**{self.desafiado.display_name}** \n {emoji_deso}"
                )
                await self._refresh_message()
                await asyncio.sleep(1)

                # verifica acertos
                acerta_desa = (esc_desafiante == carta)
                acerta_deso = (esc_desafiado == carta)

                if acerta_desa and acerta_deso:
                    empate_total = True
                    break
                if acerta_desa:
                    vencedor = self.desafiante
                    break
                if acerta_deso:
                    vencedor = self.desafiado
                    break

            # resultado
            await asyncio.sleep(1)

            Empate_Total = [
                "💀 Ambos puxaram o gatilho ao mesmo tempo... o faroeste nunca viu dois tolos tão sincronizados.",
                "💀 Dois tiros, um silêncio... e ninguém pra contar vantagem.",
                "💀 Bang! Bang! ... e os dois caíram. Chamem o coveiro, temos trabalho em dobro.",
            ]

            Empate_Parcial = [
                "🤝 Ninguém acertou... parece que esqueceram de tirar a trava do revólver.",
                "🤝 Dois covardes atirando pro vento — bonito show de pólvora, mas zero precisão.",
                "🤝 O deserto ecoou o som de dois tiros... e nenhum atingiu o alvo. Patético e poético ao mesmo tempo.",
            ]

            if empate_total:
                resultado = f"{random.choice(Empate_Total)}"
            elif vencedor:
                Vencedor_Duelo = [
                    f"🏆 {vencedor.display_name} foi mais rápido que a própria sombra — o outro só piscou e já era.",
                    f"🏆 O pó ainda nem assentou, e {vencedor.display_name} já guardou o revólver com um sorriso torto.",
                    f"🏆 {vencedor.display_name} disparou sem hesitar... e o silêncio disse o resto.",
                ]
                resultado = f"{random.choice(Vencedor_Duelo)}"
            else:
                resultado = f"{random.choice(Empate_Parcial)}"

            # Sequências completas (emojis)
            seq_bot = " ".join(self.EMOJIS[c] for c in self.bot_seq)
            seq_desafiante = " ".join(self.EMOJIS[c] for c in self.escolhas[self.desafiante.id])
            seq_desafiado = " ".join(self.EMOJIS[c] for c in self.escolhas[self.desafiado.id])

            # Mensagem final estilizada
            self.card_text.content = (
                "🎯 **Sequências reveladas!**\n\n"
                f"**Dealer:** {seq_bot}\n\n"
                f"**{self.desafiante.display_name}:**\n{seq_desafiante}\n"
                f"**{self.desafiado.display_name}:** \n{seq_desafiado}\n\n"
                f"**Resultado:** {resultado}"
            )

            self.finalizado = True
            await self._refresh_message()

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            # permite interações apenas dos dois jogadores
            if interaction.user.id in (self.desafiante.id, self.desafiado.id):
                return True
            try:
                await interaction.response.send_message(
                    "Este duelo não é seu, cowboy. Só os dois jogadores podem interagir aqui.",
                    ephemeral=True,
                )
            except:
                pass
            return False


async def setup(bot):
    await bot.add_cog(Fun(bot))
