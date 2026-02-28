import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
import random

# ============================================
# إعدادات الويب (لمنع البوت من التوقف على Render)
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
        print(f'✅ البوت جاهز!')

bot = MysteryBot()

import data.story
import data.roles
import data.questions
import utils.helpers

@bot.tree.command(name="start_mystery", description="بدء التسجيل للفعالية")
async def start_mystery(interaction: discord.Interaction):
    if interaction.user != interaction.guild.owner:
        await interaction.response.send_message("❌ فقط الأونر يمكنه بدء الفعالية!", ephemeral=True)
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
        description="انضموا الآن لكشف القاتل! (العدد المطلوب: 2 - 10 لاعبين)",
        color=discord.Color.dark_red()
    )

    class JoinButton(discord.ui.View):
        def __init__(self): super().__init__(timeout=None)
        @discord.ui.button(label="🔍 دخول الفعالية", style=discord.ButtonStyle.primary)
        async def join(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
            session = bot.active_sessions.get(btn_interaction.guild.id)
            if not session: return
            if btn_interaction.user.id in session['players']:
                await btn_interaction.response.send_message("أنت مسجل بالفعل!", ephemeral=True)
                return
            if len(session['players']) >= 10:
                await btn_interaction.response.send_message("العدد مكتمل!", ephemeral=True)
                return
            
            session['players'].append(btn_interaction.user.id)
            await btn_interaction.response.send_message("✅ تم تسجيلك!", ephemeral=True)
            await btn_interaction.message.edit(content=f"**المسجلون حالياً: {len(session['players'])}**")

    await interaction.response.send_message(embed=embed, view=JoinButton())

@bot.tree.command(name="begin_story", description="توزيع الأدوار وبدء القصة")
async def begin_story(interaction: discord.Interaction):
    session = bot.active_sessions.get(interaction.guild.id)
    if not session or len(session['players']) < 2:
        await interaction.response.send_message("❌ يجب تسجيل لاعبين اثنين على الأقل!", ephemeral=True)
        return

    await interaction.response.send_message("🏁 تبدأ اللعبة الآن... جاري توزيع الأدوار.")
    
    # توزيع الأدوار بذكاء
    players_ids = session['players'].copy()
    random.shuffle(players_ids)
    
    all_role_names = list(data.roles.ROLES.keys())
    mandatory = ["المحقق ياسين", "ياسر (الإبن)"]
    others = [r for r in all_role_names if r not in mandatory]
    random.shuffle(others)
    
    chosen_roles = mandatory + others[:len(players_ids)-2]
    random.shuffle(chosen_roles)

    roles_announcement = "📢 **الأدوار التي تم توزيعها في هذه الجلسة:**\n"
    
    for i, user_id in enumerate(players_ids):
        member = interaction.guild.get_member(user_id)
        role_name = chosen_roles[i]
        session['roles'][user_id] = role_name
        roles_announcement += f"🎭 {role_name}\n"
        
        # تغيير الاسم وإرسال الخاص
        try: await member.edit(nick=role_name)
        except: pass
        
        role_info = data.roles.ROLES[role_name]
        embed = discord.Embed(title=f"🎭 دورك: {role_name}", description=role_info, color=discord.Color.blue())
        try: await member.send(embed=embed)
        except: pass

    # إعلان الأدوار وتغيير الأسماء
    await interaction.followup.send(roles_announcement)
    await interaction.followup.send("✅ تم تغيير أسمائكم مؤقتاً لتناسب الشخصيات. تفاصيل أدواركم وأسراركم وصلتكم في الخاص! 🤫")

    # سرد القصة
    story_embed = discord.Embed(title="🏰 بداية القصة", description=data.story.STORY, color=discord.Color.gold())
    await interaction.followup.send(embed=story_embed)
    
    await asyncio.sleep(5)
    await interaction.followup.send(data.story.INITIAL_STATEMENTS)
    
    await asyncio.sleep(5)
    await utils.helpers.start_round(bot, interaction.guild.id, 1)

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
