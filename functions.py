import discord
from holidayskr import is_holiday
from datetime import datetime

async def modify_msg_form(roles, message):  
    role_name = [role["name"] for role in roles]
    edit_message = '\n'
    for name in role_name:
        role = discord.utils.get(message.guild.roles, name=name)
        member_count = len(role.members)
        member_list = ", ".join([member.display_name for member in role.members])
        if member_list == '':
            edit_message += ''
        else:
            edit_message += f"\n**{name} ({member_count}명)**\n```{member_list}```"
    return edit_message

async def reset_roles(roles, ctx):
    for role_data in roles:
        role_name = role_data["name"]
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        for member in role.members:
            await member.remove_roles(role)

async def remove_reaction(message,member, emoji):
    await message.remove_reaction(emoji, member)

def check_holiday(dt):
    if not isinstance(dt, datetime):
        raise TypeError("올바른 날짜 형식이 아닙니다.")
    holiday = is_holiday(dt.strftime("%Y-%m-%d")) #공휴일 확인
    week = dt.weekday() >= 5 #주말확인
    return holiday or week