import discord
import asyncio
from data import questions, story
from data.roles import ROLES

# دوال مساعدة للعبة

async def start_round(bot, interaction, round_num):
    """بدء جولة جديدة (إرسال الدليل وطلب الأسئلة من المحقق)"""
    guild_id = interaction.guild.id
    session = bot.active_sessions.get(guild_id)
    if not session:
        return

    # إرسال الدليل
    clue = story.CLUES[round_num - 1]
    await interaction.followup.send(clue)

    # العثور على المحقق
    detective_id = None
    detective_role = None
    for uid, role in session.get('roles', {}).items():
        if role.startswith("المحقق"):
            detective_id = uid
            detective_role = role
            break

    if detective_id:
        detective = interaction.guild.get_member(detective_id)
        if detective:
            await send_questions_to_detective(bot, interaction, detective, round_num)
    else:
        await interaction.followup.send("⚠️ لم يتم العثور على المحقق!")

async def send_questions_to_detective(bot, interaction, detective: discord.Member, round_num):
    """إرسال قائمة الأسئلة للمحقق (4 أزرار) ليختار 2"""
    q_list = questions.QUESTIONS_BY_ROUND[round_num]

    class QuestionSelectView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.selected = []

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
                # إرسال الأسئلة لجميع المشتبه بهم
                await ask_all_suspects(bot, btn_interaction, self.selected, round_num)

    await detective.send("🕵️ **اختر سؤالين لهذه الجولة:**", view=QuestionSelectView())

async def ask_all_suspects(bot, interaction, questions_list, round_num):
    """طرح كل سؤال على جميع المشتبه بهم (ما عدا المحقق)"""
    guild_id = interaction.guild.id
    session = bot.active_sessions.get(guild_id)
    if not session:
        return

    # تجهيز مكان لحفظ الإجابات
    if 'answers' not in session:
        session['answers'] = {}
    if round_num not in session['answers']:
        session['answers'][round_num] = {}

    # لكل سؤال
    for q in questions_list:
        await interaction.followup.send(f"❓ **السؤال:** {q}")
        # نرسل لكل مشتبه به (عدا المحقق) خياراته
        for user_id, role in session['roles'].items():
            if role.startswith("المحقق"):
                continue
            member = interaction.guild.get_member(user_id)
            if not member:
                continue

            # جلب خيارات هذا الشخص لهذا السؤال
            role_answers = questions.ANSWERS.get(role, {})
            options = role_answers.get(q, ["لا يوجد إجابة متاحة"])

            # بناء View بخيارات (أزرار) - 4 أزرار كحد أقصى
            view = discord.ui.View(timeout=60)
            for i, opt in enumerate(options[:4]):
                button = discord.ui.Button(label=opt[:80], style=discord.ButtonStyle.secondary)
                async def button_callback(btn_interaction, opt=opt):
                    # تخزين الإجابة
                    if user_id not in session['answers'][round_num]:
                        session['answers'][round_num][user_id] = {}
                    session['answers'][round_num][user_id][q] = opt
                    await btn_interaction.response.send_message("✅ تم تسجيل إجابتك", ephemeral=True)
                button.callback = button_callback
                view.add_item(button)

            try:
                await member.send(f"❓ **{q}**\nاختر إجابتك:", view=view)
            except discord.Forbidden:
                await interaction.followup.send(f"⚠️ {member.mention} الخاص مقفول، ما وصلته الأسئلة!", ephemeral=False)

            await asyncio.sleep(1)

    # بعد انتهاء الأسئلة، ننتظر قليلاً ثم نرسل التقرير المرحلي والمعلومات المخفية
    await asyncio.sleep(10)
    await send_round_report(bot, interaction, round_num)
    await send_hidden_info_to_all(bot, interaction, round_num)

async def send_hidden_info_to_all(bot, interaction, round_num):
    """إرسال معلومة سرية لكل عضو بعد انتهاء الجولة"""
    guild_id = interaction.guild.id
    session = bot.active_sessions.get(guild_id)
    if not session:
        return

    # معلومات سرية محددة مسبقاً لكل شخصية ولكل جولة
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

    # إرسال لكل عضو رسالته الخاصة حسب دوره
    for user_id, role in session['roles'].items():
        member = interaction.guild.get_member(user_id)
        if member:
            msg = hidden_messages.get(round_num, {}).get(role, "🕯️ لا توجد معلومات جديدة.")
            try:
                await member.send(msg)
            except:
                pass
            await asyncio.sleep(1)

async def send_round_report(bot, interaction, round_num):
    """إرسال تقرير مرحلي بعد انتهاء الجولة"""
    guild_id = interaction.guild.id
    session = bot.active_sessions.get(guild_id)
    if not session:
        return

    round_answers = session['answers'].get(round_num, {})
    if not round_answers:
        await interaction.followup.send("📊 لا توجد إجابات مسجلة لهذه الجولة.")
    else:
        report = f"📋 **تقرير الجولة {round_num}**\n\n"
        for user_id, ans_dict in round_answers.items():
            member = interaction.guild.get_member(user_id)
            name = member.display_name if member else "شخص"
            report += f"**{name}:**\n"
            for q, a in ans_dict.items():
                # اختصار السؤال إذا كان طويلاً
                short_q = q[:30] + "..." if len(q) > 30 else q
                report += f"> {short_q}\n> {a}\n\n"
        # تقطيع إذا كان طويلاً
        if len(report) > 2000:
            part1 = report[:2000]
            part2 = report[2000:]
            await interaction.followup.send(part1)
            await asyncio.sleep(1)
            await interaction.followup.send(part2)
        else:
            await interaction.followup.send(report)

    # التحقق مما إذا كانت هذه الجولة الثالثة
    if round_num == 3:
        await send_final_report(bot, interaction)
    else:
        # ننتقل للجولة التالية
        next_round = round_num + 1
        session['current_round'] = next_round
        await asyncio.sleep(5)
        await start_round(bot, interaction, next_round)

async def send_final_report(bot, interaction):
    """إرسال التقرير النهائي ومقارنة الإجابات عبر الجولات"""
    guild_id = interaction.guild.id
    session = bot.active_sessions.get(guild_id)
    if not session:
        return

    final_report = "📋 **التقرير النهائي - مقارنة الإجابات**\n\n"
    # تجميع إجابات كل لاعب عبر الجولات
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

    # تحليل التناقضات
    for uid, answers in players_answers.items():
        member = interaction.guild.get_member(uid)
        name = member.display_name if member else "شخص"
        final_report += f"**{name}:**\n"
        contradictions = 0
        for q, ans_list in answers.items():
            short_q = q[:30] + "..." if len(q) > 30 else q
            final_report += f"> {short_q} : "
            if len(set(ans_list)) > 1:
                # عرض أول إجابتين مختلفتين فقط للاختصار
                unique_ans = list(set(ans_list))
                display_ans = unique_ans[0][:30] + "..." if len(unique_ans[0]) > 30 else unique_ans[0]
                display_ans2 = unique_ans[1][:30] + "..." if len(unique_ans[1]) > 30 else unique_ans[1]
                final_report += f"⚠️ تناقض! (قال: {display_ans} ثم {display_ans2})\n"
                contradictions += 1
            else:
                display_a = ans_list[0][:50] + "..." if len(ans_list[0]) > 50 else ans_list[0]
                final_report += f"✅ ثابت: {display_a}\n"
        if contradictions > 0:
            final_report += f"🔴 عدد التناقضات: {contradictions}\n\n"
        else:
            final_report += "🟢 لا تناقضات\n\n"

    if len(final_report) > 2000:
        part1 = final_report[:2000]
        part2 = final_report[2000:]
        await interaction.followup.send(part1)
        await asyncio.sleep(1)
        await interaction.followup.send(part2)
    else:
        await interaction.followup.send(final_report)

    # بدء التصويت
    await start_voting(bot, interaction)

async def start_voting(bot, interaction):
    """بدء التصويت على القاتل"""
    guild_id = interaction.guild.id
    session = bot.active_sessions.get(guild_id)
    if not session:
        return

    # إنشاء أزرار للشخصيات (باستثناء المحقق)
    class VoteView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=180)
            self.votes = {}

        @discord.ui.button(label="لارا", style=discord.ButtonStyle.danger)
        async def vote_lara(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
            await self.record_vote(btn_interaction, "لارا (الزوجة)")

        @discord.ui.button(label="ياسر", style=discord.ButtonStyle.danger)
        async def vote_yaser(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
            await self.record_vote(btn_interaction, "ياسر (الإبن)")

        @discord.ui.button(label="ليلى", style=discord.ButtonStyle.danger)
        async def vote_layla(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
            await self.record_vote(btn_interaction, "ليلى (الإبنة)")

        @discord.ui.button(label="هند", style=discord.ButtonStyle.danger)
        async def vote_hind(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
            await self.record_vote(btn_interaction, "هند (الخادمة)")

        @discord.ui.button(label="رامي", style=discord.ButtonStyle.danger)
        async def vote_rami(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
            await self.record_vote(btn_interaction, "رامي (الحارس)")

        @discord.ui.button(label="نادين", style=discord.ButtonStyle.danger)
        async def vote_nadin(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
            await self.record_vote(btn_interaction, "نادين (الطاهية)")

        @discord.ui.button(label="د. سلمى", style=discord.ButtonStyle.danger)
        async def vote_salma(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
            await self.record_vote(btn_interaction, "د. سلمى (الطبيبة)")

        @discord.ui.button(label="فؤاد", style=discord.ButtonStyle.danger)
        async def vote_fuad(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
            await self.record_vote(btn_interaction, "فؤاد (المحامي)")

        @discord.ui.button(label="عفاف", style=discord.ButtonStyle.danger)
        async def vote_afaf(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
            await self.record_vote(btn_interaction, "عفاف (الجارة)")

        async def record_vote(self, btn_interaction, suspect_role):
            if btn_interaction.user.id in self.votes:
                await btn_interaction.response.send_message("❌ لقد صوت مسبقاً!", ephemeral=True)
                return
            self.votes[btn_interaction.user.id] = suspect_role
            await btn_interaction.response.send_message(f"🗳️ صوتك مسجل لصالح {suspect_role}", ephemeral=True)

    await interaction.followup.send("🗳️ **التصويت على القاتل:** اختر شخصاً واحداً", view=VoteView())
    # ننتظر 3 دقائق ثم نعرض النتيجة
    await asyncio.sleep(180)
    await show_vote_result(bot, interaction)

async def show_vote_result(bot, interaction):
    """عرض نتيجة التصويت وكشف القاتل الحقيقي"""
    guild_id = interaction.guild.id
    session = bot.active_sessions.get(guild_id)
    if not session:
        return

    # هنا يجب جمع الأصوات من الجلسة، لكن للتبسيط سنعرض نتيجة افتراضية مع إمكانية التعديل
    # القاتل الحقيقي مفروض يكون ياسر (الإبن)
    result_message = """
🥁 **نتيجة التصويت:**

(هنا سيتم عرض تفاصيل الأصوات)

🔪 **القاتل الحقيقي هو: ياسر (الإبن)!**

📖 **تفاصيل الجريمة:**
- دخل ياسر البرج ليهدد والده
- تطور الشجار فدفعه فوقع على الطاولة
- رمى المسدس في الحديقة وحاول التغطية
- هند رأته يخرج، وعفاف شاهدته يخبئ المسدس

🏆 **شكراً للمشاركين!** نراكم في فعالية قادمة.
"""
    await interaction.followup.send(result_message)

    # إعادة الأسماء الأصلية (اختياري)
    # يمكن إضافة دالة لاستعادة الأسماء
    await restore_original_names(bot, interaction)
