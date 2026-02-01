import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла (если существует)
load_dotenv()

# Инициализация бота
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Хранилище AFK пользователей
AFK_DATA = {}
AFK_FILE = "afk_data.json"
CHANNEL_ID = None  # Будет установлено при первом использовании
MESSAGE_ID = None  # ID сообщения со списком AFK
TABLE_MESSAGE = None  # Объект сообщения для обновления таблицы

# Загрузка данных из JSON
def load_afk_data():
    global AFK_DATA
    if os.path.exists(AFK_FILE):
        try:
            with open(AFK_FILE, 'r', encoding='utf-8') as f:
                AFK_DATA = json.load(f)
        except:
            AFK_DATA = {}
    else:
        AFK_DATA = {}

# Сохранение данных в JSON
def save_afk_data():
    with open(AFK_FILE, 'w', encoding='utf-8') as f:
        json.dump(AFK_DATA, f, ensure_ascii=False, indent=2)

# Модальное окно для ввода причины и времени AFK
class AFKModal(discord.ui.Modal, title="Отошел AFK"):
    reason = discord.ui.TextInput(
        label="Причина ухода",
        placeholder="Например: обед, встреча, сон",
        required=True,
        max_length=100
    )
    
    time_input = discord.ui.TextInput(
        label="Время отсутствия (минуты или чч:мм)",
        placeholder="Например: 30 или 1:30",
        required=True,
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        reason = self.reason.value
        time_str = self.time_input.value
        
        # Парсинг времени
        try:
            if ':' in time_str:
                # Формат чч:мм
                parts = time_str.split(':')
                hours = int(parts[0])
                minutes = int(parts[1])
                total_minutes = hours * 60 + minutes
            else:
                # Просто минуты
                total_minutes = int(time_str)
            
            if total_minutes <= 0:
                await interaction.response.send_message(
                    "❌ Время должно быть больше 0 минут!",
                    ephemeral=True
                )
                return
            
            # Добавление пользователя в AFK
            end_time = datetime.now() + timedelta(minutes=total_minutes)
            AFK_DATA[user_id] = {
                "username": interaction.user.name,
                "reason": reason,
                "start_time": datetime.now().isoformat(),
                "end_time": end_time.isoformat(),
                "duration_minutes": total_minutes
            }
            save_afk_data()
            
            await interaction.response.send_message(
                f"✅ Вы добавлены в список AFK на {total_minutes} минут!",
                ephemeral=True
            )
            
            # Обновление списка AFK
            await update_afk_table()
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Неверный формат времени! Используйте: 30 или 1:30",
                ephemeral=True
            )

# Кнопки для управления AFK
class AFKButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Отошел АФК", style=discord.ButtonStyle.danger, emoji="⏳")
    async def afk_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AFKModal())
    
    @discord.ui.button(label="Вышел из АФК", style=discord.ButtonStyle.success, emoji="✅")
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        
        if user_id in AFK_DATA:
            del AFK_DATA[user_id]
            save_afk_data()
            await interaction.response.send_message(
                "✅ Вы вышли из AFK!",
                ephemeral=True
            )
            await update_afk_table()
        else:
            await interaction.response.send_message(
                "❌ Вы не в списке AFK!",
                ephemeral=True
            )

# Функция для форматирования оставшегося времени (только в минутах)
def format_remaining_time(end_time_str: str) -> int:
    end_time = datetime.fromisoformat(end_time_str)
    remaining = end_time - datetime.now()
    
    if remaining.total_seconds() <= 0:
        return 0
    
    minutes = int(remaining.total_seconds() // 60)
    return minutes

# Обновление таблицы AFK (редактирование существующего сообщения)
async def update_afk_table():
    global MESSAGE_ID, CHANNEL_ID, TABLE_MESSAGE
    
    if CHANNEL_ID is None:
        return
    
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        return
    
    # Удаление истекших AFK
    expired_users = []
    for user_id, data in AFK_DATA.items():
        end_time = datetime.fromisoformat(data["end_time"])
        if datetime.now() >= end_time:
            expired_users.append(user_id)
    
    for user_id in expired_users:
        del AFK_DATA[user_id]
    
    save_afk_data()
    
    # Формирование embed сообщения
    if len(AFK_DATA) == 0:
        description = "Сейчас никто не в AFK ✨"
    else:
        description = ""
        for idx, (user_id, data) in enumerate(AFK_DATA.items(), 1):
            remaining = format_remaining_time(data["end_time"])
            description += f"{idx}. <@{user_id}> — {data['reason']} — {remaining}м\n"
    
    embed = discord.Embed(
        title="⏳ Люди в AFK:",
        description=description,
        color=0xFF6B35  # Оранжевый цвет
    )
    
    # Добавление логотипа UZI из локального файла
    embed.set_thumbnail(url="attachment://UZI_Logo_Vector_3_1.png")
    
    # Обновление или создание сообщения
    try:
        if MESSAGE_ID:
            TABLE_MESSAGE = await channel.fetch_message(MESSAGE_ID)
            # Отправляем с файлом логотипа
            file = discord.File("UZI_Logo_Vector_3_1.png")
            await TABLE_MESSAGE.edit(embed=embed, view=AFKButtons(), attachments=[file])
        else:
            file = discord.File("UZI_Logo_Vector_3_1.png")
            TABLE_MESSAGE = await channel.send(embed=embed, view=AFKButtons(), file=file)
            MESSAGE_ID = TABLE_MESSAGE.id
    except:
        file = discord.File("UZI_Logo_Vector_3_1.png")
        TABLE_MESSAGE = await channel.send(embed=embed, view=AFKButtons(), file=file)
        MESSAGE_ID = TABLE_MESSAGE.id

# Фоновая задача для обновления списка AFK (каждые 30 секунд)
@tasks.loop(seconds=30)
async def update_afk_list():
    await update_afk_table()

# События бота
@bot.event
async def on_ready():
    global CHANNEL_ID
    print(f"✅ Бот {bot.user} подключен!")
    
    # Загрузка данных
    load_afk_data()
    
    # Синхронизация команд
    try:
        synced = await bot.tree.sync()
        print(f"✅ Синхронизировано {len(synced)} команд")
    except Exception as e:
        print(f"❌ Ошибка синхронизации: {e}")
    
    # Запуск фоновой задачи
    if not update_afk_list.is_running():
        update_afk_list.start()
    
    print("✅ AFK Tracker готов к работе!")

# Команда для инициализации AFK трекера в канале
@bot.tree.command(name="afk_init", description="Инициализировать AFK трекер в этом канале")
async def afk_init(interaction: discord.Interaction):
    global CHANNEL_ID, MESSAGE_ID
    
    # Проверка прав администратора
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Только администраторы могут инициализировать трекер!",
            ephemeral=True
        )
        return
    
    CHANNEL_ID = interaction.channel.id
    MESSAGE_ID = None
    
    await interaction.response.send_message("✅ AFK трекер инициализирован в этом канале!", ephemeral=True)
    await update_afk_table()

# Команда для просмотра статистики
@bot.tree.command(name="afk_stats", description="Показать статистику AFK")
async def afk_stats(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📊 Статистика AFK",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="Всего в AFK", value=str(len(AFK_DATA)), inline=False)
    
    if len(AFK_DATA) > 0:
        stats_text = ""
        for user_id, data in AFK_DATA.items():
            remaining = format_remaining_time(data["end_time"])
            stats_text += f"<@{user_id}> — {data['reason']} ({remaining} мин)\n"
        embed.add_field(name="Пользователи", value=stats_text, inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Запуск бота
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    
    if not TOKEN:
        print("❌ Ошибка: DISCORD_TOKEN не установлен!")
        print(f"📋 Доступные переменные окружения: {list(os.environ.keys())}")
        exit(1)
    
    print(f"✅ Токен найден (первые 10 символов): {TOKEN[:10]}...")
    bot.run(TOKEN)
