from dico_token import Token
import discord
import asyncio
import json
from discord.ext import commands
from functions import modify_msg_form, reset_roles, remove_reaction
from datetime import datetime, timedelta
from holidayskr import is_holiday
from discord.ui import Modal, TextInput, View, Button, Select
import sqlite3

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.reactions = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

conn = sqlite3.connect('recruit_bot.db')
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS channel_access (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id INTEGER NOT NULL,
    access_channel_id INTEGER NOT NULL,
    access_message_id INTEGER NOT NULL,
    target_channel_id INTEGER NOT NULL
)
''')
conn.commit()

recruit_status = False
roles = [
    {"name": "참여", "color": discord.Color.default(), "emoji": "✅"},
    {"name": "불참", "color": discord.Color.default(), "emoji": "❌"},
]
voice_kick_roles = [
    {"name": "집중모드", "color": discord.Color.default()},
    {"name": "음성차단", "color": discord.Color.default()},
]
dos_count = {}
origin_message = ''
recruit_message_id = ''
recruit_user = ''
game_name = ''
recruit_num = 0
meetup_time = ''
deadline = ''
warning_message = {
    6: "그만눌러라",
    10: "야야",
    15: "야이 시발련아",
}
def recruit_msg_form(mention, recruit_user, game_name, recruit_num, meetup_time, deadline):
    temp = (
        f"{mention}\n"
        f"{recruit_user}님이 "
        f"모집을 시작합니다!\n\n"
        f"**게임명:** {game_name}\n"
        f"**인원 수:** {recruit_num}\n"
        f"{meetup_time}"
        f"{deadline}\n"
        f"참여를 원하시면 반응 이모지를 눌러주세요!"
    )
    return temp

class MyModal(Modal):
    def __init__(self, original_interaction: discord.Interaction, game_info: dict):
        super().__init__(title="모집 입력 양식")
        self.original_interaction = original_interaction
        self.game_info = game_info
        self.meetup_time_input = TextInput(label="모임 시간(선택)", placeholder="모임 시간 입력", required=False,style=discord.TextStyle.short)
        self.add_item(self.meetup_time_input)
        self.deadline_input = TextInput(label="마감 시간(선택)", placeholder="마감 시간 입력", required=False, style=discord.TextStyle.short)
        self.add_item(self.deadline_input)

    async def on_submit(self, interaction: discord.Interaction):
        global recruit_message_id
        global origin_message
        global game_name
        global recruit_num
        global meetup_time
        global deadline
        game_name = self.game_info["label"]
        recruit_num = self.game_info["value"]
        meetup_time = f'**모임 시간:** {self.meetup_time_input.value}\n' if self.meetup_time_input.value else ''
        deadline = f'**마감 시간:** {self.deadline_input.value}\n' if self.deadline_input.value else ''
        #입력 버튼 삭제
        await self.original_interaction.message.delete()
        #모집한 사람한테 메시지 보내기
        await interaction.response.send_message("모집이 시작되었습니다!", ephemeral=True)
        #모집 메시지 생성
        role = discord.utils.get(self.original_interaction.guild.roles, name='온라인')
        mention = role.mention if role else self.original_interaction.guild.default_role.mention
        origin_message = recruit_msg_form(mention, self.original_interaction.user.mention, game_name, recruit_num, meetup_time, deadline)
        message = await interaction.channel.send(f"{origin_message}")
        recruit_message_id = message.id
        role = discord.utils.get(message.guild.roles, name=roles[0]["name"])
        await self.original_interaction.user.add_roles(role)
        await message.add_reaction("✅")
        await message.add_reaction("❌")


class MyView(View):
    def __init__(self):
        super().__init__()

        options = [
            {"label": "롤 자랭", "description": "5명 모집", "value": 5},
            {"label": "배그 스쿼드", "description": "4명 모집", "value": 4},
            {"label": "롤 내전", "description": "10명 모집", "value": 10},
        ]

        select_options = [
            discord.SelectOption(label=opt["label"], description=opt["description"], value=json.dumps(opt))
            for opt in options
        ]

        self.select = Select(
            placeholder="게임 타입 선택",
            options=select_options,
            custom_id="game_type_select"
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        game_info = json.loads(self.select.values[0])
        modal = MyModal(original_interaction=interaction, game_info=game_info)
        await interaction.response.send_modal(modal)

@bot.command(name='모집종료')
async def end_recruitment(ctx):
    global recruit_status
    global recruit_message_id
    global game_player
    global dos_count
    user = ctx.author
    if user != recruit_user and not ctx.author.guild_permissions.administrator:
        await ctx.send("모집자만 종료할 수 있습니다.")
        return
    await reset_roles(roles, ctx)
    message = await ctx.channel.fetch_message(int(recruit_message_id))
    await message.delete()
    recruit_status = False
    recruit_message_id = ''
    game_player = 0
    dos_count = {}
    await ctx.send("모집이 종료되었습니다.")

@bot.command(name='모집')
async def recruit(ctx):
    global recruit_status
    if recruit_status:
        await ctx.send("이미 모집이 시작되었습니다. 이전 모집을 종료하고 다시 시도해주세요: !모집종료")
        return
    view = MyView()
    await ctx.send("버튼을 눌러 모집 양식을 입력해주세요.", view=view)
    recruit_status = True

@bot.command(name='모임')
async def meetup(ctx):
    global roles
    global recruit_message_id
    if not recruit_status:
        await ctx.send("모집이 시작되지 않았습니다.")
        return
    message = await ctx.channel.fetch_message(int(recruit_message_id))
    target_role = [discord.utils.get(ctx.guild.roles, name=role["name"]) for role in roles]
    #타겟 역할 멤버 닉네임 목록
    members_role_1 = [member.mention for member in target_role[0].members] if target_role[0].members else []
    temp = f"{target_role[0].mention} : {', '.join(members_role_1)}\n"
    await ctx.send(f"{temp}모집이 완료되었습니다.\n\n!모임 으로 다시 멘션이 가능합니다.\n!모집종료 명령어로 모임 완료시 모집을 종료하세요.")
    print('모집 완료')

@bot.command(name='재전송')
#원래 메시지를 삭제하고 다시 생성
async def resend(ctx):
    global origin_message
    global recruit_message_id
    global roles
    global game_player
    global dos_count
    message = await ctx.channel.fetch_message(int(recruit_message_id))
    await message.delete()
    msg = await ctx.send(origin_message)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    recruit_message_id = msg.id
    edit_message = await modify_msg_form(roles, msg)
    print(edit_message)
    await msg.edit(content=f"{origin_message}{edit_message}")

@bot.command(name='명령어')
async def help(ctx):
    await ctx.send(
        "!모집 : 모집 양식을 입력할 수 있는 버튼 메시지를 보냅니다.\n"
        "!모집종료 : 모집을 종료합니다.\n"
        "!명령어 : 도움말을 출력합니다.\n"
        "!모임 : 모집이 완료된 경우 모임을 시작합니다.(멤버 멘션)\n"
        "!재전송 : 모집 메시지를 재전송합니다.\n\n"
        "관리자 명령어\n"
        "!역할생성 : 봇에서 사용하는 역할을 생성합니다.\n"
        "!역할삭제 : 봇에서 사용하는 역할을 삭제합니다.\n"
        "!채널생성 [채널명] : 권한 부여 채널을 생성합니다.\n"
        "!메시지생성 [대상채널명] : 대상 채널에 권한 부여 메시지를 생성합니다.\n"
        "!메시지삭제 [대상채널명] : 대상 채널에 권한 부여 메시지를 삭제합니다."
    )

@bot.event
async def on_raw_reaction_add(payload):
    global origin_message
    if payload.member.bot:
        return
    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    #모집 메시지 확인
    if message.id == recruit_message_id:
        member = message.guild.get_member(payload.user_id)
        #장난치는놈 경고
        dos_count[payload.user_id] = dos_count.get(payload.user_id, 0) + 1
        #경고 메시지 warning_message에 있는 횟수만큼 경고 메시지 출력
        if dos_count[payload.user_id] in warning_message:
            await message.channel.send(f"{member.mention} {warning_message[dos_count[payload.user_id]]}")
            if dos_count[payload.user_id] >= max(warning_message.keys()):
                dos_count[payload.user_id] = 0
        #타겟 멤버 역할 초기화
        for role_data in roles:
            role_name = role_data["name"]
            role = discord.utils.get(message.guild.roles, name=role_name)
            if member in role.members:
                await member.remove_roles(role)
        if str(payload.emoji) == '✅':
            await remove_reaction(message, member, '❌')
            role = discord.utils.get(message.guild.roles, name=roles[0]["name"])
            await member.add_roles(role)
            print(f'{member.display_name}님이 모집에 참여를 선택하셨습니다.')
        elif str(payload.emoji) == '❌':
            await remove_reaction(message, member, '✅')
            role = discord.utils.get(message.guild.roles, name=roles[1]["name"])
            await member.add_roles(role)
            print(f'{member.display_name}님이 모집에 불참을 선택하셨습니다.')
        else:
            await remove_reaction(message, member, str(payload.emoji), '')
        await asyncio.sleep(0.5)
        edit_message = await modify_msg_form(roles, message)
        await message.edit(content=f"{origin_message}{edit_message}")
        target_role = [discord.utils.get(message.guild.roles, name=role["name"]) for role in roles]
        join_count = len(target_role[0].members)
        if join_count == recruit_num:
            members_role_1 = [member.mention for member in target_role[0].members] if target_role[0].members else []
            if members_role_1 == []:
                role1 = ''
            else:
                role1 = f"{target_role[0].mention} : {', '.join(members_role_1)}\n"
            await channel.send(f"{role1}모집이 완료되었습니다.\n\n!모임 으로 다시 멘션이 가능합니다.\n!모집종료 명령어로 모임 완료시 모집을 종료하세요.")
            print('모집 완료')
    #권한 부여 메시지
    else:
        if str(payload.emoji) == '✅':
            #db에서 access channel, id 검색
            cursor.execute('''
            SELECT * FROM channel_access 
            WHERE access_message_id = ? AND access_channel_id = ?
            ''', (payload.message_id, payload.channel_id))
            db = cursor.fetchone()
            if db:
                target_channel = bot.get_channel(int(db[4]))
                member = message.guild.get_member(payload.user_id)
                await target_channel.set_permissions(member, read_messages=True)
                print(f'{member.display_name}님이 {target_channel.name}채널 접근 권한을 부여하셨습니다.')

@bot.event
async def on_raw_reaction_remove(payload):
    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    global origin_message
    #모집 메시지
    if message.id == recruit_message_id:
        member = message.guild.get_member(payload.user_id)
        if str(payload.emoji) == '✅':
            role = discord.utils.get(message.guild.roles, name=roles[0]["name"])
            await member.remove_roles(role)
            print(f'{member.display_name}님이 모집 참여를 취소하셨습니다.')
        elif str(payload.emoji) == '❌':
            role = discord.utils.get(message.guild.roles, name=roles[1]["name"])
            await member.remove_roles(role)
            print(f'{member.display_name}님이 모집 불참을 취소하셨습니다.')
        await asyncio.sleep(0.5)
        edit_message = await modify_msg_form(roles, message)
        await message.edit(content=f"{origin_message}{edit_message}")
    #권한 부여 메시지
    else:
        if str(payload.emoji) == '✅':
            #db에서 access channel, id 검색
            cursor.execute('''
            SELECT * FROM channel_access 
            WHERE access_message_id = ? AND access_channel_id = ?
            ''', (payload.message_id, payload.channel_id))
            db = cursor.fetchone()
            if db:
                target_channel = bot.get_channel(int(db[4]))
                member = message.guild.get_member(payload.user_id)
                await target_channel.set_permissions(member, read_messages=False)
                print(f'{member.display_name}님이 {target_channel.name}채널 접근 권한을 취소하셨습니다.')



#서버에 들어오면 역할 생성
@bot.event
async def on_guild_join(guild):
    role_list = roles + voice_kick_roles
    for role_data in role_list:
        role_name = role_data["name"]
        color = role_data["color"]
        existing_role = discord.utils.get(guild.roles, name=role_name)
        if existing_role:
            print(f"역할 '{role_name}'가 사용중입니다. 봇에서 사용하는 역할과 중복될 수 있습니다.")
        else:
            await guild.create_role(name=role_name, color=color)
            print(f"역할 '{role_name}'이 생성되었습니다.")

#집중모드 역할을 가진 유저가 음성채널에 들어오면 추방
#주말 및 공휴일은 제외
#18시 이전에만 추방
#=============================
#데이터베이스 추가하여 개인별로 설정할 수 있도록 변경
#=============================
@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel is None and after.channel is not None:  # 유저가 보이스 채널에 들어옴
        role_names = [role.name for role in member.roles]
        current_time = datetime.now().strftime("%Y-%m-%d")
        current_hour = datetime.now().hour
        check_holiday = is_holiday(current_time)
        today_day = datetime.today().weekday()
        if today_day == 5 or today_day == 6 or check_holiday: #주말, 공휴일
            print('주말 및 공휴일')
        elif '집중모드' in role_names and 18>current_hour:
            await member.move_to(None)
        if '음성차단' in role_names:
            await member.move_to(None)
            print('집중모드로 인한 음성채널 추방')

#================================================================================================
#텍스트 채널 권한 부여 명령어
#================================================================================================
#권한 부여 채널 생성
@bot.command(name='채널생성')
@commands.has_permissions(administrator=True)
async def create_access_channel(ctx, *, channel_name: str):
    guild = ctx.guild
    channel = await guild.create_text_channel(channel_name)
    #비공개 채널 설정
    await channel.set_permissions(guild.default_role, send_messages=False)
    await ctx.send(f"채널 '{channel.name}'이 생성되었습니다.")

#권한 부여 메시지 생성
@bot.command(name='메시지생성')
@commands.has_permissions(administrator=True)
async def set_target_channel(ctx, target_channel: str):
    #대상 채널이 존재하는지 확인
    target_channel_id = ''
    for channel in ctx.guild.channels:
        if channel.name == target_channel:
            target_channel_id = channel.id
            break
    if target_channel_id == '':
        await ctx.send(f"채널 '{target_channel}'이 존재하지 않습니다.")
    #존재하면 메시지 생성, 데이터베이스에 저장
    else:
        message = await ctx.send(f"__**{target_channel}**__ 채널 권한 부여를 위해 아래 이모지를 눌러주세요.")
        await message.add_reaction("✅")
        cursor.execute(f'''
        INSERT INTO channel_access (server_id, access_channel_id, access_message_id, target_channel_id)
        VALUES ('{ctx.guild.id}', '{ctx.channel.id}', '{message.id}', '{target_channel_id}')
        ''')
        conn.commit()
        #명령어 메시지 삭제
        await ctx.message.delete()

#권한 부여 메시지 삭제
@bot.command(name='메시지삭제')
@commands.has_permissions(administrator=True)
async def delete_target_channel(ctx, target_channel: str):
    #대상 채널이 존재하는지 확인
    target_channel_id = ''
    for channel in ctx.guild.channels:
        if channel.name == target_channel:
            target_channel_id = channel.id
            break
    if target_channel_id == '':
        await ctx.send(f"채널 '{target_channel}'이 존재하지 않습니다.")
        return
    #존재하면 메시지 삭제, 데이터베이스에서 삭제
    cursor.execute('''
    SELECT * FROM channel_access
    WHERE access_channel_id = ? AND target_channel_id = ?
    ''', (ctx.channel.id, target_channel_id))
    db = cursor.fetchone()
    if db:
        print(db)
        message = await ctx.channel.fetch_message(db[3])
        await message.delete()
        cursor.execute('''
        DELETE FROM channel_access
        WHERE access_message_id = ?
        ''', (db[3],))
        conn.commit()
        #명령어 메시지 삭제
        await ctx.message.delete()

#================================================================================================
#역할생성 명령어
@bot.command(name='역할생성')
@commands.has_permissions(administrator=True)
async def create_role(ctx):
    role_list = roles + voice_kick_roles
    fail_list = []
    success_list = []
    msg = ''
    for role_data in role_list:
        role_name = role_data["name"]
        color = role_data["color"]
        existing_role = discord.utils.get(ctx.guild.roles, name=role_name)
        if existing_role:
            fail_list.append(role_name)
        else:
            await ctx.guild.create_role(name=role_name, color=color)
            success_list.append(role_name)
    if fail_list:
        msg += f"역할 '{', '.join(fail_list)}'가 이미 사용중입니다. 역할을 삭제 후 다시 시도해주세요.\n"
    if success_list:
        msg += f"역할 '{', '.join(success_list)}'이 생성되었습니다."
    await ctx.send(msg)

#역할삭제 명령어
@bot.command(name='역할삭제')
@commands.has_permissions(administrator=True)
async def delete_role(ctx):
    role_list = roles + voice_kick_roles
    fail_list = []
    success_list = []
    msg = ''
    for role_data in role_list:
        role_name = role_data["name"]
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if role:
            try:
                await role.delete()
                success_list.append(role_name)
            except:
                fail_list.append(role_name)
        else:
            fail_list.append(role_name)
    if fail_list:
        msg += f"역할 '{', '.join(fail_list)}'가 존재하지 않거나 삭제를 실패하였습니다.\n"
    if success_list:
        msg += f"역할 '{', '.join(success_list)}'이 삭제되었습니다."
    await ctx.send(msg)

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name="!명령어"))
    print('Bot is ready')

bot.run(Token)
