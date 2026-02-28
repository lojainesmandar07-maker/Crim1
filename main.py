import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
import random

# ============================================
# إعدادات الويب (Render)
# ============================================
app = Flask('')
@app.route('/')
def home(): return "البوت يعمل بنجاح!"

def run(): app.run(host='0.0.0.0', port=8080)
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
        self.active_sessions = {}

    async def setup_hook(self):
        await self.tree.sync()
        print(f'✅ البوت جاهز ومسجل الدخول!')

bot = MysteryBot()

import data.story
import data.roles
import data.questions
import utils.helpers

@bot.tree.command(name="start_mystery", description="بدء فعالية الجريمة (للاونر فقط)")
async def start_mystery(interaction: discord.Interaction):
    if interaction.user != interaction.guild.owner:
        await interaction.response.send_message("❌ فقط الأونر يمكنه استخدام هذا الأمر!", ephemeral=True)
        return

    bot.active_sessions[interaction.guild.id] = {
        'players': [],
        'stage': 'registering',
        'channel_id': interaction.channel.id,
        'roles': {},
        'answers': {}
    }

    embed = discord.Embed(
        title="🔪 جريمة في قصر الظلال 🔪",
        description="🏰 قصر الظلال يستقبل ضيوفه...\nاللورد كرم يدعوكم، لكن الحفل سيتحول إلى جريمة!\n\n**المطلوب:** 2-10 لاعبين\nاضغط الزر أدناه للدخول",
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
            if not session: return
            if btn_interaction.user.id in session['players']:
                await btn_interaction.response.send_message("✅ أنت مسجل بالفعل!", ephemeral=True)
                return
            if len(session['players']) >= 10:
                await btn_interaction.response.send_message("❌ العدد مكتمل!", ephemeral=True)
                return

            session['players'].append(btn_interaction.user.id)
            await btn_interaction.response.send_message("✅ تم تسجيلك!", ephemeral=True)
            await btn_interaction.message.edit(content=f"**المسجلون: {len(session['players'])}/10**")

    await interaction.response.send_message(embed=embed, view=JoinButton(bot, interaction.guild.id))

@bot.tree.command(name="begin_story", description="بدء القصة وتوزيع الأدوار")
async def begin_story(interaction: discord.Interaction):
    if interaction.user != interaction.guild.owner:
        await interaction.response.send_message("❌ فقط الأونر!", ephemeral=True)
        return

    session = bot.active_sessions.get(interaction.guild.id)
    if not session or len(session['players']) < 2:
        await interaction.response.send_message("❌ يجب تسجيل لاعبين اثنين على الأقل!", ephemeral=True)
        return

    await interaction.response.defer()

    # توزيع الأدوار بذكاء (المحقق والقاتل أساسيين)
    players_ids = session['players'].copy()
    random.shuffle(players_ids)
    
    all_role_names = list(data.roles.ROLES.keys())
    mandatory = ["المحقق ياسين", "ياسر (الإبن)"]
    others = [r for r in all_role_names if r not in mandatory]
    random.shuffle(others)
    
    # اختيار الأدوار بناءً على عدد اللاعبين
    chosen_roles = mandatory + others[:len(players_ids)-2]
    random.shuffle(chosen_roles)

    roles_announcement = "📢 **تم توزيع الأدوار للمشاركين في هذه الجولة:**\n\n"
    
    for i, user_id in enumerate(players_ids):
        member = interaction.guild.get_member(user_id)
        role_name = chosen_roles[i]
        session['roles'][user_id] = role_name
        roles_announcement += f"🎭 **{role_name}**\n"
        
        try:
            await member.edit(nick=role_name)
        except:
            print(f"⚠️ تعذر تغيير اسم {member}")
        
        # إرسال التفاصيل كاملة في الخاص
        role_info = data.roles.ROLES[role_name]
        embed = discord.Embed(title=f"🎭 دورك: {role_name}", description=role_info, color=discord.Color.blue())
        try:
            await member.send(embed=embed)
        except:
            await interaction.followup.send(f"⚠️ {member.mention} الخاص مقفول!")

    # 1. إعلان توزيع الأدوار في العام
    await interaction.followup.send(roles_announcement)
    await interaction.followup.send("✅ تم تغيير أسمائكم مؤقتاً\n📜 تفاصيل دوركم وأسراركم وصلتكم في الخاص!")

    # 2. إرسال القصة
    story_embed = discord.Embed(title="🏰 بداية القصة", description=data.story.STORY, color=discord.Color.gold())
    await interaction.followup.send(embed=story_embed)

    # 3. التحقيق الأولي
    await asyncio.sleep(5)
    await interaction.followup.send(data.story.INITIAL_STATEMENTS)

    # 4. بدء الجولة الأولى
    await asyncio.sleep(5)
    await utils.helpers.start_round(bot, interaction.guild.id, 1)

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
