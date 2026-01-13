# ===== Auto Install Missing Modules =====
import importlib, subprocess, sys

def ensure_package(pkg: str):
    try:
        importlib.import_module(pkg)
    except ImportError:
        print(f"📦 Installing missing package: {pkg}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

for pkg in ["aiohttp", "discord.py", "requests"]:
    ensure_package(pkg)

# ===== Imports =====
import os, io, asyncio, aiohttp, discord
from datetime import datetime
from discord.ext import commands

# ================== CONFIG ==================
DISCORD_TOKEN = " " # 🔑 ใส่ TOKEN DISCORD
API_URL = "https://slumzick.xyz/dump.php" # ห้ามแก้ไข API
API_KEY = " " # 🔑 ใส่ API Key สำหรับเชื่อมต่อ DinoShop

COMMAND_PREFIX = "!"
ALLOWED_CHANNEL_IDS = {1439345518584004812} # ห้องที่จะให้งาน คำสั่งใช้งาน !panel
HISTORY_CHANNEL_ID = 1439345861762089010 # ห้องเก็บประวัติ

MAX_FILE_MB = 10 # ห้ามแก้ไขจำกัดการส่งไฟล์
CREDIT_NAME = "SLUMZICK" # เครดิตแก้ได้

# ================== BOT SETUP ==================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)
session: aiohttp.ClientSession | None = None

@bot.event
async def on_ready():
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180))
    print(f"✅ บอท {bot.user} พร้อมใช้งานแล้ว! ใช้ API {API_URL}")

# ================== UTILITIES ==================
def split_bytes(data: bytes, filename: str, max_mb: int) -> list:
    max_b = max_mb * 1024 * 1024
    if len(data) <= max_b:
        return [discord.File(io.BytesIO(data), filename=filename)]
    files, part = [], 1
    for i in range(0, len(data), max_b):
        chunk = data[i:i + max_b]
        files.append(discord.File(io.BytesIO(chunk), filename=f"{os.path.splitext(filename)[0]}_part{part}.txt"))
        part += 1
    return files

def safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in name)

# ================== API ==================
async def query_api(keyword: str, t: int = 1) -> dict:
    assert session is not None
    params = {"q": keyword, "t": t, "key": API_KEY}
    async with session.get(API_URL, params=params) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}")
        return await resp.json(content_type=None)

# ================== SEARCH CORE ==================
async def do_search(interaction: discord.Interaction, keyword: str, t: int = 1):
    # แสดงข้อความกำลังโหลด
    await interaction.response.send_message(
        f"⏳ กำลังดึงข้อมูลจาก API สำหรับ `{keyword}` (โหมด={t}) ...",
        ephemeral=True
    )
    try:
        start = datetime.now()
        js = await query_api(keyword, t)
        if js.get("status") != "success":
            return await interaction.edit_original_response(
                content=f"❌ ไม่พบข้อมูล: {js.get('message')}"
            )

        lines = js.get("data", [])
        elapsed = (datetime.now() - start).total_seconds() * 1000
        user = interaction.user
        filename = f"{safe_filename(keyword)}.txt"

        # ✅ แก้ข้อความเดิมให้เป็นข้อความสรุปสำเร็จ
        summary = (
            f"✅ **DinoDonut สำเร็จ!**\n"
            f"• คำค้น: `{keyword}`\n"
            f"• โหมด: `{t}`\n"
            f"• จำนวน: `{len(lines):,}` บรรทัด\n"
            f"• ใช้เวลา: `{elapsed:.2f} ms`\n"
            f"📬 ระบบได้ส่งไฟล์ให้คุณทาง **DM แล้ว**"
        )
        await interaction.edit_original_response(content=summary)

        # 📩 ส่งไฟล์เข้า DM
        content = "\n".join(lines).encode("utf-8")
        files = split_bytes(content, filename, MAX_FILE_MB)

        embed = discord.Embed(
            title="📦 DinoDonut Log File",
            description=(
                f"คำค้น: `{keyword}`\n"
                f"โหมด: `{t}`\n"
                f"จำนวน: `{len(lines):,}`\n"
                f"ใช้เวลา: `{elapsed:.2f} ms`\n"
            ),
            color=discord.Color.green()
        ).set_footer(text=f"Powered by {CREDIT_NAME}")

        try:
            await user.send(embed=embed, files=files)
        except:
            await interaction.followup.send(
                "⚠️ ไม่สามารถส่งไฟล์ทาง DM ได้ (อาจปิดข้อความส่วนตัว)",
                ephemeral=True
            )

        # 🧾 บันทึกประวัติในห้อง
        history = bot.get_channel(HISTORY_CHANNEL_ID)
        if history:
            await history.send(
                embed=discord.Embed(
                    title="📜 ประวัติการค้นหา",
                    description=f"👤 {user.mention}\n🔍 `{keyword}`\nโหมด: {t} | 📄 `{len(lines):,}` บรรทัด",
                    color=discord.Color.blue()
                )
            )

    except Exception as e:
        await interaction.edit_original_response(content=f"❌ เกิดข้อผิดพลาด: `{e}`")


# ================== MODAL ==================
class SearchModal(discord.ui.Modal, title="🔎 ค้นหา Log ผ่าน DinoDonut"):
    keyword = discord.ui.TextInput(label="คำค้นหา", placeholder="เช่น pointblank.zepetto.com", required=True)
    mode = discord.ui.TextInput(label="โหมด (0=login:pass, 1=url:login:pass)", placeholder="ค่าเริ่มต้น: 1", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        kw = self.keyword.value.strip()
        try:
            t = int(self.mode.value.strip()) if self.mode.value.strip() in ["0", "1"] else 1
        except:
            t = 1
        await do_search(interaction, kw, t)

# ================== PANEL VIEW ==================
class MainView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔍 กรอกคำค้นหา", style=discord.ButtonStyle.danger)
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SearchModal())

    @discord.ui.button(label="📘 วิธีใช้งาน", style=discord.ButtonStyle.success)
    async def howto(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📖 วิธีใช้ SLUMZICK Bot",
            description=(
                "```"
                "1. กดปุ่ม 🔍 เพื่อกรอกคำค้นหา\n"
                "2. พิมพ์ keyword เช่น pointblank.zepetto.com\n"
                "3. เลือกโหมด (0 หรือ 1)\n"
                "4. ระบบจะส่งไฟล์กลับทาง DM เท่านั้น\n"
                "```"
            ),
            color=discord.Color.purple()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ================== PANEL COMMAND ==================
@bot.command()
async def panel(ctx):
    if ALLOWED_CHANNEL_IDS and ctx.channel.id not in ALLOWED_CHANNEL_IDS:
        return await ctx.send("❌ ใช้ได้เฉพาะห้องที่อนุญาตเท่านั้น")

    embed = discord.Embed(
        title="ꔫ・ SLUMZICK Log Search",
        description=(
            "```"
            "🔎 ระบบค้นหา Log ผ่าน DinoDonut\n"
            "📬 ส่งไฟล์เข้า DM เท่านั้น (ปลอดภัย)\n"
            "🔗 ตัวอย่างคำค้น: pointblank.zepetto.com\n"
            "```"
        ),
        color=discord.Color.purple()
    )
    embed.set_image(url="https://img2.pic.in.th/pic/-2000-x-600-px-1900-x-600-pxe4ab378b9446e2a0.png")
    await ctx.send(embed=embed, view=MainView())

# ================== START ==================
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)