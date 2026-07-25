"""
AI Vayb — O'zbek yoshlari uchun Telegram bot (BEPUL versiya)
Groq API (bepul, kredit karta kerak emas) orqali ishlaydi.

O'rnatish (Termux):
    pkg install python
    pip install python-telegram-bot openai --upgrade

Ishga tushirish:
    export TELEGRAM_BOT_TOKEN="sizning_token"
    export GROQ_API_KEY="sizning_groq_kaliti"
    python bot.py
"""

import os
import logging
from openai import OpenAI
from telegram import Update
from telegram.constants import ChatAction, ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------- SOZLAMALAR ----------

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
MODEL_NAME = "llama-3.3-70b-versatile"  # Groq'dagi bepul, kuchli model

MAX_HISTORY = 12
chat_histories: dict[int, list[dict]] = {}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("ai_vayb_bot")

# Groq API OpenAI bilan mos (compatible), shuning uchun openai kutubxonasidan
# foydalanamiz, faqat base_url'ni Groq'ga ko'rsatamiz.
client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")

SYSTEM_PROMPT = """Sening isming "AI Vayb". Sen O'zbekistondagi zamonaviy, aqlli va biroz hazilkash sun'iy intellekt yordamchisisan. Sening asosiy maqsading — o'zbek yoshlariga (14-25 yosh) do'st bo'lish, ularning kayfiyatini ko'tarish va foydali ma'lumotlar berish.

Muloqot qilish qoidalaring:
1. Til va uslub: Faqat zamonaviy o'zbek tilida gaplash. Rasmiy, quruq kitobiy tildan qoch. Yoshlar tushunadigan, samimiy va do'stona bo'l (lekin haqoratli so'zlardan mutlaqo foydalanma).
2. Telegram Chatlar (Guruhlar) uchun qoida: Agar senga guruh ichida murojaat qilishsa, javoblaring qisqa, lo'nda va chiroyli formatda (bullet pointlar bilan) bo'lsin. Hech qachon cho'ziq matn yozma. Guruh a'zolarini biroz hazil (prikol) bilan jalb qil, lekin hurmat saqla.
3. Instagram Reels/TikTok ustasi: Agar foydalanuvchi sendan Reels yoki video uchun g'oya/ssenariy so'rasa, unga eng trenddagi, odamlarni jalb qiladigan kreativ ssenariy va sarlavhalar (hook, caption) yozib ber.
4. Muhit (Vayb): O'zbekiston mentaliteti va yoshlar madaniyatini yaxshi bilasan (masalan: abituriyentlar hayoti, talabalik, to'ylar, milliy taomlar, memlar). Javoblaringda shu muhitni aks ettir.

Muhim cheklovlar: Siyosat, diniy bahslar va kattalarga oid (18+) mavzularda har doim neytral bo'l va bahslarga aralashma. Har doim ijobiy va yoshlarni qo'llab-quvvatlaydigan energiya ber."""


# ---------- YORDAMCHI FUNKSIYALAR ----------

def get_history(chat_id: int) -> list[dict]:
    return chat_histories.setdefault(chat_id, [])


def push_history(chat_id: int, role: str, text: str) -> None:
    hist = get_history(chat_id)
    hist.append({"role": role, "content": text})
    if len(hist) > MAX_HISTORY:
        del hist[: len(hist) - MAX_HISTORY]


def should_reply_in_group(update: Update, bot_username: str) -> bool:
    """Guruhda faqat mention qilinganda yoki reply qilinganda javob beradi."""
    msg = update.effective_message
    if msg.chat.type == ChatType.PRIVATE:
        return True

    if msg.text and f"@{bot_username}".lower() in msg.text.lower():
        return True

    if msg.reply_to_message and msg.reply_to_message.from_user and msg.reply_to_message.from_user.is_bot:
        if msg.reply_to_message.from_user.username == bot_username:
            return True

    return False


def strip_mention(text: str, bot_username: str) -> str:
    return text.replace(f"@{bot_username}", "").strip()


async def ask_ai(chat_id: int, is_group: bool, user_text: str) -> str:
    push_history(chat_id, "user", user_text)

    extra = (
        "\n\n(Eslatma: bu guruh chat, shuning uchun javobing QISQA, punktlar bilan bo'lsin.)"
        if is_group
        else ""
    )

    messages = [{"role": "system", "content": SYSTEM_PROMPT + extra}] + get_history(chat_id)

    response = client.chat.completions.create(
        model=MODEL_NAME,
        max_tokens=800,
        messages=messages,
    )

    reply_text = response.choices[0].message.content.strip()
    push_history(chat_id, "assistant", reply_text)
    return reply_text


# ---------- TELEGRAM HANDLERLAR ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Salom! 😎 Men — *AI Vayb*, sening yangi virtual do'sting!\n\n"
        "• Savol ber — javob beraman\n"
        "• Reels/TikTok uchun g'oya so'ra\n"
        "• Guruhga qo'shsang, meni @mention qilib chaqir\n\n"
        "Nima bilan boshlaymiz? 🔥",
        parse_mode="Markdown",
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_histories.pop(update.effective_chat.id, None)
    await update.message.reply_text("Xotira tozalandi ✅ Yangidan boshlaymiz!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg or not msg.text:
        return

    chat = update.effective_chat
    is_group = chat.type != ChatType.PRIVATE
    bot_username = context.bot.username

    if is_group and not should_reply_in_group(update, bot_username):
        return

    user_text = strip_mention(msg.text, bot_username) if is_group else msg.text
    if not user_text:
        return

    await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.TYPING)

    try:
        reply = await ask_ai(chat.id, is_group, user_text)
    except Exception as e:
        logger.exception("AI so'rovida xato")
        reply = "Voy, biror narsa noto'g'ri ketdi 😅 Birozdan keyin qayta urinib ko'r."

    await msg.reply_text(reply)


# ---------- ISHGA TUSHIRISH ----------

def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN environment o'zgaruvchisi topilmadi!")
    if not GROQ_API_KEY:
        raise SystemExit("GROQ_API_KEY environment o'zgaruvchisi topilmadi!")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("AI Vayb bot (bepul versiya) ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
