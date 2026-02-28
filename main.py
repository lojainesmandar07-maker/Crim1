import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
from dotenv import load_dotenv

# تحميل المتغيرات من ملف .env
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# إعدادات البوت
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MysteryBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)
        self.active_sessions = {}  # بيانات الجلسات النشطة

    async def setup_hook(self):
        await self.tree.sync()
        print(f'✅ البوت جاهز!')

bot = MysteryBot()

# استيراد الملفات الأخرى بعد تعريف bot (لتجنب circular imports)
import config.settings
import data.story
import data.roles
import data.questions
import utils.helpers

# ============================================
# أمر بدء الفعالية (للاونر فقط)
# ============================================
@bot.tree.command(name="start_mystery", description="بدء فعالية الجريمة (للاونر فقط)")
async def start_mystery(interaction: discord.Interaction):
    # التحقق من أن المستخدم هو الأونر
    if interaction.user != interaction.guild.owner:
        await interaction.response.send_message("❌ فقط الأونر يمكنه استخدام هذا الأمر!", ephemeral=True)
        return

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
        def __init__(self):
            super().__init__(timeout=None)  # أزرار دائمة
            self.joined = []

        @discord.ui.button(label="🔍 دخول الفعالية", style=discord.ButtonStyle.primary)
        async def join(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
            if len(self.joined) >= 10:
                await btn_interaction.response.send_message("❌ العدد اكتمل!", ephemeral=True)
                return
            if btn_interaction.user.id in self.joined:
                await btn_interaction.response.send_message("✅ أنت مسجل بالفعل!", ephemeral=True)
                return

            self.joined.append(btn_interaction.user.id)
            await btn_interaction.response.send_message("✅ تم تسجيلك! انتظر بدء القصة.", ephemeral=True)
            # تحديث العداد في الرسالة الأصلية
            await interaction.edit_original_response(content=f"**المسجلون: {len(self.joined)}/10**")

    await interaction.response.send_message(embed=embed, view=JoinButton())
    # تخزين الجلسة
    bot.active_sessions[interaction.guild.id] = {
        'players': [],
        'stage': 'registering'
    }

# ============================================
# أمر بدء القصة وتوزيع الأدوار (للاونر فقط)
# ============================================
@bot.tree.command(name="begin_story", description="بدء القصة وتوزيع الأدوار")
async def begin_story(interaction: discord.Interaction):
    if interaction.user != interaction.guild.owner:
        await interaction.response.send_message("❌ فقط الأونر!", ephemeral=True)
        return

    session = bot.active_sessions.get(interaction.guild.id)
    if not session or len(session['players']) != 10:
        await interaction.response.send_message("❌ يجب أن يكتمل العدد 10 أشخاص!", ephemeral=True)
        return

    await interaction.response.defer()

    # قائمة الأدوار (10 أدوار)
    role_names = list(data.roles.ROLES.keys())
    # نضمن وجود المحقق في الأدوار (الأدوار فيها 10 عناصر)
    import random
    random.shuffle(role_names)

    # تغيير الأسماء وإرسال الأدوار
    for i, user_id in enumerate(session['players']):
        member = interaction.guild.get_member(user_id)
        if member:
            try:
                # تغيير الاسم مؤقتاً
                await member.edit(nick=role_names[i])
                # حفظ دور اللاعب في الجلسة
                if 'roles' not in session:
                    session['roles'] = {}
                session['roles'][user_id] = role_names[i]

                # إرسال الدور في الخاص
                role_info = data.roles.ROLES[role_names[i]]
                embed = discord.Embed(
                    title=f"🎭 دورك: {role_names[i]}",
                    description=role_info,
                    color=discord.Color.blue()
                )
                try:
                    await member.send(embed=embed)
                except discord.Forbidden:
                    # إذا كان الخاص مقفول، نبعت تحذير
                    await interaction.followup.send(f"⚠️ {member.mention} الخاص مقفول، ما وصلتك الرسالة!", ephemeral=False)
                await asyncio.sleep(1)
            except Exception as e:
                print(f"خطأ في تغيير اسم {member}: {e}")

    # تحديث الجلسة
    session['stage'] = 'story_started'
    session['current_round'] = 1
    session['answers'] = {}  # لتخزين الإجابات
    bot.active_sessions[interaction.guild.id] = session

    # إرسال القصة
    story_embed = discord.Embed(
        title="🏰 بداية القصة",
        description=data.story.STORY,
        color=discord.Color.gold()
    )
    await interaction.followup.send(embed=story_embed)

    # التحقيق الأولي
    await asyncio.sleep(5)
    await interaction.followup.send(data.story.INITIAL_STATEMENTS)

    # بدأ الجولة الأولى
    await asyncio.sleep(5)
    await utils.helpers.start_round(bot, interaction, 1)

# ============================================
# تشغيل البوت
# ============================================
if __name__ == "__main__":
    bot.run(TOKEN)
