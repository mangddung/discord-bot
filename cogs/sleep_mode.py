import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from utils.database import get_connection, initialize_database

conn = get_connection()
cursor = conn.cursor()

db_table = ('''
CREATE TABLE IF NOT EXISTS sleep_mode (
    user_id TEXT PRIMARY KEY,
    enabled INTEGER DEFAULT 0,
    username TEXT,
    start_time TEXT,
    end_time TEXT, 
    weekdays INTEGER, 
    weekends INTEGER
)
''')

class SleepModeModal(discord.ui.Modal, title="취침모드 설정"):
    weekdays_input = discord.ui.TextInput(label="요일 (평일, 휴일, 매일)", placeholder="평일, 휴일, 매일 중 하나 입력")
    start_time_input = discord.ui.TextInput(label="시작 시간 (HH:MM)", placeholder="예: 23:00")
    end_time_input = discord.ui.TextInput(label="종료 시간 (HH:MM)", placeholder="예: 06:00")

    async def on_submit(self, interaction: discord.Interaction):
        weekdays = self.weekdays_input.value
        start_time = self.start_time_input.value
        end_time = self.end_time_input.value

        try:
            datetime.strptime(start_time, "%H:%M")
            datetime.strptime(end_time, "%H:%M")
        except ValueError:
            await interaction.response.send_message("시간 형식이 잘못되었습니다. HH:MM 형식으로 입력해주세요.", ephemeral=True)
            return
        
        cursor.execute('DELETE FROM sleep_mode WHERE user_id = ?', (str(interaction.user.id),))
        
        cursor.execute('''
            REPLACE INTO sleep_mode (user_id, username, start_time, end_time, weekdays, weekends, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (str(interaction.user.id), interaction.user.name, start_time, end_time,
              1 if weekdays in ["평일", "매일"] else 0, 1 if weekdays in ["휴일", "매일"] else 0, 1))

        conn.commit()
        await interaction.response.send_message(f"{weekdays}, {start_time}~{end_time}으로 설정되었습니다.", ephemeral=True)

class SleepMode(app_commands.Group):
    def __init__(self, bot: commands.Bot):
        super().__init__(name="취침모드", description="취침 모드 관련 명령어")
        self.bot = bot

    @app_commands.command(name="설정", description="취침 모드를 설정합니다.")
    async def set_sleep_mode(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SleepModeModal())

    @app_commands.command(name="켜기", description="취침 모드를 활성화합니다.")
    async def activate_sleep_mode(self, interaction: discord.Interaction):
        cursor.execute("SELECT start_time, end_time, weekdays, weekends, enabled FROM sleep_mode WHERE user_id = ?", (str(interaction.user.id),))
        result = cursor.fetchone()

        if not result:
            await interaction.response.send_message("❗ 취침 모드가 설정되지 않았습니다. `/취침모드 설정` 명령어를 사용해주세요.", ephemeral=True)
            return

        start_time, end_time, weekdays, weekends, enabled = result
        message = (f"{interaction.user.mention}, 현재 설정된 취침 모드 정보:\n"
                   f"시작 시간: {start_time}\n"
                   f"종료 시간: {end_time}\n"
                   f"주중 설정: {'활성화' if weekdays else '비활성화'}\n"
                   f"휴일 설정: {'활성화' if weekends else '비활성화'}")

        if not enabled:
            cursor.execute("UPDATE sleep_mode SET enabled = 1 WHERE user_id = ?", (str(interaction.user.id),))
            conn.commit()
            message += "\n✅ 취침 모드가 활성화되었습니다."

        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="끄기", description="취침 모드를 비활성화합니다.")
    async def deactivate_sleep_mode(self, interaction: discord.Interaction):
        cursor.execute("SELECT enabled FROM sleep_mode WHERE user_id = ?", (str(interaction.user.id),))
        result = cursor.fetchone()

        if not result:
            await interaction.response.send_message("❗ 취침모드 설정이 없습니다. `/취침모드 설정`으로 설정해주세요.", ephemeral=True)
            return

        if not result[0]:  # result[0] = enabled 값
            await interaction.response.send_message("❗ 이미 비활성화 상태입니다.", ephemeral=True)
            return

        cursor.execute("UPDATE sleep_mode SET enabled = 0 WHERE user_id = ?", (str(interaction.user.id),))
        conn.commit()
        await interaction.response.send_message("✅ 취침모드가 비활성화되었습니다.", ephemeral=True)

async def setup(bot: commands.Bot):
    initialize_database(db_table)
    bot.tree.add_command(SleepMode(bot))
