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

# استيراد الملفات
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
        'channel_id': interaction.channel.id
    }

    embed = discord.Embed(
        title="🔪 جريمة في قصر الظلال 🔪",
        description="""
        🏰 قصر الظلال يستقبل الضيوف...
        اللورد كرم يدعوكم لحفل عيد ميلاده، لكن الحفل سيتحول إلى جريمة قتل!
        
        **العدد المطلوب:** من 2 إلى 10 لاعبين
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
                await btn_interaction.response.send_message("❌ العدد اكتمل (10 لاعبين كحد أقصى)!", ephemeral=True)
                return
                
            if btn_interaction.user.id in session['players']:
                await btn_interaction.response.send_message("✅ أنت مسجل بالفعل!", ephemeral=True)
                return

            session['players'].append(btn_interaction.user.id)
            await btn_interaction.response.send_message("✅ تم تسجيلك! انتظر بدء القصة.", ephemeral=True)
            
            await btn_interaction.message.edit(content=f"**المسجلون: {len(session['players'])}/10**")

    await interaction.response.send_message(embed=embed, view=JoinButton(bot, interaction.guild.id))

# ============================================
# أمر بدء القصة وتوزيع الأدوار (معدل للمرونة)
# ============================================
@bot.tree.command(name="begin_story", description="بدء القصة وتوزيع الأدوار (2-10 لاعبين)")
async def begin_story(interaction: discord.Interaction):
    if interaction.user != interaction.guild.owner:
        await interaction.response.send_message("❌ فقط الأونر!", ephemeral=True)
        return

    session = bot.active_sessions.get(interaction.guild.id)
    if not session:
        await interaction.response.send_message("❌ لا توجد فعالية نشطة! استخدم /start_mystery أولاً.", ephemeral=True)
        return
    
    player_count = len(session['players'])
    if player_count < 2:
        await interaction.response.send_message("❌ يجب أن يكون عدد اللاعبين على الأقل 2 (محقق وقاتل)!", ephemeral=True)
        return

    await interaction.response.defer()

    # ============================================
    # توزيع الأدوار الذكي
    # ============================================
    # الأدوار الأساسية: المحقق دائماً + ياسر (القاتل) دائماً
    base_roles = ["المحقق ياسين", "ياسر (الإبن)"]
    
    # باقي الأدوار المتاحة (بدون المحقق وياسر)
    available_roles = [
        "لارا (الزوجة)",
        "ليلى (الإبنة)",
        "هند (الخادمة)",
        "رامي (الحارس)",
        "نادين (الطاهية)",
        "د. سلمى (الطبيبة)",
        "فؤاد (المحامي)",
        "عفاف (الجارة)"
    ]
    
    # خلط الأدوار المتاحة
    import random
    random.shuffle(available_roles)
    
    # اختيار العدد المطلوب من الأدوار المتاحة
    needed_extra = player_count - 2  # عدد الأدوار الإضافية المطلوبة
    selected_extra = available_roles[:needed_extra]
    
    # الأدوار النهائية: الأساسية + المختارة
    final_roles = base_roles + selected_extra
    random.shuffle(final_roles)  # خلط الأدوار النهائية
    
    # خلط قائمة اللاعبين
    players_copy = session['players'].copy()
    random.shuffle(players_copy)
    
    # توزيع الأدوار
    roles_assigned = {}
    role_announcement = "📢 **الأدوار تم توزيعها:**\n\n"
    
    for i, user_id in enumerate(players_copy):
        role = final_roles[i]
        roles_assigned[user_id] = role
        role_announcement += f"🎭 {role}\n"
        
        member = interaction.guild.get_member(user_id)
        if member:
            try:
                await member.edit(nick=role)
            except discord.Forbidden:
                print(f"⚠️ لم أتمكن من تغيير اسم {member}")
            
            # إرسال تفاصيل الدور في الخاص
            role_info = data.roles.ROLES.get(role, "تفاصيل الدور غير متوفرة.")
            embed = discord.Embed(
                title=f"🎭 دورك: {role}",
                description=role_info,
                color=discord.Color.blue()
            )
            try:
                await member.send(embed=embed)
            except discord.Forbidden:
                await interaction.followup.send(f"⚠️ {member.mention} الخاص مقفول، افتح الخاص لرؤية دورك!", ephemeral=False)
            await asyncio.sleep(1)
    
    # حفظ البيانات في الجلسة
    session['roles'] = roles_assigned
    session['stage'] = 'story_started'
    session['current_round'] = 1
    session['answers'] = {}
    
    # إعلان الأدوار في العام
    await interaction.followup.send(role_announcement)
    await interaction.followup.send("✅ تم تغيير أسمائكم مؤقتاً\n📜 تفاصيل دوركم وصلتكم ع الخاص")
    
    # سرد القصة
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
    await utils.helpers.start_round(bot, interaction.guild.id, 1)

# ============================================
# أمر إضافي: عرض اللاعبين المسجلين
# ============================================
@bot.tree.command(name="show_players", description="عرض قائمة اللاعبين المسجلين")
async def show_players(interaction: discord.Interaction):
    if interaction.user != interaction.guild.owner:
        await interaction.response.send_message("❌ فقط الأونر!", ephemeral=True)
        return
    
    session = bot.active_sessions.get(interaction.guild.id)
    if not session or not session['players']:
        await interaction.response.send_message("📭 لا يوجد لاعبين مسجلين حالياً.", ephemeral=True)
        return
    
    players_list = "**اللاعبون المسجلون:**\n"
    for user_id in session['players']:
        member = interaction.guild.get_member(user_id)
        if member:
            players_list += f"• {member.mention}\n"
    
    players_list += f"\n**العدد: {len(session['players'])}/10**"
    await interaction.response.send_message(players_list, ephemeral=True)

# ============================================
# أمر إضافي: إعادة تعيين الجلسة
# ============================================
@bot.tree.command(name="reset_session", description="إعادة تعيين الجلسة الحالية")
async def reset_session(interaction: discord.Interaction):
    if interaction.user != interaction.guild.owner:
        await interaction.response.send_message("❌ فقط الأونر!", ephemeral=True)
        return
    
    if interaction.guild.id in bot.active_sessions:
        del bot.active_sessions[interaction.guild.id]
        await interaction.response.send_message("✅ تم إعادة تعيين الجلسة. يمكنك بدء فعالية جديدة.", ephemeral=True)
    else:
        await interaction.response.send_message("📭 لا توجد جلسة نشطة.", ephemeral=True)

# ============================================
# تشغيل البوت
# ============================================
if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
