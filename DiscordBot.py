import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiosqlite
import asyncio
import re
import os
import csv
from datetime import datetime, timedelta, timezone
from config import *

TOKEN = "MTM5NDI1Mjc4NzM2MTI1NTU0Ng.Gx27X0.25cbID2Yyle9oQ3ZCsHM3nWHXc5fdOUwGFrtjE"  # 你的 Bot Token

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree


# -------------------------
# 權限檢查：是否管理層
def is_manager(member: discord.Member):
    return any(role.name == MANAGER_ROLE_NAME for role in member.roles)


# -------------------------
# Slash 指令區
@tree.command(name="ping", description="確認機器人是否在線")
async def ping_command(interaction: discord.Interaction):
    if not is_manager(interaction.user):
        await interaction.response.send_message("⚠️ 你沒有權限使用此功能！", ephemeral=True)
        return
    await interaction.response.send_message("✅ Hi！機器人在線中！")

@tree.command(name="panel", description="跳轉至控制面板")
async def panel_command(interaction: discord.Interaction):
    if not is_manager(interaction.user):
        await interaction.response.send_message("⚠️ 你沒有權限使用此功能！", ephemeral=True)
        return
    await interaction.response.send_message("🛠️ 控制面板：https://panel.cheapserver.tw/server/426010c8")

@tree.command(name="code", description="跳轉至 GitHub")
async def code_command(interaction: discord.Interaction):
    if not is_manager(interaction.user):
        await interaction.response.send_message("⚠️ 你沒有權限使用此功能！", ephemeral=True)
        return
    await interaction.response.send_message("📦 GitHub 倉庫：https://github.com/你的機器人倉庫")

@tree.command(name="help", description="列出所有可用指令")
async def help_command(interaction: discord.Interaction):
    help_text = """
📘 **指令列表**

**📌 Slash 指令（/開頭）**
/ping - 確認機器人是否在線  
/panel - 跳轉至控制面板  
/code - 跳轉至 GitHub 倉庫  
/help - 顯示這個說明訊息  

**🛠️ Prefix 指令（!開頭）**
!join [成員名 or ID] [身份組] - 快速新增身份組 
!mute [成員 or ID] [時間] - 禁言成員 並指定時間s,m,h,d
!unmute [成員 or ID] - 解除禁言  
!kick [成員 or ID] - 踢出成員  
!ban [成員 or ID] - 封鎖成員  
!leave - 在 #請假點名區 顯示目前請假成員  
!send_team_roles - 發送身分組選擇按鈕 
!send_checkin - 發送點名與請假按鈕
    """
    await interaction.response.send_message(help_text, ephemeral=True)


# -------------------------
# 新成員自動分配身份組

@bot.event
async def on_member_join(member):
    guild = member.guild
    role = discord.utils.get(guild.roles, name=NOT_PASSED_ROLE)
    if role:
        await member.add_roles(role, reason="新成員自動分配身份組")


# -------------------------
# Prefix 指令區

@bot.command()
async def join(ctx, member: discord.Member, role_name: str):
    if not is_manager(ctx.author):
        await ctx.send("⚠️ 你沒有權限使用此功能！", delete_after=5)
        return

    not_passed = discord.utils.get(ctx.guild.roles, name=NOT_PASSED_ROLE)
    new_role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not new_role:
        await ctx.send("❌ 指定身份組不存在")
        return

    await member.remove_roles(not_passed, reason="通過考試")
    await member.add_roles(new_role, reason="加入隊伍")

    channel = discord.utils.get(ctx.guild.text_channels, name=TEXT_CHANNEL)
    await channel.send(f"🎉 {member.mention} 已加入 {role_name}！")


@bot.command()
async def mute(ctx, member: discord.Member, duration: str):
    if not is_manager(ctx.author):
        await ctx.send("⚠️ 你沒有權限使用此功能！", delete_after=5)
        return

    match = re.fullmatch(r"(\d+)([smhd])", duration)
    if not match:
        await ctx.send("❌ 格式錯誤！請使用像 `10m`、`2h`、`1d` 等格式")
        return

    value, unit = int(match[1]), match[2]
    if unit == "s":
        delta = timedelta(seconds=value)
    elif unit == "m":
        delta = timedelta(minutes=value)
    elif unit == "h":
        delta = timedelta(hours=value)
    elif unit == "d":
        delta = timedelta(days=value)

    until = discord.utils.utcnow() + delta

    # 先用 Discord timeout API 禁言
    await member.edit(timeout=until)
    # 保留禁言身份組，讓其他功能可以檢查是否禁言中
    mute_role = discord.utils.get(ctx.guild.roles, name=MUTE_ROLE)
    if mute_role and mute_role not in member.roles:
        await member.add_roles(mute_role, reason="管理員禁言")

    await ctx.send(f"🔇 {member.mention} 已被禁言 {value}{unit}")

@bot.command()
async def unmute(ctx, member: discord.Member):
    if not is_manager(ctx.author):
        await ctx.send("⚠️ 你沒有權限使用此功能！", delete_after=5)
        return

    # 解除 Discord timeout
    await member.edit(timeout=None)
    # 移除禁言身份組
    mute_role = discord.utils.get(ctx.guild.roles, name=MUTE_ROLE)
    if mute_role and mute_role in member.roles:
        await member.remove_roles(mute_role, reason="管理員解除禁言")

    await ctx.send(f"🔊 {member.mention} 已解除禁言")

@bot.command()
async def kick(ctx, member: discord.Member):
    if not is_manager(ctx.author):
        await ctx.send("⚠️ 你沒有權限使用此功能！", delete_after=5)
        return
    await member.kick()
    await ctx.send(f"👢 {member.mention} 已被踢出伺服器")


@bot.command()
async def ban(ctx, member: discord.Member):
    if not is_manager(ctx.author):
        await ctx.send("⚠️ 你沒有權限使用此功能！", delete_after=5)
        return
    await member.ban()
    await ctx.send(f"⛔ {member.mention} 已被封鎖")


@bot.command(name="leave")
async def list_leaves(ctx):
    if not is_manager(ctx.author):
        await ctx.send("⚠️ 你沒有權限使用此功能！", delete_after=5)
        return

    # 尋找請假點名區頻道
    channel = discord.utils.get(ctx.guild.text_channels, name=CHECKIN_CHANNEL)
    if channel is None:
        await ctx.send("❌ 找不到請假點名區頻道")
        return

    now = datetime.now(timezone.utc)  # 改成帶時區
    output_lines = []

    async with aiosqlite.connect("db.sqlite3") as db:
        async with db.execute("SELECT user_id, end_time FROM leaves") as cursor:
            async for user_id, end_time_str in cursor:
                try:
                    end_time = datetime.fromisoformat(end_time_str)
                    if end_time.tzinfo is None:
                        end_time = end_time.replace(tzinfo=timezone.utc)  # 補時區
                    delta = (end_time - now).days
                    if delta < 0:
                        continue  # 跳過已過期請假
                    member = ctx.guild.get_member(user_id)
                    if member:
                        output_lines.append(f"📌 {member.display_name}：剩餘 {delta} 天")
                except Exception as e:
                    print(f"[!] 請假資料解析錯誤：{e}")

    if not output_lines:
        await channel.send("✅ 目前沒有任何請假中的成員")
    else:
        await channel.send("📝 以下是請假中的成員：\n" + "\n".join(output_lines))



# -------------------------
# 點名與請假按鈕

class CheckInView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="點名", style=discord.ButtonStyle.success, custom_id="checkin")
    async def checkin(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 紀錄點名時間到資料庫
        async with aiosqlite.connect("db.sqlite3") as db:
            await db.execute(
                "INSERT OR REPLACE INTO checkin (user_id, timestamp) VALUES (?, ?)",
                (interaction.user.id, datetime.utcnow().isoformat())
            )
            await db.commit()

        # 若有潛水身份組則移除
        diver_role = discord.utils.get(interaction.guild.roles, name=DIVER_ROLE)
        if diver_role in interaction.user.roles:
            await interaction.user.remove_roles(diver_role)

        # 若有請假中身份組，移除請假中
        leave_role = discord.utils.get(interaction.guild.roles, name=LEAVE_ROLE)
        if leave_role in interaction.user.roles:
            await interaction.user.remove_roles(leave_role)

        await interaction.response.send_message("📌 點名成功！", ephemeral=True)

    @discord.ui.button(label="請假", style=discord.ButtonStyle.primary, custom_id="leave")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("📬 請至私訊輸入請假天數", ephemeral=True)
        try:
            dm = await interaction.user.create_dm()
            await dm.send("請輸入請假天數（數字）：")

            def check(m):
                return m.author == interaction.user and m.channel == dm

            msg = await bot.wait_for("message", check=check, timeout=60)
            days = int(msg.content.strip())

            # 新增請假中身份組
            leave_role = discord.utils.get(interaction.guild.roles, name=LEAVE_ROLE)
            if leave_role not in interaction.user.roles:
                await interaction.user.add_roles(leave_role)

            review_channel = discord.utils.get(interaction.guild.text_channels, name=LEAVE_REVIEW_CHANNEL)
            approve_view = ApproveView(user=interaction.user, days=days)
            await review_channel.send(
                f"📝 {interaction.user.mention} 申請請假 {days} 天，請管理員審核：",
                view=approve_view
            )
            await dm.send("✅ 已送出請假申請，請等待審核。")
        except Exception as e:
            print(f"請假錯誤：{e}")


class ApproveView(discord.ui.View):
    def __init__(self, user, days):
        super().__init__(timeout=None)
        self.user = user
        self.days = days

    @discord.ui.button(label="批准", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_manager(interaction.user):
            await interaction.response.send_message("⚠️ 你沒有權限審核", ephemeral=True)
            return

        # ✅ 儲存請假結束時間到資料庫
        end_time = datetime.now(timezone.utc) + timedelta(days=self.days)
        async with aiosqlite.connect("db.sqlite3") as db:
            await db.execute(
                "INSERT OR REPLACE INTO leaves (user_id, end_time) VALUES (?, ?)",
                (self.user.id, end_time.isoformat())
            )
            await db.commit()

        # 私訊使用者審核通過訊息
        await self.user.send(f"✅ 你的請假 {self.days} 天已獲批准。")
        await interaction.message.edit(content="✅ 已批准請假", view=None)

    @discord.ui.button(label="拒絕", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_manager(interaction.user):
            await interaction.response.send_message("⚠️ 你沒有權限審核", ephemeral=True)
            return

        # 私訊使用者審核拒絕訊息，並移除請假中身份組
        leave_role = discord.utils.get(interaction.guild.roles, name=LEAVE_ROLE)
        if leave_role and leave_role in self.user.roles:
            await self.user.remove_roles(leave_role)
        await self.user.send(f"❌ 你的請假 {self.days} 天已被拒絕。")
        await interaction.message.edit(content="❌ 已拒絕請假", view=None)

class TeamSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for role_name in TEAM_ROLES:
            self.add_item(TeamSelectButton(role_name))


class TeamSelectButton(discord.ui.Button):
    def __init__(self, role_name):
        super().__init__(label=role_name, style=discord.ButtonStyle.primary, custom_id=f"select_{role_name}")
        self.role_name = role_name

    async def callback(self, interaction: discord.Interaction):
        async with aiosqlite.connect("db.sqlite3") as db:
            async with db.execute("SELECT 1 FROM team_selected WHERE user_id = ?", (interaction.user.id,)) as cursor:
                result = await cursor.fetchone()

        if result:
            await interaction.response.send_message("⚠️ 你已經選擇過身份組，無法再次選擇！", ephemeral=True)
            return

        view = TeamConfirmView(user=interaction.user, role_name=self.role_name)
        await interaction.response.send_message(
            f"你已選擇 {self.role_name}，再次提醒，每人只有一次機會可以做選擇，請確認你的選擇是正確的！！！",
            view=view,
            ephemeral=True
        )


class TeamConfirmView(discord.ui.View):
    def __init__(self, user: discord.Member, role_name: str):
        super().__init__(timeout=60)
        self.user = user
        self.role_name = role_name

    @discord.ui.button(label="確認", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("⚠️ 這不是給你的選項！", ephemeral=True)
            return

        role = discord.utils.get(interaction.guild.roles, name=self.role_name)
        not_passed = discord.utils.get(interaction.guild.roles, name=NOT_PASSED_ROLE)

        if role:
            await self.user.add_roles(role, reason="身份組領取確認")
        if not_passed and not_passed in self.user.roles:
            await self.user.remove_roles(not_passed, reason="已通過考試")

        async with aiosqlite.connect("db.sqlite3") as db:
            await db.execute("INSERT INTO team_selected (user_id) VALUES (?)", (self.user.id,))
            await db.commit()

        await interaction.response.edit_message(content=f"✅ 你已成功領取 {self.role_name}", view=None)

    @discord.ui.button(label="取消", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("⚠️ 這不是給你的選項！", ephemeral=True)
            return
        await interaction.response.edit_message(content="❎ 已取消選擇", view=None)


@bot.command()
async def send_team_roles(ctx):
    if not is_manager(ctx.author):
        await ctx.send("⚠️ 你沒有權限使用此功能！", delete_after=5)
        return

    target_channel = discord.utils.get(ctx.guild.text_channels, name="獲取身分組")
    if not target_channel:
        await ctx.send("❌ 找不到頻道：獲取身分組", delete_after=5)
        return

    view = TeamSelectView()
    await target_channel.send(
        "歡迎加入SDW戰隊，請在此選擇你的身分組，以確保你已經考完入隊考試，也順便讓大家知道你位於戰隊的幾館隊員。注意：身分組只能設定一次，請仔細選擇！！！",
        view=view
    )


@bot.command()
async def send_checkin(ctx):
    if not is_manager(ctx.author):
        await ctx.send("⚠️ 你沒有權限使用此功能！", delete_after=5)
        return
    checkin_channel = discord.utils.get(ctx.guild.text_channels, name=CHECKIN_CHANNEL)
    view = CheckInView()
    await checkin_channel.send(
        "📅 這裡是請假和點名區，請點擊以下按鈕完成簽到或請假申請：",
        view=view
    )


# -------------------------
# 每天 08:00 檢查未點名成員，加入潛水身份組，請假中成員跳過

@tasks.loop(time=datetime.strptime("08:00", "%H:%M").time())
async def check_inactive():
    async with aiosqlite.connect("db.sqlite3") as db:
        now = datetime.now(timezone.utc)  # 改成有時區
        async with db.execute("SELECT user_id, timestamp FROM checkin") as cursor:
            records = await cursor.fetchall()
            checkin_dict = {}
            for user_id, ts in records:
                dt = datetime.fromisoformat(ts)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)  # 補時區
                checkin_dict[user_id] = dt

        guild = bot.guilds[0]
        diver_role = discord.utils.get(guild.roles, name=DIVER_ROLE)
        leave_role = discord.utils.get(guild.roles, name=LEAVE_ROLE)

        for member in guild.members:
            if member.bot or is_manager(member):
                continue
            if leave_role and leave_role in member.roles:
                continue

            last_checkin = checkin_dict.get(member.id)
            if not last_checkin or (now - last_checkin > timedelta(days=7)):
                if diver_role and diver_role not in member.roles:
                    await member.add_roles(diver_role)
            else:
                if diver_role and diver_role in member.roles:
                    await member.remove_roles(diver_role)



# -------------------------
# 每天 08:00 檢查請假成員，移除請假中身份組

@tasks.loop(hours=1)
async def remove_expired_leaves():
    now = datetime.now(timezone.utc)  # 改成有時區
    async with aiosqlite.connect("db.sqlite3") as db:
        async with db.execute("SELECT user_id, end_time FROM leaves") as cursor:
            rows = await cursor.fetchall()

        guild = bot.guilds[0]
        leave_role = discord.utils.get(guild.roles, name=LEAVE_ROLE)

        for user_id, end_str in rows:
            end_time = datetime.fromisoformat(end_str)
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)  # 補時區

            if now >= end_time:
                member = guild.get_member(user_id)
                if member and leave_role in member.roles:
                    await member.remove_roles(leave_role, reason="請假期滿自動移除")
                    print(f"✅ 自動移除 {member} 的請假中身份組")

                await db.execute("DELETE FROM leaves WHERE user_id = ?", (user_id,))
        await db.commit()



# -------------------------
# 每週一 08:00 匯出 .csv 點名紀錄
@tasks.loop(minutes=1)
async def export_weekly_checkin():
    now = datetime.utcnow() + timedelta(hours=8)  # 台灣時區
    if now.weekday() == 0 and now.hour == 8 and now.minute == 0:
        os.makedirs("./check", exist_ok=True)
        filename = f"./check/checkin_export_{now.strftime('%Y%m%d')}.csv"

        async with aiosqlite.connect("db.sqlite3") as db:
            async with db.execute("SELECT user_id, timestamp FROM checkin") as cursor:
                rows = await cursor.fetchall()

        with open(filename, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["User ID", "Check-in Time (UTC+8)"])
            writer.writerows(rows)

        print(f"✅ 匯出簽到資料到 {filename}")

# -------------------------
# 啟動時同步 Slash 指令、建表、啟動排程
@bot.event
async def on_ready():
    print(f"✅ 機器人上線：{bot.user}")
    await tree.sync()
    await init_db()
    bot.add_view(CheckInView())
    check_inactive.start()
    export_weekly_checkin.start()
    bot.add_view(TeamSelectView())

async def init_db():
    async with aiosqlite.connect("db.sqlite3") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS checkin (
                user_id INTEGER PRIMARY KEY,
                timestamp TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS leaves (
                user_id INTEGER PRIMARY KEY,
                end_time TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS team_selected (
                user_id INTEGER PRIMARY KEY
            )
        """)

        await db.commit()


bot.run(TOKEN)