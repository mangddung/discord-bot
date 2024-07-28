from dico_token import Token
import asyncio
import json
import discord
from discord.ext import commands
from discord.ui import Modal, TextInput, View, Button, Select
from functions import modify_msg_form, reset_roles, remove_reaction
from datetime import datetime, timedelta
import pytz
from holidayskr import is_holiday
import sqlite3
import logging

logging.basicConfig(
    level=logging.DEBUG,  # 필요한 로그 레벨로 설정합니다. 예: DEBUG, INFO, WARNING, ERROR, CRITICAL
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("discord_bot.log"),  # 로그 파일 이름을 지정합니다.
        logging.StreamHandler()  # 콘솔에 로그를 출력하려면 이 핸들러를 추가합니다.
    ]
)

logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.reactions = True
intents.voice_states = True
intents.guild_messages = True  # 메시지 관련 이벤트를 감지하도록 합니다
intents.guild_reactions = True  # 리액션 관련 이벤트를 감지하도록 합니다

bot = commands.Bot(command_prefix='!', intents=intents)

tz = pytz.timezone('Asia/Seoul')

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
cursor.execute('''
CREATE TABLE IF NOT EXISTS guest_invite_code (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id INTEGER NOT NULL,
    invite_code TEXT NOT NULL,
    inviter_id INTEGER NOT NULL,
    inviter_name TEXT NOT NULL,
    target_channel_id INTEGER NOT NULL,
    target_user_id INTEGER,
    created_at TIMESTAMP,
    joined_at TIMESTAMP
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
guest_role = [{"name": "손님", "color": discord.Color.default(), "hoist": True}]

dos_count = {}
invite_tracker = {}
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
    try:
        message = await ctx.channel.fetch_message(int(recruit_message_id))
        await message.delete()
    except:
        recruit_message_id = ''
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
                await target_channel.set_permissions(member, send_messages=True)
                logging.info(f'{member.display_name}님이 {target_channel.name}채널 접근 권한을 부여하셨습니다.')

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
                await target_channel.set_permissions(member, send_messages=False)
                logging.info(f'{member.display_name}님이 {target_channel.name}채널 접근 권한을 취소하셨습니다.')


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
    await channel.set_permissions(guild.default_role, read_messages=False)
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
        try:
            message = await ctx.send(f"__**{target_channel}**__ 채널 권한 부여를 위해 아래 이모지를 눌러주세요.")
            await message.add_reaction("✅")
            cursor.execute(f'''
            INSERT INTO channel_access (server_id, access_channel_id, access_message_id, target_channel_id)
            VALUES ('{ctx.guild.id}', '{ctx.channel.id}', '{message.id}', '{target_channel_id}')
            ''')
            conn.commit()
            #명령어 메시지 삭제
            await ctx.message.delete()
            logging.info(f'{ctx.author.display_name}님이 {target_channel} 채널 권한 부여 메시지 생성')
        except:
            logging.info(f'{ctx.author.display_name}님이 {target_channel} 채널 권한 부여 메시지 생성 실패')
            ctx.send(f"채널 '{target_channel}' 권한 부여 메시지 생성 실패")

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
        try:
            message = await ctx.channel.fetch_message(db[3])
            await message.delete()
            cursor.execute('''
            DELETE FROM channel_access
            WHERE access_message_id = ?
            ''', (db[3],))
            conn.commit()
            #명령어 메시지 삭제
            await ctx.message.delete()
            logging.info(f'{ctx.author.display_name}님이 {target_channel} 채널 권한 부여 메시지 삭제')
        except:
            logging.info(f'{ctx.author.display_name}님이 {target_channel} 채널 권한 부여 메시지 삭제 실패')
            ctx.send(f"채널 '{target_channel}' 권한 부여 메시지 삭제 실패")

#================================================================================================
#역할생성 명령어
@bot.command(name='역할생성')
@commands.has_permissions(administrator=True)
async def create_role(ctx):
    role_list = roles + voice_kick_roles + guest_role
    fail_list = []
    success_list = []
    msg = ''
    for role_data in role_list:
        role_name = role_data["name"]
        color = role_data["color"]
        existing_role = discord.utils.get(ctx.guild.roles, name=role_name)
        if existing_role:
            fail_list.append(role_name)
        else: #손님 역할 생성 시 hoist 옵션 추가
            if role_name in guest_role[0]["name"]: #손님 역할 생성 및 권한 설정
                try:
                    await ctx.guild.create_role(name=role_name, color=color, hoist=guest_role[0]["hoist"])
                    role = discord.utils.get(ctx.guild.roles, name=role_name)
                    channels = ctx.guild.channels
                    for channel in channels:
                        if isinstance(channel, discord.TextChannel):
                            try:
                                await channel.set_permissions(role, read_messages=False)
                            except:
                                logging.error(f'{role_name} 역할의 {channel.name} 텍스트 채널 권한 거부 실패')
                        elif isinstance(channel, discord.VoiceChannel):
                            try:
                                await channel.set_permissions(role, view_channel=False)
                            except:
                                logging.error(f'{role_name} 역할의 {channel.name} 음성 채널 권한 거부 실패')
                    success_list.append(role_name)
                except:
                    fail_list.append(role_name)
            else:
                try:
                    await ctx.guild.create_role(name=role_name, color=color)
                    success_list.append(role_name)
                except:
                    fail_list.append(role_name)
            
    
    if fail_list:
        msg += f"역할 '{', '.join(fail_list)}'가 이미 사용중입니다. 역할을 삭제 후 다시 시도해주세요.\n"
        logging.error(f'역할 생성 실패: {fail_list}')
    if success_list:
        msg += f"역할 '{', '.join(success_list)}'이 생성되었습니다."
        logging.info(f'역할 생성 성공: {success_list}')
    await ctx.send(msg)

#역할삭제 명령어
@bot.command(name='역할삭제')
@commands.has_permissions(administrator=True)
async def delete_role(ctx):
    role_list = roles + voice_kick_roles + guest_role
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

#게스트 초대 코드 명령어
@bot.command(name='게스트')
async def guest(ctx):
    check_guest_role = discord.utils.get(ctx.guild.roles, name=guest_role[0]["name"])
    if not check_guest_role:
        await ctx.send("게스트 역할이 존재하지 않습니다. 관리자에게 문의해주세요.")
        return
    role = discord.utils.get(ctx.guild.roles, name='온라인')
    if not role:
        await ctx.send("온라인 역할이 존재하지 않습니다. 관리자에게 문의해주세요.")
        return
    user_roles = ctx.author.roles[1:] #사용자 역할 목록
    if role in user_roles:
        author_voice_state = ctx.author.voice
        if author_voice_state and author_voice_state.channel:
            voice_channel = author_voice_state.channel
            try:
                guest_max_age = 30
                guest_max_uses = 1
                invite = await voice_channel.create_invite(max_age=guest_max_age*60, max_uses=guest_max_uses, unique=True)
                await ctx.author.send(f"{voice_channel} 음성 채널 초대 링크: {invite.url}")
                await ctx.send(f"{ctx.author.mention}, DM으로 초대 링크를 보냈습니다. 해당 링크는 {guest_max_age}분간 {guest_max_uses}번 사용 가능합니다.")
                current_time = datetime.now(tz)
                cursor.execute(f'''
                INSERT INTO guest_invite_code (server_id, invite_code, inviter_id, inviter_name, target_channel_id, created_at)
                VALUES ('{ctx.guild.id}', '{invite.url[19:]}', '{ctx.author.id}', '{ctx.author.name}', '{voice_channel.id}', '{current_time}')
                ''')
                conn.commit()
                logger.info(f'{ctx.author.display_name}님이 {voice_channel.name} 음성 채널에 손님 초대 링크를 생성')
            except:
                await ctx.send(f"{ctx.author.mention}, 초대 링크 생성에 실패하였습니다.")
                logger.error(f'{ctx.author.display_name}님이 {voice_channel.name} 음성 채널에 손님 초대 링크 생성 실패')
        else:
            await ctx.send(f"{ctx.author.mention}, 먼저 음성 채널에 입장해주세요.")
    else:
        await ctx.send('온라인 역할이 있는 유저만 명령어 사용이 가능합니다.')

#초대 코드 생성, 삭제 이벤트           
@bot.event
async def on_invite_create(invite):
    invites = await invite.guild.invites()
    invite_tracker[invite.guild.id] = {inv.code: inv.uses for inv in invites}

@bot.event
async def on_invite_delete(invite):
    invites = await invite.guild.invites()
    invite_tracker[invite.guild.id] = {inv.code: inv.uses for inv in invites}

#멤버 서버 입장 이벤트(게스트 확인 후 처리 로직)
@bot.event
async def on_member_join(member):
    guild = member.guild
    invites_before_join = invite_tracker[guild.id]
    invites_after_join = await guild.invites()
    
    # 업데이트된 초대 코드 목록을 저장
    invite_tracker[guild.id] = {invite.code: invite.uses for invite in invites_after_join}

    used_invite_code = None
    inviter = None

    # 사용된 초대 코드를 찾기 위한 로직
    for invite in invites_after_join:
        if invite.code in invites_before_join:
            if invites_before_join[invite.code] < invite.uses:
                used_invite_code = invite.code
                inviter = invite.inviter
                break

    # 만약 초대 코드가 사용된 후 사라졌다면, 이전 목록에서 제거된 코드를 찾아냅니다.
    if not used_invite_code:
        used_invites = set(invites_before_join.keys()) - set(invite_tracker[guild.id].keys())
        if used_invites:
            used_invite_code = used_invites.pop()
            inviter = None  # 초대한 사람을 확인할 수 없음

    #게스트 초대 확인 로직
    if used_invite_code:
        cursor.execute('''
        SELECT * FROM guest_invite_code
        WHERE server_id = ? AND invite_code = ?
        ''', (guild.id, used_invite_code))
        db = cursor.fetchone()
        if db:
            inviter_id = db[3]
            inviter_name = db[4]
            target_channel_id = db[5]
            #초대된 멤버 id db에 저장
            try:
                current_time = datetime.now(tz)
                cursor.execute(f'''
                UPDATE guest_invite_code
                SET target_user_id = '{member.id}', joined_at = '{current_time}'
                WHERE server_id = '{guild.id}' AND invite_code = '{used_invite_code}'
                ''')
                conn.commit()
                try:
                    await member.add_roles(discord.utils.get(guild.roles, name=guest_role[0]["name"]))
                    target_channel = bot.get_channel(target_channel_id)
                    if target_channel:
                        try:
                            await target_channel.set_permissions(member, connect=True)
                        except Exception as e:
                            logging.error(f'{member.display_name}님의 음성 채널 접근 권한 부여 실패')
                except:
                    logging.error(f'{member.display_name}님의 게스트 역할 부여 실패')
                    member.guild.system_channel.send(f"{member.display_name}님의 게스트 역할 부여 실패")
                    await member.ban(reason='권한 설정 실패로 추방')
                    await member.unban()
            except:
                logging.error('게스트 정보 DB 업데이트 실패')
            #inviter_id로 초대한 사람 닉네임 찾기
            inviter = guild.get_member(inviter_id)
            if inviter:
                await member.guild.system_channel.send(f"{member.mention}님이 , {inviter.mention}님의 손님 초대로 서버에 입장하셨습니다.")
                member_name = member.display_name
                await member.edit(nick=f'{member_name}(손님)')
                logging.info(f'{member.display_name}님이 {inviter.name}님의 손님 초대로 서버에 입장하셨습니다.')
            else:
                await member.guild.system_channel.send(f"{member.mention}님이 , {inviter_name}님의 손님 초대로 서버에 입장하셨습니다.")
        else:
            logging.info(f'{member.display_name}님이 {inviter}님의 일반 초대 코드로 서버에 입장하셨습니다.')


#보이스 채널 떠날 때 이벤트(게스트 추방)
@bot.event
async def on_voice_state_update(member, before, after):
    user_roles = member.roles[1:] #사용자 역할 목록
    if discord.utils.get(member.guild.roles, name=guest_role[0]["name"]) not in user_roles:
        return
    if before.channel is not None and after.channel is None:
        try:
            cursor.execute('''
            SELECT * FROM guest_invite_code
            WHERE server_id = ? AND target_user_id = ?
            ''', (member.guild.id, member.id))
            dbs = cursor.fetchall()
            if dbs:
                for db in dbs:
                    target_channel = bot.get_channel(int(db[5]))
                    if before.channel.id == target_channel.id:
                        await member.ban(reason='게스트 추방')
                        await member.unban()
                        cursor.execute('''
                        DELETE FROM guest_invite_code
                        WHERE server_id = ? AND target_user_id = ?
                        ''', (member.guild.id, db[6]))
                        conn.commit()
                        logging.info(f'{member.display_name}님의 게스트 추방, DB삭제 성공')
        except:
            await member.default_channel.send(f"{member.display_name}님의 게스트 추방 실패 관리자 확인 바람")
            logging.error(f'{member.display_name}님의게스트 추방 실패')

#채널 생성 이벤트(게스트 권한 설정)
@bot.event
async def on_guild_channel_create(channel):
    role = discord.utils.get(channel.guild.roles, name=guest_role[0]["name"])
    # 채널 생성 이벤트가 호출될 때마다 이 함수가 실행됩니다
    if isinstance(channel, discord.TextChannel):
        try:
            await channel.set_permissions(role, read_messages=False)
            logging.info(f'{role.name} 역할의 {channel.name} 텍스트 채널 권한 거부 성공')
        except:
            logging.error(f'{role.name} 역할의 {channel.name} 텍스트 채널 권한 거부 실패')
    elif isinstance(channel, discord.VoiceChannel):
        try:
            await channel.set_permissions(role, view_channel=False)
            logging.info(f'{role.name} 역할의 {channel.name} 음성 채널 권한 거부 성공')
        except:
            logging.error(f'{role.name} 역할의 {channel.name} 음성 채널 권한 거부 실패')

@bot.command(name='명령어')
async def help(ctx):
    await ctx.send(
        "!모집 : 모집 양식을 입력할 수 있는 버튼 메시지를 보냅니다.\n"
        "!모집종료 : 모집을 종료합니다.\n"
        "!명령어 : 도움말을 출력합니다.\n"
        "!모임 : 모집이 완료된 경우 모임을 시작합니다.(멤버 멘션)\n"
        "!재전송 : 모집 메시지를 재전송합니다.\n\n"
        "!게스트 : 접속 중인 음성 채널에 손님 초대 링크를 생성합니다.\n\n"
        "관리자 명령어\n"
        "!역할생성 : 봇에서 사용하는 역할을 생성합니다.\n"
        "!역할삭제 : 봇에서 사용하는 역할을 삭제합니다.\n"
        "!채널생성 [채널명] : 권한 부여 채널을 생성합니다.\n"
        "!메시지생성 [대상채널명] : 대상 채널에 권한 부여 메시지를 생성합니다.\n"
        "!메시지삭제 [대상채널명] : 대상 채널에 권한 부여 메시지를 삭제합니다."
    )


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name="!명령어"))
    for guild in bot.guilds:
        invites = await guild.invites()
        invite_tracker[guild.id] = {invite.code: invite.uses for invite in invites}
    logging.info(f'{bot.user} has connected to Discord!')

bot.run(Token)
