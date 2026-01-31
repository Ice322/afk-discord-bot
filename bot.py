import discord
from discord.ext import commands
from datetime import datetime, timedelta
import asyncio
import re
import os

# ================= НАСТРОЙКИ =================

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise RuntimeError("TOKEN not found in environment variables")
bot.run(TOKEN)
THUMBNAIL_URL = "https://media.discordapp.net/attachments/1070143838435422288/1070143912766865499/1b1261398fdfc086.png?ex=697f4bef&is=697dfa6f&hm=a413afa35cc7d39601b902008cf087398ff950844f4eb161d8ef7dfc5164f4f3&=&format=webp&quality=lossless&width=856&height=856"  # ссылка на картинку

# ============================================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

afk_users = {}

panel_message_id = None
panel_channel_id = None


# ================= ОБНОВЛЕНИЕ ПАНЕЛИ =================

async def update_panel():
    global panel_message_id, panel_channel_id

    if panel_message_id is None:
        return

    channel = bot.get_channel(panel_channel_id)
    if not channel:
        return

    try:
        message = await channel.fetch_message(panel_message_id)
    except:
        return

    embed = discord.Embed(
        title="⏳ Люди в AFK:",
        color=discord.Color.orange()
    )

    embed.set_thumbnail(url=THUMBNAIL_URL)

    now = datetime.now()

    if not afk_users:
        embed.description = (
            "Сейчас никто не в AFK.\n\n"
            "‎\n‎\n‎\n‎"
        )
    else:
        text = ""
        i = 1

        for user_id, data in list(afk_users.items()):
            remaining = int((data["end"] - now).total_seconds())

            if remaining <= 0:
                del afk_users[user_id]
                continue

            minutes = remaining // 60
            seconds = remaining % 60

            time_left = (
                f"{minutes}м {seconds}с"
                if minutes > 0
                else f"{seconds}с"
            )

            text += (
                f"**{i}. {data['tag']}**\n"
                f"Причина: `{data['reason']}`\n"
                f"⏳ Осталось: `{time_left}`\n\n"
            )
            i += 1

        text += "‎\n" * 2
        embed.description = text

    await message.edit(embed=embed, view=AFKPanel())


# ================= ЖИВОЙ ТАЙМЕР =================

async def live_timer():
    await bot.wait_until_ready()
    while True:
        await update_panel()
        await asyncio.sleep(1)


# ================= MODAL =================

class AFKModal(discord.ui.Modal, title="Отошел в AFK"):

    reason = discord.ui.TextInput(
        label="Причина",
        placeholder="Например: готовлю рыбу",
        required=True
    )

    time = discord.ui.TextInput(
        label="На сколько? (в минутах)",
        placeholder="Например: 15",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):

        match = re.search(r"\d+", str(self.time))
        if not match:
            await interaction.response.send_message(
                "❌ Введите время в минутах.",
                ephemeral=True
            )
            return

        minutes = int(match.group())
        end_time = datetime.now() + timedelta(minutes=minutes)

        afk_users[interaction.user.id] = {
            "tag": interaction.user.mention,
            "reason": str(self.reason),
            "end": end_time
        }

        await interaction.response.send_message(
            f"✅ Вы в AFK на {minutes} минут.",
            ephemeral=True
        )

        await update_panel()


# ================= КНОПКИ =================

class AFKPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Отошел АФК", style=discord.ButtonStyle.danger)
    async def go_afk(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AFKModal())

    @discord.ui.button(label="Вышел из АФК", style=discord.ButtonStyle.success)
    async def back_afk(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id in afk_users:
            del afk_users[interaction.user.id]
            await interaction.response.send_message(
                "✅ Вы вышли из AFK.",
                ephemeral=True
            )
            await update_panel()
        else:
            await interaction.response.send_message(
                "Вы не в AFK.",
                ephemeral=True
            )


# ================= КОМАНДА ПАНЕЛИ =================

@bot.command()
async def afkpanel(ctx):
    global panel_message_id, panel_channel_id

    embed = discord.Embed(
        title="⏳ Люди в AFK:",
        description="Сейчас никто не в AFK.\n\n‎\n‎\n‎",
        color=discord.Color.orange()
    )

    embed.set_thumbnail(url=THUMBNAIL_URL)

    msg = await ctx.send(embed=embed, view=AFKPanel())

    panel_message_id = msg.id
    panel_channel_id = ctx.channel.id
# ================= READY =================

@bot.event
async def on_ready():
    print(f"Бот запущен: {bot.user}")
    bot.loop.create_task(live_timer())
bot.run(TOKEN)