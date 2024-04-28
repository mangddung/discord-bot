import discord

async def modify_msg_form(roles, message):  
    role_name = [role["name"] for role in roles]
    edit_message = ''
    for name in role_name:
        role = discord.utils.get(message.guild.roles, name=name)
        member_count = len(role.members)
        member_list = ", ".join([member.display_name for member in role.members])
        if member_list == '':
            member_list = ''
        else:
            member_list = f'```{member_list}```'
        edit_message += f"\n**{name} ({member_count}명)**\n{member_list}"
    return edit_message

async def reset_roles(roles, ctx):
    for role_data in roles:
        role_name = role_data["name"]
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        for member in role.members:
            await member.remove_roles(role)

async def remove_reaction(message,member, emoji1,emoji2):
    await message.remove_reaction(emoji1, member)
    await message.remove_reaction(emoji2, member)
