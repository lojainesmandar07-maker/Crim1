import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# ============================================
# إعدادات الويب (لمنع البوت من التوقف على Render)
# ============================================
app = Flask('')

@app.route('/')
def home():
    return "البوت يعمل بنجاح!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ============================================
# إعدادات البوت الأساسية
# ============================================
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MysteryBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='/', intents=intents)
        self.active_sessions = {}  # حفظ بيانات الجلسات النشطة لكل سيرفر

    async def setup_hook(self):
        await self.tree.sync()
        print(f'✅ البوت جاهز ومسجل الدخول!')

bot = MysteryBot()

# استيراد الملفات (لن يتم المساس بملفات البيانات الخاصة بك)
import data.story
import data.roles
import data.questions
import utils.helpers

# ============================================
# أمر بدء الفعالية
# ============================================
@bot.tree.command(name="start_mystery", description="بدء فعالية الجريمة (للاونر فقط)")
async def start_mystery(interaction: discord.Interaction):
    if interaction.user != interaction.guild.owner:
        await interaction.response.send_message("❌ فقط الأونر يمكنه استخدام هذا الأمر!", ephemeral=True)
        return

    # إنشاء جلسة جديدة للسيرفر
    bot.active_sessions[interaction.guild.id] = {
        'players': [],
        'stage': 'registering',
        'channel_id': interaction.channel.id # حفظ القناة لإرسال التحديثات لاحقاً
    }

    embed = discord.Embed(
        title="🔪 جريمة في قصر الظلال 🔪",
        description="""
        🏰 قصر الظلال يستقبل 10 ضيوف...
        اللورد كرم يدعوكم لحفل عيد ميلاده، لكن الحفل سيتحول إلى جريمة قتل!
        
        **المطلوب:** 10 متطوعين
        **المدة:** 45 دقيقة
        
        اضغط الزر أدناه للدخول
        """,
        color=discord.Color.dark_red()
    )

    class JoinButton(discord.ui.View):
        def __init__(self, bot_instance, guild_id):
            super().__init__(timeout=None)
            self.bot = bot_instance
            self.guild_id = guild_id

        @discord.ui.button(label="🔍 دخول الفعالية", style=discord.ButtonStyle.primary)
        async def join(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
            session = self.bot.active_sessions.get(self.guild_id)
            
            if not session:
                await btn_interaction.response.send_message("❌ لا توجد فعالية نشطة!", ephemeral=True)
                return
                
            if len(session['players']) >= 10:
                await btn_interaction.response.send_message("❌ العدد اكتمل!", ephemeral=True)
                return
                
            if btn_interaction.user.id in session['players']:
                await btn_interaction.response.send_message("✅ أنت مسجل بالفعل!", ephemeral=True)
                return

            # تسجيل اللاعب في الجلسة الأساسية
            session['players'].append(btn_interaction.user.id)
            await btn_interaction.response.send_message("✅ تم تسجيلك! انتظر بدء القصة.", ephemeral=True)
            
            await btn_interaction.message.edit(content=f"**المسجلون: {len(session['players'])}/10**")

    await interaction.response.send_message(embed=embed, view=JoinButton(bot, interaction.guild.id))

# ============================================
# أمر بدء القصة وتوزيع الأدوار
# ============================================
@bot.tree.command(name="begin_story", description="بدء القصة وتوزيع الأدوار")
async def begin_story(interaction: discord.Interaction):
    if interaction.user != interaction.guild.owner:
        await interaction.response.send_message("❌ فقط الأونر!", ephemeral=True)
        return

    session = bot.active_sessions.get(interaction.guild.id)
    if not session or len(session['players']) != 10:
        # ملاحظة: يمكنك تغيير الرقم 10 أثناء التجربة لعدد أقل إذا أردت تجربة البوت وحدك
        await interaction.response.send_message("❌ يجب أن يكتمل العدد 10 أشخاص!", ephemeral=True)
        return

    await interaction.response.defer()

    role_names = list(data.roles.ROLES.keys())
    import random
    random.shuffle(role_names)

    for i, user_id in enumerate(session['players']):
        member = interaction.guild.get_member(user_id)
        if member:
            try:
                await member.edit(nick=role_names[i])
            except discord.Forbidden:
                print(f"⚠️ لم أتمكن من تغيير اسم {member} (ربما لديه رتبة أعلى)")
            
            if 'roles' not in session:
                session['roles'] = {}
            session['roles'][user_id] = role_names[i]

            role_info = data.roles.ROLES[role_names[i]]
            embed = discord.Embed(
                title=f"🎭 دورك: {role_names[i]}",
                description=role_info,
                color=discord.Color.blue()
            )
            try:
                await member.send(embed=embed)
            except discord.Forbidden:
                await interaction.followup.send(f"⚠️ {member.mention} الخاص مقفول، افتح الخاص لرؤية دورك!", ephemeral=False)
            await asyncio.sleep(1)

    session['stage'] = 'story_started'
    session['current_round'] = 1
    session['answers'] = {}

    story_embed = discord.Embed(
        title="🏰 بداية القصة",
        description=data.story.STORY,
        color=discord.Color.gold()
    )
    await interaction.followup.send(embed=story_embed)

    await asyncio.sleep(5)
    await interaction.followup.send(data.story.INITIAL_STATEMENTS)

    await asyncio.sleep(5)
    # نمرر رقم السيرفر (guild_id) بدلاً من interaction لتجنب مشاكل الرسائل الخاصة
    await utils.helpers.start_round(bot, interaction.guild.id, 1)

# ============================================
# تشغيل البوت
# ============================================
if __name__ == "__main__":
    keep_alive() # تشغيل خادم الويب
    bot.run(TOKEN)
