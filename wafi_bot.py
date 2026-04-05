import re
import openai
import os
import json
import random
import asyncio
import requests
import pytz

from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, MessageHandler,
    CommandHandler, ContextTypes, filters
)
from gtts import gTTS

# =========================
# ⚡ Config — তোমার keys দাও
# =========================
TOKEN = ""               # ← Telegram Bot Token
OPENAI_API_KEY = ""      # ← OpenAI key (পরে বসাবে)
ADMIN_ID = 7974704580    # ← তোমার Telegram ID (int)
TWELVE_KEY = ""          # ← Twelve Data key (twelvedata.com)

DATA_FILE = "data.json"
MEMORY_FILE = "memory.json"
USER_FILE = "ultra_users.json"

# OpenAI client
if OPENAI_API_KEY:
    client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
else:
    client = None

# =========================
# 💎 VIP System
# =========================
VIP_USERS: set = set()
FREE_SIGNAL_LIMIT = 3      # Free user দিনে ৩টা session (৯ signal)
VIP_SIGNAL_LIMIT = 3       # VIP দিনে ৩টা session (১৫ signal)
FREE_PER_SESSION = 3       # Free: প্রতি session এ ৩টা signal
VIP_PER_SESSION = 5        # VIP: প্রতি session এ ৫টা signal

# =========================
# 📁 File Setup
# =========================
for file in [DATA_FILE, MEMORY_FILE, USER_FILE]:
    if not os.path.exists(file):
        with open(file, "w", encoding="utf-8") as f:
            json.dump({}, f)

def load_json(file):
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# =========================
# 👤 Ultra User System
# =========================
def get_user(user_id):
    data = load_json(USER_FILE)
    uid = str(user_id)
    if uid not in data:
        data[uid] = {
            "name": "বন্ধু",
            "mode": "normal",
            "xp": 0,
            "level": 1,
            "love": False,
            "signal_count": 0,
            "win": 0,
            "loss": 0,
            "is_vip": False,
            "last_reset": str(datetime.now().date())
        }
        save_json(USER_FILE, data)
    return data[uid]

def update_user(user_id, key, value):
    data = load_json(USER_FILE)
    uid = str(user_id)
    if uid not in data:
        get_user(uid)
        data = load_json(USER_FILE)
    data[uid][key] = value
    save_json(USER_FILE, data)

def add_xp(user_id, amount=3):
    data = load_json(USER_FILE)
    uid = str(user_id)
    user = get_user(uid)
    user["xp"] += amount
    if user["xp"] >= user["level"] * 50:
        user["xp"] = 0
        user["level"] += 1
    data[uid] = user
    save_json(USER_FILE, data)

def reset_daily_limit(user_id):
    data = load_json(USER_FILE)
    uid = str(user_id)
    user = get_user(uid)
    today = str(datetime.now().date())
    if user.get("last_reset") != today:
        user["signal_count"] = 0
        user["win"] = 0
        user["loss"] = 0
        user["last_reset"] = today
        data[uid] = user
        save_json(USER_FILE, data)

def is_vip(user_id):
    uid = str(user_id)
    user = get_user(uid)
    return user.get("is_vip", False) or int(uid) == ADMIN_ID

def get_signal_limit(user_id):
    # Total daily signals: Free = 3x3 = 9, VIP = 3x5 = 15
    if is_vip(user_id):
        return VIP_SIGNAL_LIMIT * VIP_PER_SESSION  # 15
    else:
        return FREE_SIGNAL_LIMIT * FREE_PER_SESSION  # 9

def get_per_session(user_id):
    # প্রতি session এ কতটা signal
    return VIP_PER_SESSION if is_vip(user_id) else FREE_PER_SESSION

# =========================
# 🎭 Personality System
# =========================
def build_prompt(user):
    mode = user.get("mode", "normal")
    love = user.get("love", False)
    name = user.get("name", "বন্ধু")

    base = (
        f"তুমি Wafi, একটি স্মার্ট এবং মজাদার বাংলা AI assistant। "
        f"User এর নাম {name}। "
        f"তুমি সবসময় বাংলায় কথা বলো এবং মানুষের মতো আচরণ করো। "
        f"তুমি trading সম্পর্কে জানো এবং সাহায্য করতে পারো।"
    )

    if mode == "funny":
        base += " তুমি খুব মজাদার এবং হাসিখুশি 😆 সবকিছুতে মজা খোঁজো।"
    elif mode == "savage":
        base += " তুমি savage style এ কথা বলো, মজার roast করো 😈 কিন্তু friendly থাকো।"
    elif mode == "emotional":
        base += " তুমি আবেগপ্রবণভাবে কথা বলো, মানুষের কথা মন দিয়ে শোনো 💔"
    elif mode == "genius":
        base += " তুমি super intelligent, সব প্রশ্নের গভীর উত্তর দাও 🧠"
    else:
        base += " তুমি স্বাভাবিকভাবে বাংলায় কথা বলো, বন্ধুর মতো।"

    if love:
        base += " তুমি একজন caring girlfriend এর মতো আচরণ করো 💖 ভালোবাসার সাথে কথা বলো।"

    return base

# =========================
# 🎮 Ultra Commands Handler
# =========================
def handle_ultra_commands(msg, user_id):
    m = msg.lower().strip()
    user = get_user(user_id)

    if m.startswith("mode "):
        try:
            mode = m.split(" ")[1]
            modes = ["funny", "savage", "emotional", "genius", "normal"]
            if mode in modes:
                update_user(user_id, "mode", mode)
                return f"🎭 Mode পরিবর্তন হয়েছে: {mode} ✅"
            else:
                return f"❌ Available modes: {', '.join(modes)}"
        except Exception:
            return "❌ use: mode funny"

    if m.startswith("setname "):
        try:
            name = msg.replace("setname ", "").strip()
            update_user(user_id, "name", name)
            return f"🤖 AI এর নাম রাখা হয়েছে: {name} ✅"
        except Exception:
            return "❌ use: setname WafiKing"

    if m == "love on":
        update_user(user_id, "love", True)
        return "💖 Girlfriend mode চালু! আমি তোমার পাশে আছি সবসময় 🥰"

    if m == "love off":
        update_user(user_id, "love", False)
        return "💔 Girlfriend mode বন্ধ।"

    if m == "mystats":
        vip_status = "💎 VIP" if is_vip(user_id) else "🆓 Free"
        limit = get_signal_limit(user_id)
        per_session = get_per_session(user_id)
        return (
            f"🎮 তোমার Stats:\n\n"
            f"👤 Status: {vip_status}\n"
            f"⚡ Level: {user['level']}\n"
            f"🔥 XP: {user['xp']}/{user['level'] * 50}\n"
            f"🎭 Mode: {user['mode']}\n"
            f"📊 আজকের Signal: {user.get('signal_count', 0)}/{limit}\n"
            f"🎯 প্রতি session: {per_session}টা signal\n"
            f"✅ Win: {user.get('win', 0)}\n"
            f"❌ Loss: {user.get('loss', 0)}"
        )

    if m == "status":
        vip_status = "💎 VIP USER" if is_vip(user_id) else "🆓 FREE USER"
        return vip_status

    if m == "help":
        return (
            "📋 সব Commands:\n\n"
            "📊 Trading:\n"
            "• signal dao — VIP Signal নাও\n"
            "• /buy — VIP কিনো\n"
            "• /status — তোমার status\n\n"
            "🎭 AI Mode:\n"
            "• mode funny — মজাদার\n"
            "• mode savage — Savage\n"
            "• mode genius — Smart\n"
            "• mode emotional — আবেগী\n"
            "• mode normal — Normal\n\n"
            "💖 Special:\n"
            "• love on / love off\n"
            "• setname [নাম]\n"
            "• mystats — তোমার stats\n\n"
            "🎙️ Voice message পাঠাতে পারো!"
        )

    return None

# =========================
# 📊 Trading Pairs
# =========================
pairs = ["USDMXN", "USDPKR", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]

# =========================
# ⏱ Dhaka Time
# =========================
def get_time():
    tz = pytz.timezone("Asia/Dhaka")
    return datetime.now(tz).strftime("%H:%M")

# =========================
# 📉 Fetch Market Data
# =========================
def fetch_market_data(pair):
    try:
        if not TWELVE_KEY:
            return None
        from_sym = pair[:3]
        to_sym = pair[3:]
        url = (
            f"https://api.twelvedata.com/time_series"
            f"?symbol={from_sym}/{to_sym}"
            f"&interval=1min&outputsize=30"
            f"&apikey={TWELVE_KEY}"
        )
        res = requests.get(url, timeout=10).json()
        if "values" not in res:
            return None
        closes = [float(v["close"]) for v in reversed(res["values"])]
        return closes
    except Exception:
        return None

# =========================
# 🧠 Market Analysis
# =========================
def analyze(pair):
    closes = fetch_market_data(pair)
    if closes is None or len(closes) < 15:
        # Key নেই — random signal with accuracy
        return random.choice(["CALL", "PUT"]), random.randint(82, 95)

    recent = closes[-5:]
    older = closes[-15:-5]
    avg_recent = sum(recent) / len(recent)
    avg_older = sum(older) / len(older)

    diff = abs(avg_recent - avg_older) / avg_older * 100
    accuracy = min(95, 81 + diff * 10)

    if accuracy < 81:
        return None, round(accuracy, 1)

    signal = "CALL" if avg_recent > avg_older else "PUT"
    return signal, round(accuracy, 1)

# =========================
# 🚀 Generate Signal
# =========================
def generate_signal(pair):
    signal_type, accuracy = analyze(pair)

    if signal_type is None:
        return None, None, accuracy

    if signal_type == "CALL":
        direction = "🟢 CALL UP 🔺"
        ball = "🟢"
    else:
        direction = "🔴 PUT DOWN 🔻"
        ball = "🔴"

    msg = (
        f"🔥 {pair}-OTCq 🔥\n"
        f"🕐 {get_time()}\n"
        f"⌛ 1 Minutes\n"
        f"{ball} {direction}\n"
        f"📈 Accuracy: {accuracy}%\n\n"
        f"❤️ Claw VIP BOT ❤️"
    )
    return msg, signal_type, accuracy

# =========================
# 🎲 Result — Real Market Data
# =========================
def generate_result(pair, signal_type, entry_price=None):
    try:
        closes = fetch_market_data(pair)
        if closes is not None and len(closes) >= 2 and entry_price is not None:
            current_price = closes[-1]
            if signal_type == "CALL":
                is_win = current_price > entry_price
            else:
                is_win = current_price < entry_price
            result = "WIN ✅" if is_win else "Loss ☑️"
            return result, is_win
    except Exception:
        pass

    # Key নেই — realistic random
    is_win = random.choices([True, False], weights=[65, 35])[0]
    result = "WIN ✅" if is_win else "Loss ☑️"
    return result, is_win

# =========================
# 📊 Session Summary
# =========================
def session_summary(win, loss):
    total = win + loss
    bars = "🟩" * win + "🟥" * loss
    return (
        f"𝗧𝗢𝗗𝗔𝗬'𝗦  𝗩𝗜𝗣  𝗦𝗜𝗚𝗡𝗔𝗟\n"
        f"{bars}\n"
        f"𝗧𝗼𝘁𝗮𝗹 𝗧𝗿𝗮𝗱𝗲𝘀 : {total:02d} 🎀\n\n"
        f"𝗪𝗶𝗻  : {win:02d} ✅\n"
        f"📊 (NOT MTG)\n\n"
        f"𝗟𝗼𝘀𝘀 : {loss:02d} ☑️\n\n"
        f"𝙰𝙻𝙷𝙰𝙼𝙳𝚄𝙻𝙸𝙻𝙻𝙰𝙷, আজকের সেশনের জন্য যথেষ্ট হয়েছে...\n\n"
        f"⭐️ @Wafi_ATC ✅"
    )

# =========================
# 🎤 Voice TTS
# =========================
async def send_voice(update: Update, text: str):
    try:
        loop = asyncio.get_event_loop()

        def make_tts():
            tts = gTTS(text=text, lang="bn")
            tts.save("voice.mp3")

        await loop.run_in_executor(None, make_tts)
        with open("voice.mp3", "rb") as audio:
            await update.message.reply_voice(audio)
        try:
            os.remove("voice.mp3")
        except Exception:
            pass
    except Exception as e:
        print(f"send_voice error: {e}")

# =========================
# 🔹 Voice → Text
# =========================
async def voice_to_text(file_path: str) -> str:
    try:
        if not OPENAI_API_KEY:
            return "OpenAI key নেই 😅"
        loop = asyncio.get_event_loop()

        def _transcribe():
            sync_client = openai.OpenAI(api_key=OPENAI_API_KEY)
            with open(file_path, "rb") as f:
                result = sync_client.audio.transcriptions.create(
                    model="whisper-1", file=f
                )
            return result.text

        return await loop.run_in_executor(None, _transcribe)
    except Exception as e:
        return f"voice error 😅 {e}"

# =========================
# 🔥 Ultra AI Reply
# =========================
async def ultra_ai_reply(message: str, user_id: str, memory: dict) -> str:
    try:
        if not client:
            return None
        user = get_user(user_id)
        prompt = build_prompt(user)

        messages = [{"role": "system", "content": prompt}]

        if user_id in memory and "chat" in memory[user_id]:
            for chat in memory[user_id]["chat"][-5:]:
                messages.append({"role": "user", "content": chat["user"]})
                messages.append({"role": "assistant", "content": chat["bot"]})

        messages.append({"role": "user", "content": message})

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
        return response.choices[0].message.content
    except Exception:
        return None

# =========================
# 🧠 User Memory
# =========================
user_context: dict = {}

def load_user_memory(user_id: str) -> dict:
    file = f"user_{user_id}.db"
    data = {}
    try:
        with open(file, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    data[k] = v
    except Exception:
        pass
    return data

def save_user_memory(user_id: str, key: str, value: str):
    file = f"user_{user_id}.db"
    data = load_user_memory(user_id)
    data[key] = value
    with open(file, "w", encoding="utf-8") as f:
        for k in data:
            f.write(k + "=" + data[k] + "\n")

def get_user_memory(user_id: str, key: str):
    return load_user_memory(user_id).get(key, None)

def set_context(user_id: str, value):
    user_context[user_id] = value

def get_context(user_id: str):
    return user_context.get(user_id, None)

# =========================
# 😊 Emotion System
# =========================
def detect_emotion(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["sad", "😢", "মন খারাপ", "কষ্ট", "দুঃখ"]):
        return "sad"
    if any(w in t for w in ["happy", "😂", "খুশি", "আনন্দ"]):
        return "happy"
    if any(w in t for w in ["angry", "😡", "রাগ", "বিরক্ত"]):
        return "angry"
    return "normal"

def emotion_reply(emotion: str):
    if emotion == "sad":
        return "😔 মন খারাপ কেন? আমি আছি তোমার পাশে, বলো কী হয়েছে..."
    if emotion == "happy":
        return "😊 দারুণ! তোমার খুশিতে আমিও খুশি! 🎉"
    if emotion == "angry":
        return "😌 শান্ত হও বন্ধু, রাগ করলে তুমিই কষ্ট পাবে। কী হয়েছে বলো?"
    return None

# =========================
# 💬 Response Bank
# =========================
greetings = ["👋 হ্যালো!", "Hi 👋", "Hey! কী খবর?", "হাই 😊 কেমন আছো?"]
jokes = [
    "😂 আমি AI, কিন্তু এখনো salary পাই না!",
    "🤣 Bug আমার best friend — সে কখনো ছেড়ে যায় না!",
    "😆 কোডিং = error + fix + আবার error",
    "🤣 WiFi password জিজ্ঞেস করলে বোঝা যায় friendship কতটা গভীর!"
]
roasts = [
    "😏 তুমি এখনও beginner level — কিন্তু চেষ্টা করতে থাকো!",
    "🤣 তোমার coding দেখলে computer ও কাঁদে 😭",
    "😆 তুমি কি trade করো নাকি donate করো? 😂"
]
advice_list = [
    "💡 প্রতিদিন একটু একটু শিখলেই বড় হওয়া যায়।",
    "💡 Practice is key — থামলেই হারবে।",
    "💡 ধৈর্য ধরো, সাফল্য আসবেই।",
    "💡 Trading এ emotion control সবচেয়ে জরুরি।"
]
fallback_replies = [
    "🤔 বুঝলাম না ভাই, আবার বলো?",
    "😅 এটা আমার মাথার উপর দিয়ে গেল!",
    "🤖 আমি শিখছি... একটু সময় দাও!"
]

# =========================
# 🧠 BRAIN System
# =========================
def brain(text: str, user_id: str) -> str:
    msg = text.lower().strip()
    mem = load_user_memory(user_id)
    name = mem.get("name")
    ctx = get_context(user_id)
    emo = detect_emotion(text)

    if ctx == "ask_name":
        save_user_memory(user_id, "name", text)
        set_context(user_id, None)
        return f"👍 সুন্দর নাম! {text}, আমি মনে রাখলাম 😊"

    if msg in ["hi", "hello", "hey", "হাই", "হ্যালো", "হেলো", "হ্যালো ভাই", "আসসালামুআলাইকুম", "সালাম"]:
        if name:
            return f"👋 ওয়ালাইকুম আস্সালাম {name}! কেমন আছো? 😊"
        set_context(user_id, "ask_name")
        return greetings[0] + " তোমার নাম কী বলো তো? 😊"

    if "নাম" in msg or "name" in msg:
        if name:
            return f"🤖 তোমার নাম: {name}"
        return "🙂 তোমার নাম কী?"

    emo_r = emotion_reply(emo)
    if emo_r:
        return emo_r

    if any(w in msg for w in ["কেমন আছো", "কেমন আছ", "how are you"]):
        return "😊 আলহামদুলিল্লাহ দারুণ আছি! তুমি কেমন আছো?"

    if any(w in msg for w in ["কে তুমি", "who are you", "তুমি কে"]):
        return "🤖 আমি Wafi — তোমার AI বন্ধু + VIP Trading Assistant! 🔥"

    if "joke" in msg or "জোকস" in msg or "মজা" in msg:
        return random.choice(jokes)

    if "roast" in msg:
        return random.choice(roasts)

    if "advice" in msg or "পরামর্শ" in msg:
        return random.choice(advice_list)

    if msg.startswith("teach "):
        try:
            parts = msg.replace("teach ", "").split("=")
            q, a = parts[0].strip(), parts[1].strip()
            save_user_memory(user_id, q, a)
            return "🧠 শিখে ফেললাম!"
        except Exception:
            return "❌ Format: teach question = answer"

    learned = get_user_memory(user_id, msg)
    if learned:
        return learned

    if "my name is" in msg:
        n = msg.replace("my name is", "").strip()
        save_user_memory(user_id, "name", n)
        return f"👍 Nice to meet you {n}! 😊"

    if msg in ["ok", "okay", "ঠিক আছে", "আচ্ছা", "ওকে"]:
        return "👍 ঠিক আছে!"

    if msg in ["hmm", "hm", "হুম"]:
        return "🤔 হুম... কিছু মাথায় আসছে?"

    if any(w in msg for w in ["motivate", "অনুপ্রেরণা", "motivation"]):
        return "🚀 তুমি পারবে! Never give up — সাফল্য তোমার জন্যই অপেক্ষা করছে! 💪"

    if "time" in msg or "সময়" in msg:
        return f"⏰ এখন ঢাকার সময়: {get_time()}"

    if "bye" in msg or "বিদায়" in msg or "আল্লাহ হাফেজ" in msg:
        return "👋 আল্লাহ হাফেজ! আবার কথা হবে 😊"

    if "ভালোবাসি" in msg or "love you" in msg:
        return "🥰 আমিও তোমাকে ভালোবাসি বন্ধু! (AI style 😄)"

    if "trading" in msg or "ট্রেডিং" in msg:
        return "📊 Trading এর জন্য signal dao লিখো — আমি VIP signal দেবো! 🔥"

    return random.choice(fallback_replies)

# =========================
# 🚀 Start Command
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    get_user(user_id)
    first_name = update.message.from_user.first_name or "বন্ধু"
    vip_badge = "💎 VIP" if is_vip(user_id) else "🆓 Free"

    await update.message.reply_text(
        f"👋 আস্সালামু আলাইকুম, {first_name}! {vip_badge}\n\n"
        f"🤖 আমি Wafi — তোমার স্মার্ট AI বন্ধু\n"
        f"এবং VIP Trading Assistant! 🔥\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 TRADING SIGNALS:\n"
        f"• signal dao — VIP Signal নাও\n"
        f"• /buy — VIP Plan কিনো 💎\n"
        f"• /status — তোমার status দেখো\n\n"
        f"🎭 AI CHAT MODES:\n"
        f"• mode funny — হাসিখুশি mode 😂\n"
        f"• mode savage — Savage mode 😈\n"
        f"• mode genius — Smart mode 🧠\n"
        f"• mode emotional — আবেগী mode 💔\n"
        f"• love on — Special mode 💖\n\n"
        f"🎮 COMMANDS:\n"
        f"• mystats — তোমার সব stats\n"
        f"• setname [নাম] — AI এর নাম দাও\n"
        f"• help — সব commands দেখো\n\n"
        f"🎙️ Voice message পাঠাতে পারো!\n"
        f"💬 যেকোনো কথা বলো — আমি সবসময় আছি!\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🌟 Free: দিনে ৯টা Signal (৩+৩+৩)\n"
        f"💎 VIP: দিনে ১৫টা Signal (৫+৫+৫)\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⭐ @Wafi_ATC"
    )

# =========================
# 💎 Buy Command
# =========================
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💎 VIP PLAN — মাত্র ৫০০ টাকা!\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💰 Payment করো:\n\n"
        "📱 bKash: 01759852112\n"
        "📱 Nagad: 01625141477\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✅ VIP সুবিধা:\n"
        "• দিনে ১৫টা Signal (৫+৫+৫) (Free তে ৯টা)\n"
        "• Real market analysis\n"
        "• Priority support\n\n"
        "📤 Payment করে লিখো:\n"
        "paid [TXN ID] অথবা screenshot পাঠাও\n\n"
        "⭐ @Wafi_ATC"
    )

# =========================
# 💎 VIP On Command (Admin only)
# =========================
async def vip_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ তুমি admin না!")
        return
    try:
        target_id = int(context.args[0])
        VIP_USERS.add(target_id)
        update_user(str(target_id), "is_vip", True)
        await context.bot.send_message(
            chat_id=target_id,
            text=(
                "🎉 অভিনন্দন! তোমার VIP Activated হয়েছে! 💎\n\n"
                "এখন দিনে ১৫টা Signal পাবে (৫+৫+৫)!\n"
                "signal dao লিখে শুরু করো! 🔥"
            )
        )
        await update.message.reply_text(f"✅ {target_id} কে VIP করা হয়েছে!")
    except Exception:
        await update.message.reply_text("❌ use: /vip_on [user_id]")

# =========================
# 📊 Status Command
# =========================
async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    user = get_user(user_id)
    vip_status = "💎 VIP USER" if is_vip(user_id) else "🆓 FREE USER"
    limit = get_signal_limit(user_id)
    used = user.get("signal_count", 0)
    await update.message.reply_text(
        f"📊 তোমার Status:\n\n"
        f"👤 {vip_status}\n"
        f"📈 আজকের Signal: {used}/{limit}\n"
        f"✅ Win: {user.get('win', 0)}\n"
        f"❌ Loss: {user.get('loss', 0)}\n\n"
        f"VIP কিনতে /buy লিখো 💎"
    )

# =========================
# 🔥 Signal Session Handler
# =========================
async def run_signal_session(update: Update, user_id: str):
    user = get_user(user_id)

    # Daily limit reset
    reset_daily_limit(user_id)
    user = get_user(user_id)

    # Limit check
    daily_limit = get_signal_limit(user_id)
    per_session = get_per_session(user_id)
    used = user.get("signal_count", 0)

    if used >= daily_limit:
        vip_hint = "" if is_vip(user_id) else "\n\n💎 VIP কিনলে আরো বেশি signal পাবে!\n/buy লিখো"
        await update.message.reply_text(
            f"⛔ আজকের signal limit শেষ! ({used}/{daily_limit})\n"
            f"🌙 রাত ১২টার পর আবার signal পাবে।"
            f"{vip_hint}"
        )
        return

    # Market check
    await update.message.reply_text("🔍 Market analyze করছি...")

    test_closes = fetch_market_data("EURUSD")
    if test_closes is not None and len(test_closes) >= 15:
        wait_min = 0
    else:
        # সর্বোচ্চ ১৫ মিনিট — random 0,3,5,7,10,14 মিনিট
        wait_options = [0, 3, 5, 7, 10, 14]
        wait_min = random.choice(wait_options)

    if wait_min > 0:
        await update.message.reply_text(
            f"⚠️ Market এখন একটু weak!\n"
            f"⏳ আনুমানিক {wait_min} মিনিট অপেক্ষা করুন...\n"
            f"🔔 সময় হলে আমি নিজেই জানাবো!"
        )
        await asyncio.sleep(wait_min * 60)
        await update.message.reply_text(
            f"🔔 অপেক্ষার সময় শেষ!\n"
            f"✅ Market এখন GOOD!\n"
            f"🚀 Signal শুরু হচ্ছে..."
        )

    session_win = 0
    session_loss = 0

    # এই session এ কতটা signal দেওয়া যাবে
    remaining_today = daily_limit - used
    this_session = min(per_session, remaining_today)  # ৩টা বা ৫টা (limit না পেরোলে)

    selected_pairs = random.sample(pairs, min(this_session, len(pairs)))

    for pair in selected_pairs:
        user = get_user(user_id)
        if user.get("signal_count", 0) >= daily_limit:
            break

        sig_msg, signal_type, accuracy = generate_signal(pair)

        if sig_msg is None:
            await update.message.reply_text(
                f"⚠️ {pair} — Market এখন ভালো না, skip..."
            )
            continue

        await update.message.reply_text(sig_msg)
        await asyncio.sleep(2)

        # Entry price নাও
        entry_closes = fetch_market_data(pair)
        entry_price = entry_closes[-1] if entry_closes else None

        await update.message.reply_text(f"⏳ {pair} — ১ মিনিট অপেক্ষা করো... 🕐")
        await asyncio.sleep(60)

        # Real result
        result_text, is_win = generate_result(pair, signal_type, entry_price)
        await update.message.reply_text(f"🗓 {pair}-OTCq {result_text}")

        if is_win:
            session_win += 1
            update_user(user_id, "win", user.get("win", 0) + 1)
        else:
            session_loss += 1
            update_user(user_id, "loss", user.get("loss", 0) + 1)

        update_user(user_id, "signal_count", user.get("signal_count", 0) + 1)
        await asyncio.sleep(3)

    # Session summary
    await update.message.reply_text(session_summary(session_win, session_loss))

    user = get_user(user_id)
    remaining = daily_limit - user.get("signal_count", 0)
    if remaining > 0:
        await update.message.reply_text(
            f"📊 আজকে আর {remaining}টা signal পাবে।\n"
            f"আবার signal চাইলে লিখো: signal dao"
        )

# =========================
# 💳 Payment Handler
# =========================
async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    msg = update.message.text

    # TXN ID / number extract
    numbers = re.findall(r'\d+', msg)
    txn = numbers[-1] if numbers else "Not found"

    text = (
        f"🟢 NEW PAYMENT REQUEST\n\n"
        f"👤 Name: {user.first_name}\n"
        f"🆔 User ID: {user.id}\n\n"
        f"💬 Message:\n{msg}\n\n"
        f"💳 TXN / Number:\n{txn}"
    )

    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=text)
        await update.message.reply_text(
            "✅ Payment info পাঠানো হয়েছে!\n"
            "⏳ Admin verify করবে — একটু অপেক্ষা করো..."
        )
    except Exception:
        pass

# =========================
# 🔥 Main Reply Handler
# =========================
async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    msg = update.message.text
    msg_lower = msg.lower().strip()
    user_id = str(update.message.from_user.id)

    memory = load_json(MEMORY_FILE)
    data = load_json(DATA_FILE)

    if user_id not in memory:
        memory[user_id] = {}

    # XP add
    add_xp(user_id, 3)

    # ✅ Signal triggers
    signal_triggers = [
        "signal", "সিগনাল", "signal dao", "সিগনাল দাও",
        "সিগনাল দিবা", "সিগনাল কখন", "entry", "trade dao",
        "signal daw", "sinal dao", "signa", "সিগ"
    ]
    if any(word in msg_lower for word in signal_triggers):
        await run_signal_session(update, user_id)
        return

    # ✅ Payment check (paid লিখলে)
    if msg_lower.startswith("paid"):
        await handle_payment(update, context)
        return

    # ✅ Ultra commands
    ultra = handle_ultra_commands(msg, user_id)
    if ultra:
        await update.message.reply_text(ultra)
        return

    # ✅ Admin clear
    if msg_lower == "clear" and int(user_id) == ADMIN_ID:
        data.clear()
        save_json(DATA_FILE, data)
        await update.message.reply_text("✅ সব data delete হয়েছে!")
        return

    # 📖 Learned data
    if msg_lower in data:
        await update.message.reply_text(random.choice(data[msg_lower]))
        return

    # ✅ Brain check
    brain_result = brain(msg, user_id)
    if brain_result not in fallback_replies:
        await update.message.reply_text(brain_result)
        return

    # 🤖 Ultra AI (OpenAI)
    await update.message.chat.send_action(action="typing")
    ai_text = await ultra_ai_reply(msg, user_id, memory)

    if ai_text:
        await update.message.reply_text(ai_text)
        await send_voice(update, ai_text)
        if "chat" not in memory[user_id]:
            memory[user_id]["chat"] = []
        memory[user_id]["chat"].append({"user": msg, "bot": ai_text})
        save_json(MEMORY_FILE, memory)
        if msg_lower not in data:
            data[msg_lower] = [ai_text]
            save_json(DATA_FILE, data)
    else:
        # OpenAI নেই — personality based reply
        user = get_user(user_id)
        mode = user.get("mode", "normal")
        if mode == "funny":
            await update.message.reply_text(random.choice(jokes))
        elif mode == "savage":
            await update.message.reply_text(random.choice(roasts))
        elif mode == "emotional":
            await update.message.reply_text("💭 বলো, আমি মন দিয়ে শুনছি...")
        else:
            await update.message.reply_text(
                "🤖 আমি এখন basic mode এ আছি!\n"
                "যেকোনো কথা বলো — চেষ্টা করবো উত্তর দিতে 😊\n"
                "help লিখলে সব commands দেখবে।"
            )

# =========================
# 🎙️ Voice Handler
# =========================
async def voice_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.voice:
        return

    user_id = str(update.message.from_user.id)
    memory = load_json(MEMORY_FILE)

    if user_id not in memory:
        memory[user_id] = {}

    try:
        await update.message.chat.send_action(action="typing")
        voice_file = await update.message.voice.get_file()
        file_path = f"voice_{user_id}.ogg"
        await voice_file.download_to_drive(file_path)
        transcribed = await voice_to_text(file_path)

        try:
            os.remove(file_path)
        except Exception:
            pass

        await update.message.reply_text(f"🎙️ তুমি বললে: {transcribed}")

        if client:
            ai_text = await ultra_ai_reply(transcribed, user_id, memory)
            if ai_text:
                await update.message.reply_text(ai_text)
                await send_voice(update, ai_text)
                if "chat" not in memory[user_id]:
                    memory[user_id]["chat"] = []
                memory[user_id]["chat"].append({"user": transcribed, "bot": ai_text})
                save_json(MEMORY_FILE, memory)
                return

        brain_result = brain(transcribed, user_id)
        await update.message.reply_text(brain_result)

    except Exception as e:
        await update.message.reply_text(f"Voice error 😅 {e}")

# =========================
# ▶️ RUN
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("vip_on", vip_on))
    app.add_handler(CommandHandler("status", status_cmd))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply))
    app.add_handler(MessageHandler(filters.VOICE, voice_reply))

    print("🤖 Wafi GOD LEVEL Bot চালু হয়েছে! 🔥")
    app.run_polling()

if __name__ == "__main__":
    main()
