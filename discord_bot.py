from dico_token import Token
import discord
import asyncio
from discord.ext import commands
from functions import modify_msg_form, reset_roles, remove_reaction
from datetime import datetime, timedelta
from holidayskr import is_holiday

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.reactions = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

recruit_status = False
roles = [
    {"name": "함", "color": discord.Color.default()},
    {"name": "하면함", "color": discord.Color.default()},
    {"name": "안함", "color": discord.Color.default()},
]
voice_kick_roles = [
    {"name": "집중모드", "color": discord.Color.default()},
    {"name": "음성차단", "color": discord.Color.default()},
]
dos_count = {}
origin_message = ''
game_player = 0
bot_message_id = ''

@bot.command(name='모집종료')
async def end_recruitment(ctx):
    global recruit_status
    global bot_message_id
    global game_player
    global dos_count
    await reset_roles(roles, ctx)
    message = await ctx.channel.fetch_message(int(bot_message_id))
    await message.delete()
    recruit_status = False
    bot_message_id = ''
    game_player = 0
    dos_count = {}
    await ctx.send("모집이 종료되었습니다.")

@bot.command(name='모집')
async def recruit(ctx, game_name, num_players: int, deadline="?", meetup_time="?"):
    global origin_message
    global recruit_status
    global game_player
    global bot_message_id
    game_player = num_players
    if recruit_status:
        await ctx.send("이미 모집이 시작되었습니다. 이전 모집을 종료하고 다시 시도해주세요: !모집종료")
        return

    origin_message = (
            f"{ctx.guild.default_role.mention}\n"
            f"{ctx.author.mention}님이 "
            f"모집을 시작합니다!\n\n"
            f"**게임명:** {game_name}\n"
            f"**인원 수:** {num_players}\n"
            f"**마감 시간:** {deadline}\n"
            f"**모임 시간:** {meetup_time}\n\n"
            f"참여를 원하시면 반응 이모지를 눌러주세요!"
        )
    hmh_emoji = discord.utils.get(ctx.guild.emojis, name="hmh")
    msg = await ctx.send(origin_message)
    if hmh_emoji:
        await msg.add_reaction("✅")
        await msg.add_reaction(hmh_emoji)
        await msg.add_reaction("❌")
    else:
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
    recruit_status = True
    bot_message_id = msg.id

@bot.command(name='모임')
async def meetup(ctx):
    global roles
    global bot_message_id
    if not recruit_status:
        await ctx.send("모집이 시작되지 않았습니다.")
        return
    message = await ctx.channel.fetch_message(int(bot_message_id))
    target_role = [discord.utils.get(ctx.guild.roles, name=role["name"]) for role in roles]
    #타겟 역할 멤버 닉네임 목록
    hmh_emoji = discord.utils.get(ctx.guild.emojis, name="hmh")
    members_role_1 = [member.mention for member in target_role[0].members] if target_role[0].members else []
    if hmh_emoji:
        members_role_2 = [member.mention for member in target_role[1].members] if target_role[1].members else []
        temp = f"{target_role[0].mention} : {', '.join(members_role_1)}\n{target_role[1].mention} : {', '.join(members_role_2)}\n"
    else:
        temp = f"{target_role[0].mention} : {', '.join(members_role_1)}\n"
    await ctx.send(f"{temp}모집이 완료되었습니다.\n\n!모임 으로 다시 멘션이 가능합니다.\n!모집종료 명령어로 모임 완료시 모집을 종료하세요.")
    print('모집 완료')

@bot.command(name='재전송')
#원래 메시지를 삭제하고 다시 생성
async def resend(ctx):
    global origin_message
    global bot_message_id
    global roles
    global game_player
    global dos_count
    message = await ctx.channel.fetch_message(int(bot_message_id))
    await message.delete()
    msg = await ctx.send(origin_message)
    hmh_emoji = discord.utils.get(ctx.guild.emojis, name="hmh")
    if hmh_emoji:
        await msg.add_reaction("✅")
        await msg.add_reaction(hmh_emoji)
        await msg.add_reaction("❌")
    else:
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
    bot_message_id = msg.id
    edit_message = await modify_msg_form(roles, msg)
    print(edit_message)
    await msg.edit(content=f"{origin_message}{edit_message}")

@bot.command(name='명령어')
async def help(ctx):
    await ctx.send(
        "!모집 [게임명] [인원수] \{마감시간\} \{모임시간\} : 모집을 시작합니다.\n"
        "!모집종료 : 모집을 종료합니다.\n"
        "!명령어 : 도움말을 출력합니다.\n"
        "!모임 : 모집이 완료된 경우 모임을 시작합니다.(멤버 멘션)\n"
        "!재전송 : 모집 메시지를 재전송합니다.\n"
    )
@bot.event
async def on_raw_reaction_add(payload):
    global origin_message
    if payload.member.bot:
        return
    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)

    if message.author == bot.user:
        member = message.guild.get_member(payload.user_id)
        #장난치는놈 경고
        dos_count[payload.user_id] = dos_count.get(payload.user_id, 0) + 1
        if dos_count[payload.user_id] > 5:
            mention = f'<@{payload.user_id}>'
            await member.send(f'{mention} 고만해라')
            dos_count[payload.user_id] = 0
            return
        hmh_emoji = discord.utils.get(message.guild.emojis, name="hmh")
        #타겟 멤버 역할 초기화
        for role_data in roles:
            role_name = role_data["name"]
            role = discord.utils.get(message.guild.roles, name=role_name)
            if member in role.members:
                await member.remove_roles(role)
        if str(payload.emoji) == '✅':
            await remove_reaction(message, member, hmh_emoji, '❌')
            role = discord.utils.get(message.guild.roles, name=roles[0]["name"])
            await member.add_roles(role)
            print(f'{member.display_name}님이 모집에 참여를 선택하셨습니다.')
        elif str(payload.emoji) == str(hmh_emoji):
            await remove_reaction(message, member, '✅', '❌')
            role = discord.utils.get(message.guild.roles, name=roles[1]["name"])
            await member.add_roles(role)
            print(f'{member.display_name}님이 hmh를 선택하셨습니다.')
        elif str(payload.emoji) == '❌':
            await remove_reaction(message, member, '✅', hmh_emoji)
            role = discord.utils.get(message.guild.roles, name=roles[2]["name"])
            await member.add_roles(role)
            print(f'{member.display_name}님이 모집에 불참을 선택하셨습니다.')
        await asyncio.sleep(0.5)
        edit_message = await modify_msg_form(roles, message)
        await message.edit(content=f"{origin_message}{edit_message}")
        target_role = [discord.utils.get(message.guild.roles, name=role["name"]) for role in roles]
        join_count = len(target_role[0].members) + len(target_role[1].members)
        if join_count >= game_player:
            hmh_emoji = discord.utils.get(ctx.guild.emojis, name="hmh")
            members_role_1 = [member.mention for member in target_role[0].members] if target_role[0].members else []
            if hmh_emoji:
                members_role_2 = [member.mention for member in target_role[1].members] if target_role[1].members else []
                temp = f"{target_role[0].mention} : {', '.join(members_role_1)}\n{target_role[1].mention} : {', '.join(members_role_2)}\n"
            else:
                temp = f"{target_role[0].mention} : {', '.join(members_role_1)}\n"
            await ctx.send(f"{temp}모집이 완료되었습니다.\n\n!모임 으로 다시 멘션이 가능합니다.\n!모집종료 명령어로 모임 완료시 모집을 종료하세요.")
            print('모집 완료')

@bot.event
async def on_raw_reaction_remove(payload):
    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    global origin_message
    if message.author == bot.user:
        member = message.guild.get_member(payload.user_id)
        hmh_emoji = discord.utils.get(message.guild.emojis, name="hmh")
        if str(payload.emoji) == '✅':
            role = discord.utils.get(message.guild.roles, name=roles[0]["name"])
            await member.remove_roles(role)
            print(f'{member.display_name}님이 모집 참여를 취소하셨습니다.')
        elif str(payload.emoji) == str(hmh_emoji):
            role = discord.utils.get(message.guild.roles, name=roles[1]["name"])
            await member.remove_roles(role)
            print(f'{member.display_name}님이 hmh 선택을 취소하셨습니다.')
        elif str(payload.emoji) == '❌':
            role = discord.utils.get(message.guild.roles, name=roles[2]["name"])
            await member.remove_roles(role)
            print(f'{member.display_name}님이 모집 불참을 취소하셨습니다.')
        await asyncio.sleep(0.5)
        edit_message = await modify_msg_form(roles, message)
        await message.edit(content=f"{origin_message}{edit_message}")

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

#서버에서 나가면 역할 삭제
@bot.event
async def on_guild_remove(guild):
    role_list = roles + voice_kick_roles
    for role_data in role_list:
        role_name = role_data["name"]
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            await role.delete()
            print(f"역할 '{role_name}'이 삭제되었습니다.")

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
        if today_day == 5 or today_day == 6 or check_holiday:
            print('주말 및 공휴일')
        elif '집중모드' in role_names and 18>current_hour:
            await member.move_to(None)
            print('집중모드로 인한 음성채널 추방')

#역할생성 명령어
@bot.command(name='역할생성')
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
