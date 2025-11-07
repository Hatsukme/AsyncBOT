import discord
from discord.ext import commands
from asyncio import Lock
from utils.channels import load_channels, save_channels


class VoiceFactory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.deleting = Lock()  # Evita race condition ao deletar

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        data = load_channels()
        templates = data.get("voice_templates", {})
        temps = data.setdefault("voice_temporary", [])

        # ======================
        # ENTRANDO EM ALGUM CANAL
        # ======================
        if after.channel:
            base = after.channel.id

            async def create_temp(key, name, limit=None):
                # Lista de canais-base para aquele tipo
                base_list = templates.get(key, [])

                # Se não é um canal-base → não criar nada
                if base not in base_list:
                    return

                category = after.channel.category

                # Criar canal temporário
                new = await member.guild.create_voice_channel(
                    name=name,
                    user_limit=limit,
                    category=category
                )

                # Registrar como temporário
                temps.append(new.id)
                save_channels(data)

                # Mover pessoa para o canal recém-criado
                await member.move_to(new)

            # Criação conforme o tipo
            await create_temp("voice_duo", f"🔹 Duo • {member.display_name}", 2)
            await create_temp("voice_esquadrao", f"🔸 Esquadrão • {member.display_name}", 4)
            await create_temp("voice_geral", f"🎤 Sala • {member.display_name}")

        # ======================
        # SAINDO DE ALGUM CANAL
        # ======================
        temp_list = data.get("voice_temporary", [])

        # Se o canal que a pessoa saiu é um temporário
        if before.channel and before.channel.id in temp_list:
            # E ficou vazio
            if len(before.channel.members) == 0:
                async with self.deleting:
                    data = load_channels()
                    temp_list = data.get("voice_temporary", [])

                    # Verifica novamente antes de deletar
                    if before.channel.id in temp_list and len(before.channel.members) == 0:
                        await before.channel.delete()
                        temp_list.remove(before.channel.id)
                        save_channels(data)


async def setup(bot):
    await bot.add_cog(VoiceFactory(bot))
