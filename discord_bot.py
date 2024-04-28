from dico_token import Token
import discord
import asyncio
from discord.ext import commands
from functions import modify_msg_form, reset_roles, remove_reaction

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix='!', intents=intents)

recruit_status = False
roles = [
    {"name": "참여", "color": discord.Color.default()},
    {"name": "하면함", "color": discord.Color.default()},
    {"name": "불참", "color": discord.Color.default()}
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
async def recruit(ctx, game_name, num_players: int, deadline, meetup_time):
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
            f"{game_name} 모집을 시작합니다!\n\n"
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
        if dos_count[payload.user_id] > 8:
            mention = f'<@{payload.user_id}>'
            await member.send(f'{mention} 고만해라')
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
            members_role_1 = [member.display_name for member in target_role[0].members] if target_role[0].members else []
            members_role_2 = [member.display_name for member in target_role[1].members] if target_role[1].members else []
            join_list = ', '.join(members_role_1 + members_role_2)
            await channel.send(f"{target_role[0].mention} {target_role[1].mention} 모집이 완료되었습니다.\n 멤버: {join_list}\n !모집종료 명령어로 모집을 종료하세요.")
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
        edit_message = await modify_msg_form(roles, message)
        await message.edit(content=f"{origin_message}{edit_message}")

@bot.event
async def on_guild_join(guild):
    for role_data in roles:
        role_name = role_data["name"]
        color = role_data["color"]
        
        existing_role = discord.utils.get(guild.roles, name=role_name)
        if existing_role:
            print(f"'{role_name}' 역할은 이미 존재합니다.")
        else:
            role = await guild.create_role(name=role_name, color=color)
            print(f"역할 '{role_name}'이 생성되었습니다.")

@bot.event
async def on_ready():
    print('Bot is ready')

bot.run(Token)
