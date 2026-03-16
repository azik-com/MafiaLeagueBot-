# =============================================
#  MAFIA BOT — Bitta fayl (Pydroid3 uchun)
#  pip install python-telegram-bot
# =============================================
import asyncio
import random
import logging
from dataclasses import dataclass, field
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO)

# ── TOKEN ──────────────────────────────────────
import os
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# ── SOZLAMALAR ─────────────────────────────────
MIN_PLAYERS  = 4
NIGHT_TIME   = 45   # soniya
DAY_TIME     = 90   # soniya

# ── ROLLAR ─────────────────────────────────────
ROLES_INFO = {
    "tinch":     {"nom": "Tinch aholi", "emoji": "👤", "fraksiya": "tinch"},
    "mafia":     {"nom": "Mafia",       "emoji": "🔴", "fraksiya": "mafia"},
    "don":       {"nom": "Don",         "emoji": "👑", "fraksiya": "mafia"},
    "sherif":    {"nom": "Sherif",      "emoji": "👮", "fraksiya": "tinch"},
    "doktor":    {"nom": "Doktor",      "emoji": "🩺", "fraksiya": "tinch"},
    "detektiv":  {"nom": "Detektiv",    "emoji": "🕵", "fraksiya": "tinch"},
    "sevgilisi": {"nom": "Sevgilisi",   "emoji": "💘", "fraksiya": "tinch"},
    "maniac":    {"nom": "Maniac",      "emoji": "🔪", "fraksiya": "yolgiz"},
    "terrorchi": {"nom": "Terrorchi",   "emoji": "💣", "fraksiya": "tinch"},
}

ROL_TAVSIFLARI = {
    "tinch":     "👤 <b>Tinch aholi</b>\n\nOddiy fuqaro. Kunduz ovoz bering.\n🎯 Barcha mafiachini haydang!",
    "mafia":     "🔴 <b>Mafia a'zosi</b>\n\nKecha jabrlanuvchi tanlang. Don bilan ishlaysiz.\n🎯 Tinch aholini kamaytiring!",
    "don":       "👑 <b>Don</b>\n\nMafia boshlig'i! Sherif sizni 'tinch' ko'radi.\n🎯 Shaharni qo'lga oling!",
    "sherif":    "👮 <b>Sherif</b>\n\nKecha bir o'yinchini tekshiring (mafia/tinch).\n⚠️ Don tekshirilganda 'tinch' ko'rinadi!\n🎯 Mafiachini aniqlang!",
    "doktor":    "🩺 <b>Doktor</b>\n\nKecha bir o'yinchini davolang (o'zingizni ham).\n🎯 Jabrlanuvchilarni qutqaring!",
    "detektiv":  "🕵 <b>Detektiv</b>\n\nKecha birovning ANIQ rolini biling.\n🎯 Sirni oshkor qiling!",
    "sevgilisi": "💘 <b>Sevgilisi</b>\n\nSizga sevgilingiz borligini bot aytadi.\n⚠️ Sevgilingiz o'lsa — siz ham o'lasiz!\n🎯 Sevgilini asrang!",
    "maniac":    "🔪 <b>Maniac</b>\n\nYolg'iz bo'ri! Kecha hamma ni o'ldira olasiz.\nSherif: 'begona' ko'radi.\n🎯 Faqat siz tirik qolishingiz kerak!",
    "terrorchi": "💣 <b>Terrorchi</b>\n\nO'ldirilsangiz — o'ldiruvchi ham portlaydi!\n🎯 Yashang va dushmanlarni qo'rqiting!",
}

ROLE_DIST = {
    4:  {"mafia":1,"sherif":1},
    5:  {"mafia":1,"sherif":1,"doktor":1},
    6:  {"mafia":1,"sherif":1,"doktor":1,"sevgilisi":1},
    7:  {"mafia":1,"don":1,"sherif":1,"doktor":1,"sevgilisi":1},
    8:  {"mafia":1,"don":1,"sherif":1,"doktor":1,"detektiv":1,"sevgilisi":1},
    9:  {"mafia":2,"don":1,"sherif":1,"doktor":1,"sevgilisi":1,"terrorchi":1},
    10: {"mafia":2,"don":1,"sherif":1,"doktor":1,"detektiv":1,"sevgilisi":1,"maniac":1},
    12: {"mafia":2,"don":1,"sherif":1,"doktor":1,"detektiv":1,"sevgilisi":1,"maniac":1,"terrorchi":1},
}

def get_roles_list(n):
    best = max((k for k in ROLE_DIST if k <= n), default=4)
    dist = dict(ROLE_DIST[best])
    dist["tinch"] = n - sum(dist.values())
    result = []
    for role, cnt in dist.items():
        result.extend([role] * cnt)
    return result

# ── O'YINCHI ───────────────────────────────────
@dataclass
class Player:
    uid: int
    name: str
    username: Optional[str]
    role: str = ""
    alive: bool = True
    lover_id: Optional[int] = None
    night_action: Optional[int] = None
    day_vote: Optional[int] = None

    def mention(self):
        return f"@{self.username}" if self.username else self.name

    def role_display(self):
        r = ROLES_INFO.get(self.role, {})
        return f"{r.get('emoji','?')} {r.get('nom','?')}"

# ── O'YIN ──────────────────────────────────────
@dataclass
class Game:
    chat_id: int
    admin_id: int
    players: dict = field(default_factory=dict)
    phase: str = "lobby"
    round: int = 0
    winner: Optional[str] = None
    start_time: float = 0.0

    def alive_list(self):
        return [p for p in self.players.values() if p.alive]

    def alive_count(self):
        return sum(1 for p in self.players.values() if p.alive)

    def add_player(self, uid, name, username):
        if uid in self.players:
            return False
        self.players[uid] = Player(uid, name, username)
        return True

    def assign_roles(self):
        import time
        self.start_time = time.time()
        uids = list(self.players.keys())
        roles = get_roles_list(len(uids))
        random.shuffle(roles)
        random.shuffle(uids)
        for uid, role in zip(uids, roles):
            self.players[uid].role = role
        # Sevgilisi partner
        for p in self.players.values():
            if p.role == "sevgilisi":
                others = [x for x in self.players.values() if x.uid != p.uid]
                if others:
                    partner = random.choice(others)
                    p.lover_id = partner.uid
                    partner.lover_id = p.uid

    def start_night(self):
        self.phase = "night"
        self.round += 1
        for p in self.players.values():
            p.night_action = None

    def start_day(self):
        self.phase = "day"
        for p in self.players.values():
            p.day_vote = None

    def process_night(self):
        alive = {p.uid: p for p in self.alive_list()}
        events = []

        healed_id = next((p.night_action for p in self.alive_list()
                          if p.role == "doktor" and p.night_action), None)

        # Mafia ovozi
        mafia_votes = {}
        for p in self.alive_list():
            if p.role in {"mafia","don"} and p.night_action:
                mafia_votes[p.night_action] = mafia_votes.get(p.night_action, 0) + 1
        mafia_target = max(mafia_votes, key=mafia_votes.get) if mafia_votes else None

        # Maniac ovozi
        maniac_target = next((p.night_action for p in self.alive_list()
                               if p.role == "maniac" and p.night_action), None)

        to_kill = set()
        killer_of = {}
        if mafia_target and mafia_target != healed_id:
            to_kill.add(mafia_target)
            killers = [p.uid for p in self.alive_list() if p.role in {"mafia","don"}]
            if killers:
                killer_of[mafia_target] = killers[0]
        if maniac_target and maniac_target != healed_id:
            to_kill.add(maniac_target)
            maniac_p = next((p for p in self.alive_list() if p.role == "maniac"), None)
            if maniac_p:
                killer_of[maniac_target] = maniac_p.uid

        dead_this_night = []
        for uid in list(to_kill):
            victim = alive.get(uid)
            if not victim:
                continue
            if victim.role == "terrorchi":
                killer_id = killer_of.get(uid)
                if killer_id and killer_id in alive:
                    killer = alive[killer_id]
                    killer.alive = False
                    dead_this_night.append(killer)
                    events.append(f"💥 {victim.mention()} Terrorchi edi! {killer.mention()} ham portladi!")
            victim.alive = False
            dead_this_night.append(victim)

        if not dead_this_night:
            if healed_id and (mafia_target or maniac_target):
                events.append("✨ Hujum bo'ldi, lekin doktor qutqardi!")
            else:
                events.append("😴 Kechasi hech kim o'lmadi.")
        else:
            for p in dead_this_night:
                if p.role != "terrorchi":
                    events.append(f"💀 {p.mention()} ({p.role_display()}) o'ldirildi!")

        # Sevgilisi effekti
        for dead in list(dead_this_night):
            if dead.lover_id and dead.lover_id in alive:
                lover = alive[dead.lover_id]
                if lover.alive:
                    lover.alive = False
                    dead_this_night.append(lover)
                    events.append(f"💔 {lover.mention()} sevgilisiz yasha olmasdi...")
        return events

    def process_day_vote(self):
        tally = {}
        for p in self.alive_list():
            if p.day_vote and p.day_vote != -1:
                tally[p.day_vote] = tally.get(p.day_vote, 0) + 1
        if not tally:
            return {"type": "skip"}
        max_v = max(tally.values())
        top = [uid for uid, v in tally.items() if v == max_v]
        if len(top) > 1:
            return {"type": "tie"}
        exiled = self.players.get(top[0])
        lovers_died = []
        if exiled:
            exiled.alive = False
            if exiled.lover_id:
                lover = self.players.get(exiled.lover_id)
                if lover and lover.alive:
                    lover.alive = False
                    lovers_died.append(lover)
        return {"type": "exile", "player": exiled, "votes": max_v, "lovers": lovers_died}

    def check_winner(self):
        alive = self.alive_list()
        if not alive:
            self.winner = "nobody"; return "nobody"
        mafia = [p for p in alive if ROLES_INFO.get(p.role,{}).get("fraksiya") == "mafia"]
        maniacs = [p for p in alive if p.role == "maniac"]
        if maniacs and len(alive) == 1:
            self.winner = "maniac"; return "maniac"
        if not mafia:
            if not maniacs:
                self.winner = "town"; return "town"
        non_mafia = len(alive) - len(mafia)
        if len(mafia) >= non_mafia:
            self.winner = "mafia"; return "mafia"
        return None

    def final_roles_text(self):
        lines = []
        for p in self.players.values():
            s = "💀" if not p.alive else "✅"
            lines.append(f"{s} {p.mention()} — {p.role_display()}")
        return "\n".join(lines)

# ── GLOBAL O'YINLAR ────────────────────────────
GAMES: dict[int, Game] = {}

# ── YORDAMCHI ──────────────────────────────────
def player_keyboard(game: Game, exclude_uid=None, skip_btn=False):
    btns = []
    for p in game.alive_list():
        if p.uid == exclude_uid:
            continue
        btns.append([InlineKeyboardButton(p.mention(), callback_data=f"sel_{p.uid}")])
    if skip_btn:
        btns.append([InlineKeyboardButton("⏭ Hech kim", callback_data="sel_skip")])
    return InlineKeyboardMarkup(btns)

def find_game_by_player(uid):
    for g in GAMES.values():
        if uid in g.players:
            return g
    return None

async def send_role(ctx, game, uid):
    p = game.players[uid]
    desc = ROL_TAVSIFLARI.get(p.role, "")
    await ctx.bot.send_message(
        chat_id=uid,
        text=f"🎭 <b>Sizning rolingiz:</b>\n\n{desc}\n\n🤫 Bu sir!",
        parse_mode=ParseMode.HTML
    )
    # Mafia jamoasini ko'rsatish
    if p.role in {"mafia","don"}:
        team = [x for x in game.players.values() if x.role in {"mafia","don"}]
        members = "\n".join(f"  {ROLES_INFO[x.role]['emoji']} {x.mention()}" for x in team)
        await ctx.bot.send_message(
            chat_id=uid,
            text=f"🔴 <b>Mafia safingiz:</b>\n\n{members}",
            parse_mode=ParseMode.HTML
        )
    # Sevgilisi partnerini ko'rsatish
    if p.lover_id:
        partner = game.players.get(p.lover_id)
        if partner:
            await ctx.bot.send_message(
                chat_id=uid,
                text=f"💘 <b>Muhabbat!</b>\n\nSiz <b>{partner.mention()}</b> ga ko'ngil qo'ygansiz!\nU o'lsa — siz ham o'lasiz 💔",
                parse_mode=ParseMode.HTML
            )

# ── BUYRUQLAR ──────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text(
            "🎭 <b>Mafia Bot ga xush kelibsiz!</b>\n\n"
            "Guruhga /newgame yuboring, keyin /join bilan qo'shiling.\n"
            "Admin /start_game bilan boshlaydi.\n\n"
            "/help — qoidalar",
            parse_mode=ParseMode.HTML
        )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 <b>Buyruqlar:</b>\n"
        "/newgame — Yangi o'yin (guruhda)\n"
        "/join — O'yinga qo'shilish\n"
        "/start_game — Boshlash (admin)\n"
        "/cancel_game — Bekor qilish (admin)\n"
        "/players — O'yinchilar ro'yxati\n\n"
        "👤 Tinch aholi | 🔴 Mafia | 👑 Don\n"
        "👮 Sherif | 🩺 Doktor | 🕵 Detektiv\n"
        "💘 Sevgilisi | 🔪 Maniac | 💣 Terrorchi",
        parse_mode=ParseMode.HTML
    )

async def cmd_newgame(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if update.effective_chat.type == "private":
        await update.message.reply_text("⚠️ Faqat guruhlarda ishlaydi.")
        return
    if cid in GAMES:
        await update.message.reply_text("⚠️ O'yin allaqachon mavjud!")
        return
    GAMES[cid] = Game(chat_id=cid, admin_id=update.effective_user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🙋 Qo'shilish", callback_data="join_game")],
        [InlineKeyboardButton("👥 O'yinchilar", callback_data="show_players")]
    ])
    await update.message.reply_text(
        f"🎭 <b>Yangi Mafia o'yini!</b>\n\n"
        f"👥 O'yinchilar: 0/{MIN_PLAYERS} (min)\n"
        f"Qo'shilish uchun /join yoki tugmani bosing.\n"
        f"Admin /start_game bilan boshlaydi.",
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )

async def cmd_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if update.effective_chat.type == "private":
        await update.message.reply_text("⚠️ Faqat guruhlarda ishlaydi.")
        return
    game = GAMES.get(cid)
    if not game:
        await update.message.reply_text("❌ Hozir o'yin yo'q. /newgame")
        return
    if game.phase != "lobby":
        await update.message.reply_text("⚠️ O'yin allaqachon boshlangan!")
        return
    u = update.effective_user
    if game.add_player(u.id, u.full_name, u.username):
        await update.message.reply_text(
            f"✅ <b>{u.full_name}</b> qo'shildi! ({len(game.players)} o'yinchi)",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text("⚠️ Siz allaqachon ro'yxatda!")

async def cmd_players(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    game = GAMES.get(cid)
    if not game:
        await update.message.reply_text("❌ Hozir o'yin yo'q.")
        return
    if game.phase == "lobby":
        lines = "\n".join(f"{i}. {p.mention()}" for i,p in enumerate(game.players.values(),1))
        await update.message.reply_text(
            f"👥 <b>O'yinchilar ({len(game.players)}):</b>\n\n{lines or 'Hali hech kim yo\'q'}",
            parse_mode=ParseMode.HTML
        )
    else:
        lines = "\n".join(f"{'💀' if not p.alive else '🔵'} {p.mention()}" for p in game.players.values())
        await update.message.reply_text(
            f"👥 <b>Tirik: {game.alive_count()} ta</b>\n\n{lines}",
            parse_mode=ParseMode.HTML
        )

async def cmd_start_game(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    uid = update.effective_user.id
    game = GAMES.get(cid)
    if not game:
        await update.message.reply_text("❌ O'yin yo'q.")
        return
    if game.phase != "lobby":
        await update.message.reply_text("⚠️ O'yin allaqachon boshlangan!")
        return
    if uid != game.admin_id:
        await update.message.reply_text("🔒 Faqat admin boshlaydi.")
        return
    if len(game.players) < MIN_PLAYERS:
        await update.message.reply_text(f"❌ Kamida {MIN_PLAYERS} o'yinchi kerak. Hozir: {len(game.players)}")
        return

    game.assign_roles()
    await update.message.reply_text(
        f"🎲 <b>O'yin boshlanmoqda!</b>\n👥 {len(game.players)} o'yinchi\n📩 Rollar yuborilmoqda...",
        parse_mode=ParseMode.HTML
    )
    for player_uid in game.players:
        try:
            await send_role(ctx, game, player_uid)
            await asyncio.sleep(0.3)
        except Exception as e:
            logging.warning(f"Rol yuborib bo'lmadi {player_uid}: {e}")

    await asyncio.sleep(2)
    await do_night(cid, ctx, game)

async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    uid = update.effective_user.id
    game = GAMES.get(cid)
    if not game:
        await update.message.reply_text("❌ O'yin yo'q.")
        return
    if uid != game.admin_id:
        await update.message.reply_text("🔒 Faqat admin bekor qiladi.")
        return
    del GAMES[cid]
    await update.message.reply_text("🚫 O'yin bekor qilindi.")

# ── KECHA FAZASI ───────────────────────────────
async def do_night(cid, ctx, game):
    game.start_night()
    await ctx.bot.send_message(
        chat_id=cid,
        text=f"🌙 <b>{game.round}-kecha boshlanmoqda...</b>\n\n"
             f"Shahar uxlayapti. Maxsus rollar harakat qilsin!\n"
             f"⏰ Vaqt: <b>{NIGHT_TIME} soniya</b>",
        parse_mode=ParseMode.HTML
    )
    night_roles = {"mafia","don","sherif","doktor","detektiv","maniac"}
    for p in game.alive_list():
        if p.role not in night_roles:
            continue
        prompts = {
            "mafia":    "🔴 Kimni o'ldirasiz?",
            "don":      "👑 Kimni o'ldirishni buyurasiz?",
            "sherif":   "👮 Kimni tekshirasiz?",
            "doktor":   "🩺 Kimni davolaymiz?",
            "detektiv": "🕵 Kimning rolini bilmoqchisiz?",
            "maniac":   "🔪 Kimni yo'q qilasiz?",
        }
        excl = p.uid if p.role in {"sherif","doktor","detektiv","maniac"} else None
        try:
            await ctx.bot.send_message(
                chat_id=p.uid,
                text=prompts[p.role],
                parse_mode=ParseMode.HTML,
                reply_markup=player_keyboard(game, exclude_uid=excl)
            )
        except Exception as e:
            logging.warning(f"Kecha xabar yuborib bo'lmadi {p.uid}: {e}")

    async def night_timer():
        await asyncio.sleep(NIGHT_TIME)
        g = GAMES.get(cid)
        if g and g.phase == "night":
            await finish_night(cid, ctx, g)
    asyncio.create_task(night_timer())

async def finish_night(cid, ctx, game):
    events = game.process_night()
    summary = "\n".join(events)
    await ctx.bot.send_message(
        chat_id=cid,
        text=f"🌅 <b>Tong otdi!</b>\n\n{summary}",
        parse_mode=ParseMode.HTML
    )
    winner = game.check_winner()
    if winner:
        await announce_winner(cid, ctx, game)
        return
    await asyncio.sleep(2)
    await do_day(cid, ctx, game)

# ── KUNDUZ FAZASI ──────────────────────────────
async def do_day(cid, ctx, game):
    game.start_day()
    alive_text = "\n".join(f"🔵 {p.mention()}" for p in game.alive_list())
    await ctx.bot.send_message(
        chat_id=cid,
        text=f"☀️ <b>{game.round}-kun</b>\n\n"
             f"<b>Tirik o'yinchilar:</b>\n{alive_text}\n\n"
             f"🗳 Kimni haydaymiz?\n⏰ <b>{DAY_TIME} soniya</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=player_keyboard(game, skip_btn=True)
    )
    async def day_timer():
        await asyncio.sleep(DAY_TIME)
        g = GAMES.get(cid)
        if g and g.phase == "day":
            await finish_day(cid, ctx, g)
    asyncio.create_task(day_timer())

async def finish_day(cid, ctx, game):
    result = game.process_day_vote()
    if result["type"] == "exile" and result.get("player"):
        p = result["player"]
        r = ROLES_INFO.get(p.role, {})
        await ctx.bot.send_message(
            chat_id=cid,
            text=f"🔨 <b>{p.mention()}</b> ({result['votes']} ovoz) haydaldi!\n"
                 f"Roli: {r.get('emoji','')} <b>{r.get('nom','')}</b>",
            parse_mode=ParseMode.HTML
        )
        for lover in result.get("lovers", []):
            await ctx.bot.send_message(
                chat_id=cid,
                text=f"💔 {lover.mention()} sevgilisiz yasha olmasdi...",
                parse_mode=ParseMode.HTML
            )
    elif result["type"] == "tie":
        await ctx.bot.send_message(cid, "🤝 Ovoz tenglashdi! Hech kim haydalmadi.")
    else:
        await ctx.bot.send_message(cid, "⏭ Aholi hech kimni haydamaslikka qaror qildi.")

    winner = game.check_winner()
    if winner:
        await announce_winner(cid, ctx, game)
        return
    await asyncio.sleep(2)
    await do_night(cid, ctx, game)

# ── G'OLIB ─────────────────────────────────────
async def announce_winner(cid, ctx, game):
    import time
    secs = int(time.time() - game.start_time)
    m, s = divmod(secs, 60)
    win_msgs = {
        "town":   "🎉 <b>TINCH AHOLI YUTDI!</b>\nBarcha mafia haydaldi!",
        "mafia":  "💀 <b>MAFIA YUTDI!</b>\nShahar qo'lga olindi!",
        "maniac": "🔪 <b>MANIAC YUTDI!</b>\nYolg'iz bo'ri hammani yo'q qildi!",
        "nobody": "👻 <b>HECH KIM YUTMADI!</b>\nShahar bo'sh qoldi...",
    }
    roles_text = game.final_roles_text()
    await ctx.bot.send_message(
        chat_id=cid,
        text=f"{win_msgs.get(game.winner, '🏁 Oyin tugadi!')}\n\n"
             f"⏱ {m} daqiqa {s} soniya | 🔄 {game.round} tur\n\n"
             f"<b>Barcha rollar:</b>\n{roles_text}",
        parse_mode=ParseMode.HTML
    )
    del GAMES[cid]

# ── CALLBACK HANDLER ───────────────────────────
async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    uid = q.from_user.id
    cid = q.message.chat_id
    chat_type = q.message.chat.type

    # Lobby tugmalari
    if data == "join_game":
        game = GAMES.get(cid)
        if not game:
            await q.answer("O'yin yo'q!", show_alert=True); return
        if game.phase != "lobby":
            await q.answer("O'yin boshlangan!", show_alert=True); return
        u = q.from_user
        if game.add_player(u.id, u.full_name, u.username):
            await ctx.bot.send_message(
                cid,
                f"✅ <b>{u.full_name}</b> qo'shildi! ({len(game.players)} o'yinchi)",
                parse_mode=ParseMode.HTML
            )
        else:
            await q.answer("Siz allaqachon ro'yxatda!", show_alert=True)
        return

    if data == "show_players":
        game = GAMES.get(cid)
        if not game:
            await q.answer("O'yin yo'q!", show_alert=True); return
        lines = "\n".join(f"{i}. {p.mention()}" for i,p in enumerate(game.players.values(),1))
        await q.answer(f"👥 O'yinchilar ({len(game.players)}):\n{lines or 'Hali hech kim'}", show_alert=True)
        return

    # Kecha/kunduz tanlovlari — faqat shaxsiy chatda
    if not data.startswith("sel_"):
        return
    if chat_type != "private":
        return

    game = find_game_by_player(uid)
    if not game:
        await q.answer("Siz o'yinda emassiz!", show_alert=True); return

    player = game.players.get(uid)
    if not player or not player.alive:
        return

    target_id = None if data == "sel_skip" else int(data.split("_")[1])

    # ── KECHA ──
    if game.phase == "night":
        if player.night_action is not None:
            await q.answer("Allaqachon ovoz berdingiz!", show_alert=True); return
        if target_id and target_id not in game.players:
            await q.answer("Noto'g'ri tanlov!", show_alert=True); return

        player.night_action = target_id or -1
        await q.answer("✅ Qabul qilindi!", show_alert=True)
        await q.edit_message_reply_markup(reply_markup=None)

        # Sherif natijasi
        if player.role == "sherif" and target_id:
            t = game.players.get(target_id)
            if t:
                fraksiya = ROLES_INFO.get(t.role, {}).get("fraksiya", "tinch")
                if t.role == "don":
                    fraksiya = "tinch"  # Don camuflaj
                if fraksiya == "mafia":
                    msg = f"🚨 <b>{t.mention()}</b> — MAFIAchi!"
                else:
                    msg = f"✅ <b>{t.mention()}</b> — tinch aholi."
                await ctx.bot.send_message(uid, msg, parse_mode=ParseMode.HTML)

        # Detektiv natijasi
        elif player.role == "detektiv" and target_id:
            t = game.players.get(target_id)
            if t:
                r = ROLES_INFO.get(t.role, {})
                await ctx.bot.send_message(
                    uid,
                    f"🔍 <b>{t.mention()}</b> — {r.get('emoji','')} <b>{r.get('nom','')}</b>",
                    parse_mode=ParseMode.HTML
                )

    # ── KUNDUZ ──
    elif game.phase == "day":
        if player.day_vote is not None:
            await q.answer("Allaqachon ovoz berdingiz!", show_alert=True); return

        player.day_vote = target_id or -1
        await q.answer("✅ Ovozingiz qabul qilindi!", show_alert=True)
        await q.edit_message_reply_markup(reply_markup=None)

        if target_id:
            t = game.players.get(target_id)
            if t:
                await ctx.bot.send_message(
                    game.chat_id,
                    f"🗳 {player.mention()} → {t.mention()} ga ovoz berdi",
                    parse_mode=ParseMode.HTML
                )

        # Hammasi ovoz berdimi?
        if all(p.day_vote is not None for p in game.alive_list()):
            await finish_day(game.chat_id, ctx, game)

# ── HEALTH CHECK (Render uchun) ────────────────
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, *args):
        pass  # logni jimita

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

# ── MAIN ───────────────────────────────────────
def main():
    # Health check serverni alohida threadda ishga tushirish
    t = threading.Thread(target=run_health_server, daemon=True)
    t.start()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("newgame", cmd_newgame))
    app.add_handler(CommandHandler("join", cmd_join))
    app.add_handler(CommandHandler("start_game", cmd_start_game))
    app.add_handler(CommandHandler("cancel_game", cmd_cancel))
    app.add_handler(CommandHandler("players", cmd_players))
    app.add_handler(CallbackQueryHandler(on_callback))
    print("🎭 Mafia Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
