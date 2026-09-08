import os
import json
import random
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# --- BRANDING & CONFIGURATION ---
GUILD_ID = 1522607630219087892             # Server ID
MODMAIL_CATEGORY_ID = 1540986934808027137  # Ticket Category ID
STAFF_ROLE_ID = 1546910653116190840        # Dedicated Staff Role ID for Replies/Commands

# Brand Settings
BRAND_NAME = "Montreo"
EMBED_COLOR = discord.Color.from_str("#D2B48C")  # Tan Color

# Custom Emojis
CONFIRM_EMOJI = discord.PartialEmoji(name="Tick", id=1546906830763196476)
CANCEL_EMOJI = discord.PartialEmoji(name="Cross", id=1546907243960860682)
REACTION_EMOJI = discord.PartialEmoji(name="MontreoReaction", id=1541442445097570375)

# Anonymous Staff Names for .areply
ANONYMOUS_AGENT_NAMES = [
    "Agent Alpha", "Agent Bravo", "Agent Charlie", 
    "Agent Delta", "Agent Echo"
]

# --- INTENTS SETUP ---
intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True
intents.guild_messages = True
intents.members = True

bot = commands.Bot(command_prefix=".", intents=intents)

# --- JSON DATA STORAGE HELPERS ---
def load_json(filename: str) -> dict:
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_json(filename: str, data: dict):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# Global Data Structures
SNIPPETS = load_json("snippets.json")
BANNED_USERS = load_json("banned_users.json")
SUBSCRIBERS = load_json("subscribers.json")


@bot.event
async def on_ready():
    print(f"✅ {BRAND_NAME} Chatbot active as {bot.user}")


# --- UI COMPONENTS FOR TICKET CREATION ---

class DepartmentSelect(discord.ui.Select):
    def __init__(self, initial_message: discord.Message):
        self.initial_message = initial_message
        options = [
            discord.SelectOption(label="Human Resources", value="Human Resources"),
            discord.SelectOption(label="Operations", value="Operations"),
            discord.SelectOption(label="Public Relations", value="Public Relations")
        ]
        super().__init__(placeholder="Select a department...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        selected_dept = self.values[0]
        guild = bot.get_guild(GUILD_ID)
        category = guild.get_channel(MODMAIL_CATEGORY_ID)
        staff_role = guild.get_role(STAFF_ROLE_ID)

        channel_name = f"ticket-{interaction.user.id}"
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        ticket_channel = await category.create_text_channel(name=channel_name, overwrites=overwrites)

        staff_ping = f"<@&{STAFF_ROLE_ID}>" if STAFF_ROLE_ID else ""

        staff_embed = discord.Embed(
            title=f"New {BRAND_NAME} Ticket Created",
            description=(
                f"**User:** {interaction.user.mention} (`{interaction.user.id}`)\n"
                f"**Department:** {selected_dept}\n"
                f"**Initial Message:**\n{self.initial_message.content}"
            ),
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )
        staff_embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await ticket_channel.send(content=staff_ping, embed=staff_embed)

        if self.initial_message.attachments:
            for attachment in self.initial_message.attachments:
                await ticket_channel.send(attachment.url)

        self.view.stop()


class DepartmentView(discord.ui.View):
    def __init__(self, initial_message: discord.Message):
        super().__init__(timeout=180)
        self.add_item(DepartmentSelect(initial_message))


class ConfirmationView(discord.ui.View):
    def __init__(self, initial_message: discord.Message):
        super().__init__(timeout=180)
        self.initial_message = initial_message

    @discord.ui.button(
        style=discord.ButtonStyle.secondary, 
        emoji=CONFIRM_EMOJI
    )
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        dept_embed = discord.Embed(
            description=(
                "**Department Selection**\n\n"
                "Before we create a ticket, please select a department "
                "you are opening a ticket for from the dropdown menu below."
            ),
            color=EMBED_COLOR
        )
        await interaction.response.send_message(embed=dept_embed, view=DepartmentView(self.initial_message))
        self.stop()

    @discord.ui.button(
        style=discord.ButtonStyle.secondary, 
        emoji=CANCEL_EMOJI
    )
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ Ticket creation cancelled.", ephemeral=False)
        self.stop()


# --- MESSAGE & EVENT HANDLING ---

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if isinstance(message.channel, discord.DMChannel):
        if str(message.author.id) in BANNED_USERS:
            await message.channel.send("You are currently blocked from creating support tickets.")
            return

        guild = bot.get_guild(GUILD_ID)
        if not guild:
            return

        category = guild.get_channel(MODMAIL_CATEGORY_ID)
        if not category:
            return

        channel_name = f"ticket-{message.author.id}"
        existing_channel = discord.utils.get(category.text_channels, name=channel_name)

        if existing_channel:
            dm_embed = discord.Embed(
                description=message.content,
                color=EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            dm_embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
            dm_embed.set_footer(text="User DM")

            if message.attachments:
                dm_embed.set_image(url=message.attachments[0].url)

            str_chan_id = str(existing_channel.id)
            pings = ""
            if str_chan_id in SUBSCRIBERS and SUBSCRIBERS[str_chan_id]:
                pings = " ".join([f"<@{uid}>" for uid in SUBSCRIBERS[str_chan_id]])

            await existing_channel.send(content=pings if pings else None, embed=dm_embed)
            await message.add_reaction(REACTION_EMOJI)
            return

        confirm_embed = discord.Embed(
            description=(
                f"**Almost There!**\n"
                f"-# Welcome to {BRAND_NAME} Support\n\n"
                f"Before proceeding, please confirm that you would like "
                f"to create a new support ticket with the {BRAND_NAME} team by reacting below."
            ),
            color=EMBED_COLOR
        )
        await message.channel.send(embed=confirm_embed, view=ConfirmationView(message))
        return

    await bot.process_commands(message)

    # 3. DYNAMIC SNIPPET TRIGGER (.snippet_name) INSIDE TICKETS
    if message.content.startswith(".") and message.channel.name.startswith("ticket-"):
        ctx = await bot.get_context(message)
        if ctx.valid:
            return

        # Check if author has the specific staff role
        if not isinstance(message.author, discord.Member) or not any(role.id == STAFF_ROLE_ID for role in message.author.roles):
            return

        trigger = message.content[1:].split()[0].lower()
        if trigger in SNIPPETS:
            user_id = int(message.channel.name.split("-")[1])
            target_user = await bot.fetch_user(user_id)
            snippet_text = SNIPPETS[trigger]

            roles = [r.name for r in message.author.roles if r.name != "@everyone"]
            agent_rank = roles[-1] if roles else "Support Agent"

            embed = discord.Embed(
                description=snippet_text,
                color=EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
            embed.set_footer(text=agent_rank)

            if target_user:
                try:
                    await target_user.send(embed=embed)
                except discord.HTTPException:
                    await message.channel.send("⚠️ Could not DM user (DMs may be closed).")
                    return

            await message.channel.send(embed=embed)
            try:
                await message.delete()
            except discord.Forbidden:
                pass


# --- STAFF CHECK PERMISSION (STRICT ROLE CHECK) ---

def is_staff():
    async def predicate(ctx):
        if not isinstance(ctx.author, discord.Member):
            return False
        # Strictly checks for role ID 1546910653116190840
        return any(role.id == STAFF_ROLE_ID for role in ctx.author.roles)
    return commands.check(predicate)


# --- STAFF TICKET COMMANDS ---

@bot.command(name="reply")
@is_staff()
async def reply(ctx, *, response: str):
    if not ctx.channel.name.startswith("ticket-"):
        return await ctx.send("This command can only be used inside a ticket channel.")

    user_id = int(ctx.channel.name.split("-")[1])
    target_user = await bot.fetch_user(user_id)

    roles = [r.name for r in ctx.author.roles if r.name != "@everyone"]
    agent_rank = roles[-1] if roles else "Support Agent"

    embed = discord.Embed(
        description=response,
        color=EMBED_COLOR,
        timestamp=discord.utils.utcnow()
    )
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    embed.set_footer(text=agent_rank)

    if target_user:
        try:
            await target_user.send(embed=embed)
        except discord.HTTPException:
            return await ctx.send("⚠️ Could not DM user.")

    await ctx.send(embed=embed)
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


@bot.command(name="areply")
@is_staff()
async def areply(ctx, *, response: str):
    if not ctx.channel.name.startswith("ticket-"):
        return await ctx.send("This command can only be used inside a ticket channel.")

    user_id = int(ctx.channel.name.split("-")[1])
    target_user = await bot.fetch_user(user_id)

    agent_name = random.choice(ANONYMOUS_AGENT_NAMES)

    embed = discord.Embed(
        description=response,
        color=EMBED_COLOR,
        timestamp=discord.utils.utcnow()
    )
    embed.set_author(name=f"Customer Support ({agent_name})")
    embed.set_footer(text=f"{BRAND_NAME} Helpdesk")

    if target_user:
        try:
            await target_user.send(embed=embed)
        except discord.HTTPException:
            return await ctx.send("⚠️ Could not DM user.")

    await ctx.send(embed=embed)
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


@bot.command(name="sub")
@is_staff()
async def sub(ctx):
    if not ctx.channel.name.startswith("ticket-"):
        return await ctx.send("This command can only be used inside a ticket channel.")

    chan_id = str(ctx.channel.id)
    if chan_id not in SUBSCRIBERS:
        SUBSCRIBERS[chan_id] = []

    if ctx.author.id not in SUBSCRIBERS[chan_id]:
        SUBSCRIBERS[chan_id].append(ctx.author.id)
        save_json("subscribers.json", SUBSCRIBERS)
        await ctx.send(f"✅ {ctx.author.mention} subscribed to this ticket.")
    else:
        await ctx.send("You are already subscribed to this ticket.")


@bot.command(name="unsub")
@is_staff()
async def unsub(ctx):
    if not ctx.channel.name.startswith("ticket-"):
        return await ctx.send("This command can only be used inside a ticket channel.")

    chan_id = str(ctx.channel.id)
    if chan_id in SUBSCRIBERS and ctx.author.id in SUBSCRIBERS[chan_id]:
        SUBSCRIBERS[chan_id].remove(ctx.author.id)
        save_json("subscribers.json", SUBSCRIBERS)
        await ctx.send(f"❌ {ctx.author.mention} unsubscribed from this ticket.")
    else:
        await ctx.send("You are not subscribed to this ticket.")


@bot.command(name="ban")
@is_staff()
async def ban_user(ctx, user: discord.User):
    BANNED_USERS[str(user.id)] = True
    save_json("banned_users.json", BANNED_USERS)
    
    embed = discord.Embed(
        description=f"🚫 User {user.mention} (`{user.id}`) has been banned from opening tickets.",
        color=EMBED_COLOR
    )
    await ctx.send(embed=embed)


@bot.command(name="unban")
@is_staff()
async def unban_user(ctx, user: discord.User):
    if str(user.id) in BANNED_USERS:
        del BANNED_USERS[str(user.id)]
        save_json("banned_users.json", BANNED_USERS)
        
    embed = discord.Embed(
        description=f"✅ User {user.mention} (`{user.id}`) has been unbanned from opening tickets.",
        color=EMBED_COLOR
    )
    await ctx.send(embed=embed)


# --- SNIPPET MANAGEMENT COMMANDS ---

@bot.command(name="addsnippet")
@is_staff()
async def addsnippet(ctx, name: str, *, msg: str):
    snippet_name = name.lower()
    if bot.get_command(snippet_name):
        return await ctx.send(f"Cannot use `{snippet_name}` because it is a reserved command.")

    SNIPPETS[snippet_name] = msg
    save_json("snippets.json", SNIPPETS)

    embed = discord.Embed(description=f"Snippet `.{snippet_name}` created.", color=EMBED_COLOR)
    await ctx.send(embed=embed)


@bot.command(name="editsnippet")
@is_staff()
async def editsnippet(ctx, name: str, *, msg: str):
    snippet_name = name.lower()
    if snippet_name not in SNIPPETS:
        return await ctx.send(f"Snippet `.{snippet_name}` does not exist.")

    SNIPPETS[snippet_name] = msg
    save_json("snippets.json", SNIPPETS)

    embed = discord.Embed(description=f"Snippet `.{snippet_name}` updated.", color=EMBED_COLOR)
    await ctx.send(embed=embed)


@bot.command(name="deletesnippet")
@is_staff()
async def deletesnippet(ctx, name: str):
    snippet_name = name.lower()
    if snippet_name not in SNIPPETS:
        return await ctx.send(f"Snippet `.{snippet_name}` does not exist.")

    del SNIPPETS[snippet_name]
    save_json("snippets.json", SNIPPETS)

    embed = discord.Embed(description=f"Snippet `.{snippet_name}` deleted.", color=EMBED_COLOR)
    await ctx.send(embed=embed)


@bot.command(name="snippets")
@is_staff()
async def list_snippets(ctx):
    if not SNIPPETS:
        embed = discord.Embed(title="Saved Snippets", description="No snippets exist.", color=EMBED_COLOR)
        return await ctx.send(embed=embed)

    snippet_list = "\n".join([f"• `.{name}`" for name in SNIPPETS.keys()])
    embed = discord.Embed(title="Saved Snippets", description=snippet_list, color=EMBED_COLOR)
    await ctx.send(embed=embed)


@bot.command(name="close")
@is_staff()
async def close_ticket(ctx):
    if ctx.channel.name.startswith("ticket-"):
        user_id = int(ctx.channel.name.split("-")[1])
        user = await bot.fetch_user(user_id)
        if user:
            try:
                close_embed = discord.Embed(
                    description=f"Your ticket has been marked as closed. Thank you for contacting {BRAND_NAME} Support.",
                    color=EMBED_COLOR
                )
                await user.send(embed=close_embed)
            except discord.HTTPException:
                pass

        chan_id = str(ctx.channel.id)
        if chan_id in SUBSCRIBERS:
            del SUBSCRIBERS[chan_id]
            save_json("subscribers.json", SUBSCRIBERS)

        await ctx.channel.delete()

bot.run(os.getenv("DISCORD_TOKEN"))
