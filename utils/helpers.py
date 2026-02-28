import discord
import asyncio
import data.questions as questions
import data.story as story
import data.roles as roles
import random

# ============================================
# بدء الجولة
# ============================================
async def start_round(bot, guild_id, round_num):
    session = bot.active_sessions.get(guild_id)
    if not session: return
    
    channel = bot.get_channel(session['channel_id'])
    guild = bot.get_guild(guild_id)
    
    clue = story.CLUES[round_num - 1]
    await channel.send(clue)

    detective_id = None
    for uid, role in session.get('roles', {}).items():
        if role.startswith("المحقق"):
            detective_id = uid
            break

    if detective_id:
        detective = guild.get_member(detective_id)
        if detective:
            await send_questions_to_detective(bot, guild_id, detective, round_num)
    else:
        await channel.send("⚠️ لم يتم العثور على المحقق!")

# ============================================
# إرسال الأسئلة للمحقق (في الخاص)
# ============================================
async def send_questions_to_detective(bot, guild_id, detective: discord.Member, round_num):
    q_list = questions.QUESTIONS_BY_ROUND[round_num]

    class QuestionSelectView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.selected = []
            self.guild_id = guild_id
            self.bot = bot

        @discord.ui.button(label=q_list[0][:80], style=discord.ButtonStyle.primary)
        async def q1(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
            await self.add_question(btn_interaction, q_list[0])

        @discord.ui.button(label=q_list[1][:80], style=discord.ButtonStyle.primary)
        async def q2(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
            await self.add_question(btn_interaction, q_list[1])

        @discord.ui.button(label=q_list[2][:80], style=discord.ButtonStyle.primary)
        async def q3(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
            await self.add_question(btn_interaction, q_list[2])

        @discord.ui.button(label=q_list[3][:80], style=discord.ButtonStyle.primary)
        async def q4(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
            await self.add_question(btn_interaction, q_list[3])

        async def add_question(self, btn_interaction, question):
            if len(self.selected) >= 2:
                await btn_interaction.response.send_message("✅ لقد اخترت سؤالين بالفعل!", ephemeral=True)
                return
            self.selected.append(question)
            await btn_interaction.response.send_message(f"✅ تم اختيار: {question}", ephemeral=True)
            
            if len(self.selected) == 2:
                await ask_all_suspects(self.bot, self.guild_id, self.selected, round_num)

    await detective.send("🕵️ **اختر سؤالين لهذه الجولة:**", view=QuestionSelectView())

# ============================================
# طرح الأسئلة على المشتبه بهم (بدون حرق)
# ============================================
async def ask_all_suspects(bot, guild_id, questions_list, round_num):
    session = bot.active_sessions.get(guild_id)
    if not session: return
    channel = bot.get_channel(session['channel_id'])
    guild = bot.get_guild(guild_id)

    if 'answers' not in session:
        session['answers'] = {}
    if round_num not in session['answers']:
        session['answers'][round_num] = {}

    for q in questions_list:
        # إنشاء View يحتوي على أزرار لكل شخصية
        class AnswersView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)

        view = AnswersView()

        # إضافة زر لكل مشتبه به
        for user_id, role in session['roles'].items():
            if role.startswith("المحقق"):
                continue
            member = guild.get_member(user_id)
            if not member:
                continue

            role_name = role.split(' (')[0] if ' (' in role else role

            button = discord.ui.Button(
                label=f"👤 {role_name}",
                style=discord.ButtonStyle.secondary,
                custom_id=f"ans_{user_id}_{round_num}"
            )

            async def button_callback(btn_interaction: discord.Interaction, 
                                     u_id=user_id, 
                                     u_role=role, 
                                     question=q):
                if btn_interaction.user.id != u_id:
                    await btn_interaction.response.send_message("❌ هذا الزر ليس لك!", ephemeral=True)
                    return

                role_answers = questions.ANSWERS.get(u_role, {})
                options = role_answers.get(question, ["لا يوجد إجابة متاحة"])

                # تحويل الخيارات إلى رموز بدون حرق
                symbols = ["🔴", "🔵", "🟢", "🟡"]
                symbol_options = []
                for i, opt in enumerate(options[:4]):
                    symbol_options.append(f"{symbols[i]}")

                class OptionView(discord.ui.View):
                    def __init__(self):
                        super().__init__(timeout=30)

                option_view = OptionView()

                for i, opt in enumerate(options[:4]):
                    opt_button = discord.ui.Button(
                        label=symbols[i],
                        style=discord.ButtonStyle.primary,
                        custom_id=f"opt_{u_id}_{i}"
                    )

                    async def opt_callback(opt_interaction: discord.Interaction, 
                                          opt_val=opt, 
                                          u_id_val=u_id, 
                                          q_val=question,
                                          symbol=symbols[i]):
                        if u_id_val not in session['answers'][round_num]:
                            session['answers'][round_num][u_id_val] = {}
                        session['answers'][round_num][u_id_val][q_val] = opt_val

                        # نرسل فقط الرمز بدون تفاصيل
                        role_name_display = u_role.split(' (')[0] if ' (' in u_role else u_role
                        await channel.send(f"✅ **{role_name_display}:** {symbol}")

                        await opt_interaction.response.send_message("✅ تم تسجيل إجابتك!", ephemeral=True)

                    opt_button.callback = opt_callback
                    option_view.add_item(opt_button)

                await btn_interaction.response.send_message("📝 **اختر إجابتك:**", view=option_view, ephemeral=True)

            button.callback = button_callback
            view.add_item(button)

        await channel.send(f"❓ **{q}**", view=view)
        await asyncio.sleep(20)

    await channel.send("⏳ جاري تحليل الإجابات...")
    await asyncio.sleep(5)
    
    # ما نرسل تقرير إلا في الجولة الثالثة
    if round_num == 3:
        await send_final_report(bot, guild_id)
    else:
        next_round = round_num + 1
        session['current_round'] = next_round
        await asyncio.sleep(5)
        await start_round(bot, guild_id, next_round)
    
    # المعلومات السرية تظل كما هي
    await send_hidden_info_to_all(bot, guild_id, round_num)

# ============================================
# إرسال المعلومات السرية (كما هي)
# ============================================
async def send_hidden_info_to_all(bot, guild_id, round_num):
    session = bot.active_sessions.get(guild_id)
    if not session: return
    guild = bot.get_guild(guild_id)

    hidden_messages = {
        1: {
            "المحقق ياسين": "🕯️ هند صادقة... ثق بها.",
            "لارا (الزوجة)": "🕯️ رامي سيحميك لكن لا تعتمدي عليه كلياً.",
            "ياسر (الإبن)": "🕯️ هند رأتك... احذر منها.",
            "ليلى (الإبنة)": "🕯️ فؤاد يحبك لكنه خائف.",
            "هند (الخادمة)": "🕯️ أنت الوحيدة الآمنة مع المحقق.",
            "رامي (الحارس)": "🕯️ لارا ستنكر معرفتها بك.",
            "نادين (الطاهية)": "🕯️ رامي ولارا يخافان منك.",
            "د. سلمى (الطبيبة)": "🕯️ ياسر كان ينتظرك تحت البرج.",
            "فؤاد (المحامي)": "🕯️ ليلى ستنكر معرفتها بك.",
            "عفاف (الجارة)": "🕯️ أنت المفتاح الحقيقي."
        },
        2: {
            "المحقق ياسين": "🕯️ ياسر متوتر جداً.",
            "لارا (الزوجة)": "🕯️ هند رأتك تخرجين من غرفة رامي.",
            "ياسر (الإبن)": "🕯️ عفاف تراقبك من الخارج.",
            "ليلى (الإبنة)": "🕯️ رأيت شيئاً... تذكري جيداً.",
            "هند (الخادمة)": "🕯️ ياسر يحاول كسبك لجانبه.",
            "رامي (الحارس)": "🕯️ عفاف رأتك... احذر.",
            "نادين (الطاهية)": "🕯️ أنت تعرفين أكثر مما تظنين.",
            "د. سلمى (الطبيبة)": "🕯️ فؤاد يشك فيك.",
            "فؤاد (المحامي)": "🕯️ عفاف تعرف شيئاً عنك.",
            "عفاف (الجارة)": "🕯️ انتظري الوقت المناسب."
        },
        3: {
            "المحقق ياسين": "🕯️ لارا تخفي علاقة مع رامي.",
            "لارا (الزوجة)": "🕯️ ياسر ينظر إليك بطريقة مريبة.",
            "ياسر (الإبن)": "🕯️ ليلى شكت فيك مؤخراً.",
            "ليلى (الإبنة)": "🕯️ ياسر أخوك... لكنه يخفي شيئاً.",
            "هند (الخادمة)": "🕯️ لارا تخاف منك لأنك تعرفين سرها.",
            "رامي (الحارس)": "🕯️ المفتاح عندك... لا تخبر أحداً.",
            "نادين (الطاهية)": "🕯️ ياسر كان غاضباً جداً.",
            "د. سلمى (الطبيبة)": "🕯️ المسدس ليس له علاقة.",
            "فؤاد (المحامي)": "🕯️ ياسر محروم من الوصية.",
            "عفاف (الجارة)": "🕯️ كلهم مذنبون بطريقتهم."
        }
    }

    for user_id, role in session['roles'].items():
        member = guild.get_member(user_id)
        if member:
            msg = hidden_messages.get(round_num, {}).get(role, "🕯️ لا توجد معلومات جديدة.")
            try:
                await member.send(msg)
            except:
                pass
            await asyncio.sleep(1)

# ============================================
# التقرير النهائي (بدون حرق)
# ============================================
async def send_final_report(bot, guild_id):
    session = bot.active_sessions.get(guild_id)
    if not session: return
    channel = bot.get_channel(session['channel_id'])
    guild = bot.get_guild(guild_id)

    final_report = "📋 **التقرير النهائي - تحليل التناقضات**\n\n"
    players_answers = {}
    
    for round_num in [1,2,3]:
        round_ans = session['answers'].get(round_num, {})
        for uid, ans_dict in round_ans.items():
            if uid not in players_answers:
                players_answers[uid] = {}
            for q, a in ans_dict.items():
                if q not in players_answers[uid]:
                    players_answers[uid][q] = []
                players_answers[uid][q].append(a)

    for uid, answers in players_answers.items():
        member = guild.get_member(uid)
        if not member: continue
        role_name = session['roles'].get(uid, "شخص")
        role_name = role_name.split(' (')[0] if ' (' in role_name else role_name
        
        # نحسب التناقضات بدون عرض التفاصيل
        contradictions = 0
        for q, ans_list in answers.items():
            if len(set(ans_list)) > 1:
                contradictions += 1
        
        if contradictions > 0:
            final_report += f"⚠️ **{role_name}:** لديه {contradictions} تناقض\n"
        else:
            final_report += f"✅ **{role_name}:** ثابت\n"

    await channel.send(final_report)
    await start_voting(bot, guild_id)

# ============================================
# التصويت (كما هو)
# ============================================
async def start_voting(bot, guild_id):
    session = bot.active_sessions.get(guild_id)
    if not session: return
    channel = bot.get_channel(session['channel_id'])
    guild = bot.get_guild(guild_id)

    class VoteView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.votes = {}

    view = VoteView()

    for user_id, role in session['roles'].items():
        if role.startswith("المحقق"):
            continue
        role_name = role.split(' (')[0] if ' (' in role else role
        member = guild.get_member(user_id)
        if member:
            button = discord.ui.Button(
                label=role_name,
                style=discord.ButtonStyle.danger,
                custom_id=f"vote_{user_id}"
            )

            async def vote_callback(btn_interaction: discord.Interaction, 
                                   u_id=user_id, 
                                   r_name=role_name):
                if btn_interaction.user.id in view.votes:
                    await btn_interaction.response.send_message("❌ لقد صوت مسبقاً!", ephemeral=True)
                    return
                view.votes[btn_interaction.user.id] = r_name
                await btn_interaction.response.send_message(f"🗳️ تم التصويت لـ {r_name}", ephemeral=True)

            button.callback = vote_callback
            view.add_item(button)

    await channel.send("🗳️ **التصويت على القاتل:**", view=view)
    await asyncio.sleep(120)
    await show_vote_result(bot, guild_id)

# ============================================
# عرض النتيجة
# ============================================
async def show_vote_result(bot, guild_id):
    session = bot.active_sessions.get(guild_id)
    if not session: return
    channel = bot.get_channel(session['channel_id'])

    result_message = """
🥁 **انتهى التصويت!**

🔪 **القاتل الحقيقي هو: ياسر (الإبن)!**

📖 **تفاصيل الجريمة:**
- دخل ياسر البرج ليهدد والده
- تطور الشجار فدفعه فوقع على الطاولة
- رمى المسدس في الحديقة وحاول التغطية
- هند رأته يخرج، وعفاف شاهدته يخبئ المسدس

🏆 **شكراً للمشاركين!**
"""
    await channel.send(result_message)
    
    if guild_id in bot.active_sessions:
        del bot.active_sessions[guild_id]
