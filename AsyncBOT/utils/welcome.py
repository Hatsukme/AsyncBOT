import discord
from utils.channels import load_channels
from utils.phrase_builder import gerar_boas_vindas

async def send_welcome(bot: discord.Client, member: discord.Member):
    data = load_channels()
    if "welcome" not in data:
        return

    channel = bot.get_channel(data["welcome"])
    if channel is None:
        return

    avatar = member.display_avatar.url
    frase = gerar_boas_vindas(member.mention)

    # CARD
    card_text = discord.ui.TextDisplay(
        content=(
            f"{frase}\n\n"
            f"🆔 : `{member.id}`\n"
        )
    )
    card_thumb = discord.ui.Thumbnail(media=avatar)
    card = discord.ui.Section(card_text, accessory=card_thumb)


    # MONTA O CARD
    container = discord.ui.Container(
        card
    )

    view = discord.ui.LayoutView(timeout=None)
    view.add_item(container)

    await channel.send(view=view)
