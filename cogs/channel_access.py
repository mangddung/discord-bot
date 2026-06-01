import discord
from discord import app_commands
from discord.ext import commands
import logging
from utils.database import get_connection, initialize_database

db_table = '''
CREATE TABLE IF NOT EXISTS channel_access (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id INTEGER NOT NULL,
    access_channel_id INTEGER NOT NULL,
    access_message_id INTEGER NOT NULL,
    target_channel_id INTEGER NOT NULL,
    target_channel_name TEXT NOT NULL
)
'''


class ChannelAccessCog(commands.GroupCog, name="채널접근"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.conn = get_connection()
        self.cursor = self.conn.cursor()

    @app_commands.command(name="채널생성", description="비공개 텍스트 채널을 생성합니다.")
    @app_commands.checks.has_permissions(administrator=True)
    async def create_channel(self, interaction: discord.Interaction, 채널명: str):
        channel = await interaction.guild.create_text_channel(채널명)
        await channel.set_permissions(interaction.guild.default_role, read_messages=False)
        await interaction.response.send_message(f"채널 '{channel.name}'이 생성되었습니다.", ephemeral=True)

    @app_commands.command(name="메시지생성", description="채널 접근 권한 부여 메시지를 생성합니다.")
    @app_commands.checks.has_permissions(administrator=True)
    async def create_message(self, interaction: discord.Interaction, 채널명: str):
        target_channel = discord.utils.get(interaction.guild.channels, name=채널명)
        if not target_channel:
            await interaction.response.send_message(f"채널 '{채널명}'이 존재하지 않습니다.", ephemeral=True)
            return
        if not target_channel.permissions_for(interaction.user).read_messages:
            await interaction.response.send_message(f"'{채널명}' 채널에 대한 읽기 권한이 없습니다.", ephemeral=True)
            return
        try:
            await interaction.response.defer(ephemeral=True)
            message = await interaction.channel.send(f"__**{채널명}**__ 채널 권한 부여를 위해 아래 이모지를 눌러주세요.")
            await message.add_reaction("✅")
            self.cursor.execute('''
                INSERT INTO channel_access (server_id, access_channel_id, access_message_id, target_channel_id, target_channel_name)
                VALUES (?, ?, ?, ?, ?)
            ''', (interaction.guild.id, interaction.channel.id, message.id, target_channel.id, 채널명))
            self.conn.commit()
            await interaction.followup.send("권한 부여 메시지가 생성되었습니다.", ephemeral=True)
            logging.info(f'{interaction.user.display_name}님이 {채널명} 채널 권한 부여 메시지 생성')
        except Exception as e:
            logging.error(f'{interaction.user.display_name}님이 {채널명} 채널 권한 부여 메시지 생성 실패: {e}')
            await interaction.followup.send(f"채널 '{채널명}' 권한 부여 메시지 생성 실패", ephemeral=True)

    @app_commands.command(name="메시지삭제", description="채널 접근 권한 부여 메시지를 삭제합니다.")
    @app_commands.checks.has_permissions(administrator=True)
    async def delete_message(self, interaction: discord.Interaction, 채널명: str):
        target_channel = discord.utils.get(interaction.guild.channels, name=채널명)
        if not target_channel:
            await interaction.response.send_message(f"채널 '{채널명}'이 존재하지 않습니다.", ephemeral=True)
            return
        if not target_channel.permissions_for(interaction.user).read_messages:
            await interaction.response.send_message(f"'{채널명}' 채널에 대한 읽기 권한이 없습니다.", ephemeral=True)
            return
        self.cursor.execute('''
            SELECT * FROM channel_access
            WHERE access_channel_id = ? AND target_channel_id = ?
        ''', (interaction.channel.id, target_channel.id))
        db = self.cursor.fetchone()
        if not db:
            await interaction.response.send_message(f"채널 '{채널명}'에 대한 권한 부여 메시지가 없습니다.", ephemeral=True)
            return
        try:
            await interaction.response.defer(ephemeral=True)
            msg = await interaction.channel.fetch_message(db[3])
            await msg.delete()
            self.cursor.execute('DELETE FROM channel_access WHERE access_message_id = ?', (db[3],))
            self.conn.commit()
            await interaction.followup.send("권한 부여 메시지가 삭제되었습니다.", ephemeral=True)
            logging.info(f'{interaction.user.display_name}님이 {채널명} 채널 권한 부여 메시지 삭제')
        except Exception as e:
            logging.error(f'{interaction.user.display_name}님이 {채널명} 채널 권한 부여 메시지 삭제 실패: {e}')
            await interaction.followup.send(f"채널 '{채널명}' 권한 부여 메시지 삭제 실패", ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.member and payload.member.bot:
            return
        if str(payload.emoji) != '✅':
            return
        self.cursor.execute('''
            SELECT * FROM channel_access
            WHERE access_message_id = ? AND access_channel_id = ?
        ''', (payload.message_id, payload.channel_id))
        db = self.cursor.fetchone()
        if db:
            target_channel = self.bot.get_channel(int(db[4]))
            member = self.bot.get_guild(payload.guild_id).get_member(payload.user_id)
            await target_channel.set_permissions(member, read_messages=True, send_messages=True)
            logging.info(f'{member.display_name}님이 {target_channel.name}채널 접근 권한을 부여하셨습니다.')

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if str(payload.emoji) != '✅':
            return
        self.cursor.execute('''
            SELECT * FROM channel_access
            WHERE access_message_id = ? AND access_channel_id = ?
        ''', (payload.message_id, payload.channel_id))
        db = self.cursor.fetchone()
        if db:
            target_channel = self.bot.get_channel(int(db[4]))
            member = self.bot.get_guild(payload.guild_id).get_member(payload.user_id)
            await target_channel.set_permissions(member, read_messages=False, send_messages=False)
            logging.info(f'{member.display_name}님이 {target_channel.name}채널 접근 권한을 취소하셨습니다.')

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        # target_channel 삭제: 연결된 권한 부여 메시지도 함께 제거
        self.cursor.execute('SELECT * FROM channel_access WHERE target_channel_id = ?', (channel.id,))
        for db in self.cursor.fetchall():
            access_ch = self.bot.get_channel(int(db[2]))
            if access_ch:
                try:
                    msg = await access_ch.fetch_message(db[3])
                    await msg.delete()
                except Exception:
                    pass
        self.cursor.execute('DELETE FROM channel_access WHERE target_channel_id = ?', (channel.id,))
        logging.info(f'채널 삭제: target_channel={channel.name} 관련 channel_access 레코드 정리')

        # access_channel 삭제: 메시지는 이미 소멸, DB 레코드만 제거
        self.cursor.execute('DELETE FROM channel_access WHERE access_channel_id = ?', (channel.id,))
        self.conn.commit()
        logging.info(f'채널 삭제: access_channel={channel.name} 관련 channel_access 레코드 정리')

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        if before.name == after.name:
            return
        self.cursor.execute('SELECT * FROM channel_access WHERE target_channel_id = ?', (after.id,))
        rows = self.cursor.fetchall()
        for db in rows:
            access_ch = self.bot.get_channel(int(db[2]))
            if access_ch:
                try:
                    msg = await access_ch.fetch_message(db[3])
                    await msg.edit(content=f"__**{after.name}**__ 채널 권한 부여를 위해 아래 이모지를 눌러주세요.")
                except Exception:
                    pass
        self.cursor.execute(
            'UPDATE channel_access SET target_channel_name = ? WHERE target_channel_id = ?',
            (after.name, after.id)
        )
        self.conn.commit()
        logging.info(f'채널 이름 변경: {before.name} → {after.name}, channel_access 레코드 업데이트')


async def setup(bot: commands.Bot):
    initialize_database(db_table)
    await bot.add_cog(ChannelAccessCog(bot))
