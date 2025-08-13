import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import (
    Message, FSInputFile,
    InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, ReplyKeyboardRemove
)
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.client.default import DefaultBotProperties

import db
from datetime import datetime
import pandas as pd
from collections import defaultdict
import calendar

# Initialize DB
try:
    db.init_db()
except Exception:
    pass  # Prevent crash if already initialized

import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher

# 📂 Load .env variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing! Check your .env file.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Your handlers below...
user_sessions = {}

# ================== Keyboards ==================
def main_menu(session: dict):
    kb = ReplyKeyboardBuilder()

    if session.get("is_admin"):
        # Admin actions
        kb.button(text="📊 Barcha Ma'lumotlar")
        kb.button(text="🗓 Kunlik Hisobot")
        kb.button(text="👥 Foydalanuvchilarni Boshqarish")
        kb.button(text="➕ Foydalanuvchi Qo‘shish")
        # Mold management
        kb.button(text="➕ Qolip Qo‘shish")
        kb.button(text="🗑 Qolip O‘chirish")
        kb.button(text="📋 Qoliplar")
        kb.adjust(2, 2, 3)
    else:
        # Worker actions
        kb.button(text="➕ Ishlab chiqarishni Qo‘shish")
        kb.button(text="📝 Mening Yozuvlarim")
        kb.adjust(1, 1)

    # Common for both
    kb.button(text="⚙ Profilni Tahrirlash")
    kb.button(text="🚪 Chiqish")
    kb.adjust(1, 1)

    return kb.as_markup(resize_keyboard=True)


def molds_reply_keyboard(include_cancel=True):
    molds = db.get_all_molds()
    builder = ReplyKeyboardBuilder()

    # Safe handling whether molds are dicts or plain strings
    for m in molds:
        if isinstance(m, dict):
            builder.button(text=m.get("name", "❓ No Name"))
        else:
            builder.button(text=str(m))

    if include_cancel:
        builder.button(text="❌ Bekor qilish")

    # Adjust: 2 per row for molds, last row for cancel
    total_molds = len(molds)
    if include_cancel:
        builder.adjust(2, 2, *((total_molds + 1) % 2 and (1,) or ()))
    else:
        builder.adjust(2, 2)

    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


@dp.message(Command("start"))
async def cmd_start(msg: Message):
    user_sessions[msg.from_user.id] = {"state": "awaiting_username"}
    await msg.answer("Xush kelibsiz! Iltimos, foydalanuvchi nomingizni kiriting:")

@dp.message(lambda m: user_sessions.get(m.from_user.id, {}).get("state") == "awaiting_username")
async def get_username(msg: Message):
    sess = user_sessions[msg.from_user.id]
    sess["username"] = msg.text.strip()
    sess["state"] = "awaiting_password"
    await msg.answer("Parolingizni kiriting:")

@dp.message(lambda m: user_sessions.get(m.from_user.id, {}).get("state") == "awaiting_password")
async def get_password(msg: Message):
    sess = user_sessions[msg.from_user.id]
    user = db.get_user(sess["username"])
    if not user or user["password"] != msg.text.strip():
        user_sessions.pop(msg.from_user.id, None)
        return await msg.answer("Kirish amalga oshmadi. Qayta urinib ko‘rish uchun /start buyrug‘idan foydalaning.")
    if user.get("blocked"):
        user_sessions.pop(msg.from_user.id, None)
        return await msg.answer("Siz bloklangansiz.")
    sess.update({
        "is_admin": user["is_admin"],
        "name": user["name"],
        "state": "logged_in"
    })
    db.update_user(sess["username"], {"telegram_id": msg.from_user.id})
    await msg.answer(
        f"<b>{sess['name']}</b> sifatida tizimga kirdingiz ({'Admin' if sess['is_admin'] else 'Ishchi'})",
        reply_markup=main_menu(sess)
    )


# ➕ Admin: Create Worker
# ➕ Start Create User
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


@dp.message(F.text == "➕ Foydalanuvchi Qo‘shish")
async def create_user_start(msg: Message):
    sess = user_sessions[msg.from_user.id]
    if not sess.get("is_admin"):
        return await msg.answer("🚫 Ruxsat berilmagan.")

    sess["state"] = "creating_user_name"

    cancel_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True
    )

    await msg.answer(
        "🆕 Yangi ishchining to‘liq ismini kiriting:",
        reply_markup=cancel_kb
    )


# 📛 1-qadam — To‘liq ismni kiriting
@dp.message(lambda m: user_sessions.get(m.from_user.id, {}).get("state") == "creating_user_name")
async def creating_username(msg: Message):
    if msg.text.strip().lower() == "cancel" or msg.text.strip() == "❌ Bekor qilish":
        user_sessions[msg.from_user.id]["state"] = "logged_in"
        return await msg.answer("❌ Foydalanuvchi yaratish bekor qilindi.", reply_markup=main_menu(user_sessions[msg.from_user.id]))

    sess = user_sessions[msg.from_user.id]
    sess["new_user_name"] = msg.text.strip()
    sess["state"] = "creating_user_username"
    await msg.answer("👤 Yangi ishchi uchun foydalanuvchi nomini kiriting (yoki ❌ Bekor qilish):")


# 👤 2-qadam — Foydalanuvchi nomini kiriting
@dp.message(lambda m: user_sessions.get(m.from_user.id, {}).get("state") == "creating_user_username")
async def creating_password(msg: Message):
    if msg.text.strip().lower() == "cancel" or msg.text.strip() == "❌ Bekor qilish":
        user_sessions[msg.from_user.id]["state"] = "logged_in"
        return await msg.answer("❌ Foydalanuvchi yaratish bekor qilindi.", reply_markup=main_menu(user_sessions[msg.from_user.id]))

    sess = user_sessions[msg.from_user.id]
    sess["new_user_username"] = msg.text.strip()
    sess["state"] = "creating_user_password"
    await msg.answer("🔑 Yangi ishchi uchun parolni kiriting (yoki ❌ Bekor qilish):")



# 🔑 3-qadam — Foydalanuvchini yaratishni yakunlash
@dp.message(lambda m: user_sessions.get(m.from_user.id, {}).get("state") == "creating_user_password")
async def finish_creating_user(msg: Message):
    if msg.text.strip().lower() == "cancel" or msg.text.strip() == "❌ Bekor qilish":
        user_sessions[msg.from_user.id]["state"] = "logged_in"
        return await msg.answer("❌ Foydalanuvchi yaratish bekor qilindi.", reply_markup=main_menu(user_sessions[msg.from_user.id]))

    sess = user_sessions[msg.from_user.id]
    password = msg.text.strip()
    db.add_user(
        username=sess["new_user_username"],
        password=password,
        name=sess["new_user_name"],
        is_admin=False
    )
    sess["state"] = "logged_in"
    await msg.answer("✅ Yangi ishchi muvaffaqiyatli qo‘shildi!", reply_markup=main_menu(sess))

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

CANCEL_BUTTON = KeyboardButton(text="❌ Bekor qilish")
CONFIRM_BUTTON = KeyboardButton(text="✅ Tasdiqlash")


from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

from pytz import timezone

# Uzbekistan timezone
UZB_TZ = timezone("Asia/Tashkent")


# =========================
# =========================
# 📦 Add Production Flow
# =========================

# Worker - Start adding production
from aiogram import F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime
import db

# Example constants (make sure you have them somewhere in your code)


# Example global storage for sessions


# ========== ADD PRODUCTION FLOW ==========

@dp.message(F.text == "➕ Ishlab chiqarishni Qo‘shish")
async def add_prod(msg: Message):
    sess = user_sessions[msg.from_user.id]
    sess["state"] = "awaiting_prod_type"

    molds = db.get_all_molds()  # returns list of strings
    if not molds:
        sess["state"] = "logged_in"
        return await msg.answer(
            "❌ Hozircha qoliplar mavjud emas. Admin qo‘shishi kerak.",
            reply_markup=main_menu(sess)
        )

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=m)] for m in molds] + [[CANCEL_BUTTON]],
        resize_keyboard=True
    )
    await msg.answer("Ishlab chiqarish qolip turini tanlang:", reply_markup=kb)


@dp.message(lambda m: user_sessions.get(m.from_user.id, {}).get("state") == "awaiting_prod_type")
async def prod_type(msg: Message):
    if msg.text == "❌ Bekor qilish":
        return await cancel_prod(msg)

    molds = db.get_all_molds()  # list of strings
    if msg.text not in molds:
        return await msg.answer("❌ Iltimos, ro‘yxatdan qolip tanlang.")

    sess = user_sessions[msg.from_user.id]
    sess["production_type"] = msg.text.strip()
    sess["state"] = "awaiting_quantity"

    await msg.answer("Miqdorni kiriting:", reply_markup=ReplyKeyboardMarkup(
        keyboard=[[CANCEL_BUTTON]],
        resize_keyboard=True
    ))



@dp.message(lambda m: user_sessions.get(m.from_user.id, {}).get("state") == "awaiting_quantity")
async def prod_qty(msg: Message):
    if msg.text == "❌ Bekor qilish":
        return await cancel_prod(msg)

    if not msg.text.isdigit():
        return await msg.answer("❌ Miqdor faqat raqam bo‘lishi kerak.")

    sess = user_sessions[msg.from_user.id]
    sess["quantity"] = int(msg.text.strip())
    sess["state"] = "confirming"

    await msg.answer(
        f"Tasdiqlang:\nQolip: {sess['production_type']}\nMiqdor: {sess['quantity']}",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[CONFIRM_BUTTON, CANCEL_BUTTON]],
            resize_keyboard=True
        )
    )


@dp.message(F.text == "✅ Tasdiqlash")
async def confirm_prod(msg: Message):
    sess = user_sessions[msg.from_user.id]
    if sess.get("state") != "confirming":
        return await msg.answer("Kutilmagan qadam.")

    if not sess.get("production_type") or not sess.get("quantity"):
        return await msg.answer("❌ Ma'lumotlar to‘liq emas. Iltimos, qaytadan boshlang.")

    now_uzb = datetime.now(UZB_TZ)

    db.save_production({
        "name": sess["name"],
        "production_type": sess["production_type"],
        "quantity": sess["quantity"],
        "date": now_uzb.strftime("%Y-%m-%d %H:%M:%S")
    })

    alert_text = (
        f"📢 Yangi ishlab chiqarish yozuvi\n"
        f"👤 Ishchi: {sess['name']}\n"
        f"🆔 Foydalanuvchi nomi: @{msg.from_user.username or 'N/A'}\n"
        f"🚗 Qolip: {sess['production_type']}\n"
        f"📦 Miqdor: {sess['quantity']}\n"
        f"🕒 Vaqt: {now_uzb.strftime('%Y-%m-%d %H:%M')}"
    )

    sess["state"] = "logged_in"
    sess.pop("production_type", None)
    sess.pop("quantity", None)

    await msg.answer("✅ Saqlandi!", reply_markup=main_menu(sess))

    admins = [uid for uid, data in user_sessions.items() if data.get("is_admin")]
    for admin_id in admins:
        try:
            await bot.send_message(admin_id, alert_text)
        except Exception as e:
            print(f"Admin {admin_id} ga xabar yuborilmadi: {e}")


@dp.message(F.text == "❌ Bekor qilish")
async def cancel_prod(msg: Message):
    sess = user_sessions.get(msg.from_user.id, {})
    for key in ["state", "production_type", "quantity"]:
        sess.pop(key, None)
    sess["state"] = "logged_in"
    await msg.answer("Bekor qilindi.", reply_markup=main_menu(sess))

# =========================
# 🛠 Mold Management (Admin)
# =========================

from aiogram import F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# =========================
# 🛠 Mold Management (Admin)
# =========================

@dp.message(F.text.regexp(r"^➕\s*Qolip\s+Qo['‘`ʼ]shish$"))
async def add_mold_start(msg: Message):
    sess = user_sessions[msg.from_user.id]
    if not sess.get("is_admin"):
        return await msg.answer("❌ Sizda ruxsat yo‘q.")
    sess["state"] = "awaiting_new_mold"
    await msg.answer(
        "🆕 Qolip nomini kiriting:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[CANCEL_BUTTON]],
            resize_keyboard=True
        )
    )


@dp.message(lambda m: user_sessions.get(m.from_user.id, {}).get("state") == "awaiting_new_mold")
async def add_mold_finish(msg: Message):
    if msg.text == "❌ Bekor qilish":
        return await cancel_prod(msg)

    mold_name = msg.text.strip()
    if not mold_name:
        return await msg.answer("❌ Qolip nomi bo‘sh bo‘lishi mumkin emas.")

    # Check if mold already exists
    if mold_name in db.get_all_molds():
        return await msg.answer("⚠️ Bu qolip allaqachon mavjud.")

    db.add_mold(mold_name)
    sess = user_sessions[msg.from_user.id]
    sess["state"] = "logged_in"
    await msg.answer(f"✅ Qolip qo‘shildi: {mold_name}", reply_markup=main_menu(sess))


@dp.message(F.text.regexp(r"^🗑\s*Qolip\s+O['‘`ʼ]chirish$"))
async def remove_mold_start(msg: Message):
    sess = user_sessions[msg.from_user.id]
    if not sess.get("is_admin"):
        return await msg.answer("❌ Sizda ruxsat yo‘q.")

    molds = db.get_all_molds()
    if not molds:
        return await msg.answer("❌ Qoliplar mavjud emas.")

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=m)] for m in molds] + [[CANCEL_BUTTON]],
        resize_keyboard=True
    )
    sess["state"] = "awaiting_remove_mold"
    await msg.answer("🗑 O‘chirmoqchi bo‘lgan qolipni tanlang:", reply_markup=kb)


@dp.message(lambda m: user_sessions.get(m.from_user.id, {}).get("state") == "awaiting_remove_mold")
async def remove_mold_finish(msg: Message):
    if msg.text == "❌ Bekor qilish":
        return await cancel_prod(msg)

    mold_name = msg.text.strip()
    if mold_name not in db.get_all_molds():
        return await msg.answer("❌ Bunday qolip topilmadi.")

    db.remove_mold(mold_name)
    sess = user_sessions[msg.from_user.id]
    sess["state"] = "logged_in"
    await msg.answer(f"🗑 Qolip o‘chirildi: {mold_name}", reply_markup=main_menu(sess))


@dp.message(F.text == "📋 Qoliplar")
async def show_molds(msg: Message):
    molds = db.get_all_molds()
    if not molds:
        return await msg.answer("❌ Qoliplar mavjud emas.")
    await msg.answer("📋 Hozirgi qoliplar:\n" + "\n".join(f"• {m}" for m in molds))


# =========================
# 🚫 FIX for "Iltimos, menyudan tanlang."
# =========================




from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
import pytz

UZB_TZ = pytz.timezone("Asia/Tashkent")

# 📝 Mening yozuvlarim
@dp.message(F.text == "📝 Mening Yozuvlarim")
async def my_entries(msg: Message):
    sess = user_sessions[msg.from_user.id]
    records = [r for r in db.get_productions() if r["name"] == sess["name"]]

    if not records:
        return await msg.answer("Hozircha yozuvlar yo‘q.")

    # Only last 10 entries, newest first
    records = sorted(records, key=lambda r: r["date"], reverse=True)[:10]
    sess["my_entries"] = records

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{i+1}. {r.get('production_type', '—')} ×{r.get('quantity', 0)} | {format_uzb_time(r.get('date'))}",
                callback_data=f"edit:{i}"
            )]
            for i, r in enumerate(records)
        ]
    )
    await msg.answer("✏️ Tahrirlash yoki o‘chirish uchun yozuvni tanlang:", reply_markup=kb)


def format_uzb_time(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(tzinfo=pytz.utc).astimezone(UZB_TZ)
        return dt.strftime("%d.%m %H:%M")
    except:
        return date_str or "—"


@dp.callback_query(F.data.startswith("edit:"))
async def edit_entry(call: CallbackQuery):
    sess = user_sessions[call.from_user.id]
    idx = int(call.data.split(":")[1])
    rec = sess["my_entries"][idx]
    sess["editing"] = {"id": rec.get("id"), "idx": idx}

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Qolip turi", callback_data=f"edit_model:{idx}")],
        [InlineKeyboardButton(text="🔢 Miqdor", callback_data=f"edit_qty:{idx}")],
        [InlineKeyboardButton(text="🗑 O‘chirish", callback_data=f"delete:{idx}")]
    ])

    await call.message.answer(
        f"🏷 Qolip turi: {rec.get('production_type', '—')}\n"
        f"📦 Miqdor: {rec.get('quantity', 0)}\n"
        f"🕒 Sana: {format_uzb_time(rec.get('date'))}\n\n"
        f"Qaysi amaliyotni bajarmoqchisiz?",
        reply_markup=kb
    )
    await call.answer()


@dp.callback_query(F.data.startswith("edit_model:"))
async def edit_model(call: CallbackQuery):
    idx = int(call.data.split(":")[1])
    sess = user_sessions[call.from_user.id]
    rec = sess["my_entries"][idx]
    sess["editing"] = {"id": rec.get("id"), "field": "production_type"}

    molds = db.get_all_molds()
    if not molds:
        return await call.message.answer("❌ Hozircha qoliplar mavjud emas. Admin qo‘shishi kerak.")

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=m)] for m in molds] + [[CANCEL_BUTTON]],
        resize_keyboard=True
    )
    await call.message.answer("✏️ Yangi qolip turini tanlang:", reply_markup=kb)
    await call.answer()


@dp.callback_query(F.data.startswith("edit_qty:"))
async def edit_qty(call: CallbackQuery):
    idx = int(call.data.split(":")[1])
    sess = user_sessions[call.from_user.id]
    rec = sess["my_entries"][idx]
    sess["editing"] = {"id": rec.get("id"), "field": "quantity"}
    await call.message.answer("🔢 Yangi miqdorni kiriting:", reply_markup=ReplyKeyboardMarkup(
        keyboard=[[CANCEL_BUTTON]],
        resize_keyboard=True
    ))
    await call.answer()


@dp.callback_query(F.data.startswith("delete:"))
async def delete_entry(call: CallbackQuery):
    idx = int(call.data.split(":")[1])
    sess = user_sessions[call.from_user.id]
    rec = sess["my_entries"][idx]

    if hasattr(db, "delete_production"):  # Real delete if implemented
        db.delete_production(rec.get("id"))
    else:
        db.update_production(rec.get("id"), {"quantity": 0})

    await call.message.answer("🗑 Yozuv o‘chirildi!", reply_markup=main_menu(sess))
    await call.answer()


@dp.message(lambda m: "editing" in user_sessions.get(m.from_user.id, {}))
async def process_edit(msg: Message):
    sess = user_sessions[msg.from_user.id]
    rec = sess["editing"]

    if msg.text == "❌ Bekor qilish":
        sess.pop("editing", None)
        sess["state"] = "logged_in"
        return await msg.answer("Bekor qilindi.", reply_markup=main_menu(sess))

    if rec["field"] == "quantity":
        if not msg.text.strip().isdigit():
            return await msg.answer("❌ Miqdor faqat raqam bo‘lishi kerak.")
        db.update_production(rec["id"], {"quantity": int(msg.text.strip())})

    elif rec["field"] == "production_type":
        molds = db.get_all_molds()
        if msg.text not in molds:
            return await msg.answer("❌ Iltimos, ro‘yxatdan qolip tanlang.")
        db.update_production(rec["id"], {"production_type": msg.text.strip()})

    sess.pop("editing", None)
    sess["state"] = "logged_in"
    await msg.answer("✅ Yangilandi!", reply_markup=main_menu(sess))



# 👥 Manage Users (Admin Only)
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram import F
from aiogram.types import Message, CallbackQuery

@dp.message(F.text == "👥 Foydalanuvchilarni Boshqarish")
async def manage_users(msg: Message):
    sess = user_sessions.get(msg.from_user.id)
    if not sess or not sess.get("is_admin"):
        return await msg.answer("🚫 Ruxsat berilmagan.")

    users = db.get_all_users()
    if not users:
        user_list = "⚠️ Foydalanuvchilar topilmadi."
    else:
        user_list = "\n".join(
            f"👤 {d['name']} (@ {u}) | 🔑 Parol: {d.get('password', '❓')} | "
            f"Admin: {'✅' if d['is_admin'] else '❌'} | "
            for u, d in users.items()
        )

    # Admin foydalanuvchilarni boshqarish menyusi
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➖ Foydalanuvchini O‘chirish")],
            [KeyboardButton(text="❌ Bekor qilish")]
        ],
        resize_keyboard=True
    )

    await msg.answer(
        f"📋 **Foydalanuvchilar ro‘yxati:**\n\n{user_list}",
        reply_markup=kb,
        parse_mode="Markdown"
    )

# 🗑 Remove User Step 1 — Ask for username
@dp.message(F.text == "➖ Foydalanuvchini O‘chirish")
async def ask_remove_user(msg: Message):
    sess = user_sessions.get(msg.from_user.id)
    if not sess or not sess.get("is_admin"):
        return await msg.answer("🚫 Ruxsat berilmagan.")

    sess["state"] = "removing_user"
    await msg.answer("✏️ O‘chirmoqchi bo‘lgan foydalanuvchi nomini yuboring (@ belgisisiz).")


# 🗑 2-qadam — Foydalanuvchini o‘chirish jarayoni
@dp.message(lambda m: user_sessions.get(m.from_user.id, {}).get("state") == "removing_user")
async def process_remove_user(msg: Message):
    sess = user_sessions[msg.from_user.id]
    username_to_remove = msg.text.strip().lstrip("@")

    if not db.get_user(username_to_remove):
        sess["state"] = "logged_in"
        return await msg.answer("⚠️ Foydalanuvchi topilmadi.", reply_markup=main_menu(sess))

    db.delete_user(username_to_remove)  # db.py ichida amalga oshirilishi kerak
    sess["state"] = "logged_in"
    await msg.answer(f"✅ Foydalanuvchi `{username_to_remove}` o‘chirildi.", reply_markup=main_menu(sess), parse_mode="Markdown")

# 🚪 Bekor qilish
@dp.message(F.text == "❌ Bekor qilish")
async def cancel_manage_users(msg: Message):
    sess = user_sessions.get(msg.from_user.id)
    if sess:
        sess["state"] = "logged_in"
    await msg.answer("❌ Bekor qilindi.", reply_markup=main_menu(sess))


@dp.message(F.text == "📊 Barcha Ma'lumotlar")
async def all_data(msg: Message):
    sess = user_sessions.get(msg.from_user.id)
    if not sess or not sess.get("is_admin"):
        return await msg.answer("🚫 Ruxsat yo‘q.")

    try:
        rows = db.get_productions()
        if not rows:
            return await msg.answer("📭 Ishlab chiqarish bo‘yicha ma'lumotlar mavjud emas.")

        df = pd.DataFrame(rows)

        # ---- Map usernames -> display names (no structure change)
        users_map = {username: info["name"] for username, info in db.get_all_users().items()}
        if "name" in df.columns:
            df["name"] = df["name"].map(lambda x: users_map.get(x, x))

        # ---- Keep production_type as simple text
        if "production_type" in df.columns:
            df["production_type"] = df["production_type"].astype(str)
        else:
            df["production_type"] = ""

        # ---- Ensure date column exists
        if "date" not in df.columns:
            return await msg.answer("⚠️ Ma'lumotlar bazasida 'date' ustuni yo‘q.")

        # ---- Parse dates
        df["date_parsed"] = pd.to_datetime(df["date"], errors="coerce")
        if df["date_parsed"].isna().all():
            return await msg.answer("⚠️ Sana formatlari noto‘g‘ri. Hech bir yozuvni o‘qib bo‘lmadi.")

        # ---- Coerce quantity to int
        if "quantity" not in df.columns:
            df["quantity"] = 0
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)

        now = datetime.now()
        df_valid = df.dropna(subset=["date_parsed"]).copy()

        df_month = df_valid[
            (df_valid["date_parsed"].dt.year == now.year) &
            (df_valid["date_parsed"].dt.month == now.month)
        ].copy()

        if df_month.empty:
            return await msg.answer(f"📭 {now.strftime('%B %Y')} oyida ma'lumotlar topilmadi.")

        df_month["kun"] = df_month["date_parsed"].dt.day

        # =================== TEXT OUTPUT ===================
        text_lines = [f"📊 Ishlab chiqarish hisobot — {now.strftime('%B %Y')}\n"]

        for day in sorted(df_month["kun"].unique()):
            df_day = df_month[df_month["kun"] == day]
            day_total = int(df_day["quantity"].sum())
            text_lines.append(f"📅 {day}-kun — Jami: {day_total} dona")

            worker_totals = (
                df_day.groupby("name")["quantity"]
                .sum()
                .sort_values(ascending=False)
            )
            for worker, wtot in worker_totals.items():
                text_lines.append(f"  👤 {worker}: {int(wtot)} dona")
                df_w = df_day[df_day["name"] == worker]
                model_totals = df_w.groupby("production_type")["quantity"].sum()
                for model, mqty in model_totals.items():
                    text_lines.append(f"    • {model}: {int(mqty)} dona")
            text_lines.append("")

        text_lines.append("📈 Oylik jami (ishchi bo‘yicha):")
        worker_month = (
            df_month.groupby("name")["quantity"]
            .sum()
            .sort_values(ascending=False)
        )
        for worker, qty in worker_month.items():
            text_lines.append(f"  👤 {worker}: {int(qty)} dona")

        text_lines.append("\n📦 Oylik jami (model bo‘yicha):")
        model_month = (
            df_month.groupby("production_type")["quantity"]
            .sum()
            .sort_values(ascending=False)
        )
        for model, qty in model_month.items():
            text_lines.append(f"  • {model}: {int(qty)} dona")

        total_month = int(df_month["quantity"].sum())
        text_lines.append(f"\n🧾 Umumiy jami (oy): {total_month} dona")

        # =================== EXCEL OUTPUT ===================
        excel_df = df_month.copy()
        for c in ["id", "name", "production_type", "quantity", "date"]:
            if c not in excel_df.columns:
                excel_df[c] = "" if c != "quantity" else 0

        raw_sheet = (
            excel_df[["id", "name", "production_type", "quantity", "date"]]
            .sort_values("date")
            .rename(columns={
                "id": "ID",
                "name": "Ishchi",
                "production_type": "Model",
                "quantity": "Soni",
                "date": "Sana"
            })
        )

        # Daily worker + model
        daily_wm = (
            df_month.groupby(["kun", "name", "production_type"])["quantity"]
            .sum()
            .reset_index()
            .rename(columns={
                "kun": "Kun",
                "name": "Ishchi",
                "production_type": "Model",
                "quantity": "Soni"
            })
            .sort_values(["Kun", "Ishchi", "Model"])
        )

        # Daily worker totals
        daily_ws = (
            df_month.groupby(["kun", "name"])["quantity"]
            .sum()
            .reset_index()
            .rename(columns={
                "kun": "Kun",
                "name": "Ishchi",
                "quantity": "JamiSoni"
            })
            .sort_values(["Kun", "JamiSoni"], ascending=[True, False])
        )

        # Monthly worker totals
        worker_totals_df = (
            worker_month.reset_index()
            .rename(columns={"name": "Ishchi", "quantity": "Soni"})
        )

        # Monthly model totals
        model_totals_df = (
            model_month.reset_index()
            .rename(columns={"production_type": "Model", "quantity": "Soni"})
        )

        # ✅ NEW: Monthly worker + model totals
        worker_model_month_df = (
            df_month.groupby(["name", "production_type"])["quantity"]
            .sum()
            .reset_index()
            .rename(columns={
                "name": "Ishchi",
                "production_type": "Model",
                "quantity": "Soni"
            })
            .sort_values(["Ishchi", "Model"])
        )

        # Save Excel
        fname = f"Barcha_Malumotlar_{now.strftime('%Y-%m')}.xlsx"
        with pd.ExcelWriter(fname, engine="openpyxl") as writer:
            raw_sheet.to_excel(writer, sheet_name="Xom", index=False)
            daily_wm.to_excel(writer, sheet_name="Kunlik_Ishchi_Model", index=False)
            daily_ws.to_excel(writer, sheet_name="Kunlik_Ishchi_Jami", index=False)
            worker_totals_df.to_excel(writer, sheet_name="Oylik_Ishchi_Jami", index=False)
            model_totals_df.to_excel(writer, sheet_name="Oylik_Model_Jami", index=False)
            worker_model_month_df.to_excel(writer, sheet_name="Oylik_Ishchi_Model", index=False)  # ✅ new sheet

        # =================== SEND TEXT + FILE ===================
        assembled = "\n".join(text_lines)
        max_len = 3900
        if len(assembled) <= max_len:
            await msg.answer(assembled)
        else:
            start = 0
            while start < len(assembled):
                await msg.answer(assembled[start:start + max_len])
                start += max_len

        await msg.answer_document(FSInputFile(fname))

    except Exception as e:
        print("Xatolik (all_data):", e)
        await msg.answer(f"⚠️ Hisobot yaratishda xatolik: {e}")



from aiogram import F
from aiogram.types import Message, FSInputFile
import pandas as pd
from datetime import datetime, date
import db  # your DB module

@dp.message(F.text == "🗓 Kunlik Hisobot")
async def daily_report(msg: Message):
    print("[DEBUG] Daily report button clicked, text:", msg.text)
    sess = user_sessions.get(msg.from_user.id)
    if not sess or not sess.get("is_admin"):
        print("[DEBUG] Access denied for user:", msg.from_user.id)
        return await msg.answer("🚫 Ruxsat etilmagan.")

    today = date.today()
    print("[DEBUG] Today is:", today)

    # 1️⃣ Fetch all productions from DB
    all_recs = db.get_productions()
    print("[DEBUG] All productions from DB:", all_recs)

    # 2️⃣ Filter today's records
    recs = []
    for r in all_recs:
        r_date = r.get("date")
        parsed_date = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y"):
            try:
                parsed_date = datetime.strptime(str(r_date), fmt).date()
                break
            except ValueError:
                continue
        if not parsed_date:
            print(f"[DEBUG] Skipping record with bad date format: {r_date}")
            continue
        if parsed_date == today:
            recs.append(r)

    print("[DEBUG] Today's matched records:", recs)

    if not recs:
        return await msg.answer("📭 Bugun hech qanday yozuv yo‘q.")

    # 3️⃣ Refresh worker names
    users = db.get_all_users()
    print("[DEBUG] All users from DB:", users)

    for rec in recs:
        raw_name = str(rec.get("name", "")).strip()
        if raw_name in users:
            rec["name"] = users[raw_name]["name"]
        else:
            match = next((u["name"] for uname, u in users.items() if uname.lower() == raw_name.lower()), None)
            if match:
                rec["name"] = match
            else:
                print(f"[DEBUG] No user match for production name: {raw_name}")

    # 4️⃣ Map molds
    molds_list = db.get_all_molds()
    molds_map = {str(name).strip().lower(): name for name in molds_list}
    print("[DEBUG] All molds:", molds_list)

    for rec in recs:
        ptype = str(rec.get("production_type", "")).strip()
        rec["production_type"] = molds_map.get(ptype.lower(), ptype or "❓ Model yo‘q")

    # 5️⃣ Create DataFrame
    df = pd.DataFrame(recs)

    for col in ["name", "production_type", "quantity", "date"]:
        if col not in df.columns:
            df[col] = ""

    df.rename(columns={
        "name": "👤 Ishchi",
        "production_type": "📦 Model",
        "quantity": "🔢 Miqdor",
        "date": "📅 Sana"
    }, inplace=True)

    df["🔢 Miqdor"] = pd.to_numeric(df["🔢 Miqdor"], errors="coerce").fillna(0).astype(int)
    df["📅 Sana"] = pd.to_datetime(df["📅 Sana"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")

    # 6️⃣ Build text output
    text_lines = [f"📊 **Kunlik Ishlab Chiqarish Hisoboti — {today.strftime('%d.%m.%Y')}**\n"]

    group = df.groupby(["👤 Ishchi", "📦 Model"], dropna=False)["🔢 Miqdor"].sum().reset_index()

    for worker in sorted(group["👤 Ishchi"].fillna("❓ Noma'lum").unique()):
        text_lines.append(f"👤 {worker}:")
        models_for_worker = group[group["👤 Ishchi"] == worker]
        total_worker = 0
        for _, row in models_for_worker.iterrows():
            model = row["📦 Model"] if pd.notna(row["📦 Model"]) else "❓ Model yo‘q"
            qty = int(row["🔢 Miqdor"])
            total_worker += qty
            text_lines.append(f"    • {model}: {qty} dona")
        text_lines.append(f"  🔹 Jami: {total_worker} dona\n")

    total_qty = int(df["🔢 Miqdor"].sum())
    text_lines.append(f"🛠 **Umumiy kunlik jami**: {total_qty} dona")

    # 7️⃣ Save Excel with better structure
    fname = f"Kunlik_Hisobot_{today.strftime('%Y-%m-%d')}.xlsx"

    # Extra breakdown for Excel
    worker_model_df = group.rename(columns={
        "👤 Ishchi": "Ishchi",
        "📦 Model": "Model",
        "🔢 Miqdor": "Soni"
    })

    worker_total_df = df.groupby("👤 Ishchi")["🔢 Miqdor"].sum().reset_index().rename(columns={
        "👤 Ishchi": "Ishchi",
        "🔢 Miqdor": "Kunlik Jami"
    })

    with pd.ExcelWriter(fname, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name="Xom Ma'lumot", index=False)
        worker_model_df.to_excel(writer, sheet_name="Ishchi_Model", index=False)
        worker_total_df.to_excel(writer, sheet_name="Ishchi_Kunlik_Jami", index=False)

    print("[DEBUG] Excel saved as:", fname)

    # 8️⃣ Send to Telegram
    assembled = "\n".join(text_lines)
    max_len = 3900
    if len(assembled) <= max_len:
        await msg.answer(assembled)
    else:
        start = 0
        while start < len(assembled):
            await msg.answer(assembled[start:start + max_len])
            start += max_len

    await msg.answer_document(FSInputFile(fname))
    print("========== DAILY REPORT END ==========")


# ⚙ Edit Profile
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# ⚙ Profilni Tahrirlash
@dp.message(F.text == "⚙ Profilni Tahrirlash")
async def edit_profile(msg: Message):
    print("[DEBUG] Edit profile clicked")
    sess = user_sessions[msg.from_user.id]
    sess["state"] = "editing_profile"

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Bekor qilish")]
        ],
        resize_keyboard=True
    )

    await msg.answer(
        "✏️ Yangi ismingizni yuboring yoki ❌ Bekor qilish tugmasini bosing:",
        reply_markup=kb
    )


# ❌ Profil tahririni bekor qilish (works anywhere now)
@dp.message(F.text == "❌ Bekor qilish")
async def cancel_edit_profile(msg: Message):
    print("[DEBUG] Cancel pressed")
    sess = user_sessions.get(msg.from_user.id)

    if sess:
        sess["state"] = "logged_in"  # Always reset to logged_in
        await msg.answer("✅ Amaliyot bekor qilindi.", reply_markup=main_menu(sess))
    else:
        await msg.answer("⚠️ Siz tizimga kirmagansiz.")


# Save new profile name when in editing_profile
@dp.message(lambda m: user_sessions.get(m.from_user.id, {}).get("state") == "editing_profile")
async def save_profile(msg: Message):
    print(f"[DEBUG] Saving new profile name: {msg.text}")
    new_name = msg.text.strip()
    sess = user_sessions[msg.from_user.id]
    db.update_user(sess["username"], {"name": new_name})
    sess["name"] = new_name
    sess["state"] = "logged_in"
    await msg.answer(f"✅ Ism {new_name} ga o‘zgartirildi.", reply_markup=main_menu(sess))

# 🚪 Chiqish
@dp.message(F.text == "🚪 Chiqish")
async def logout(msg: Message):
    user_sessions.pop(msg.from_user.id, None)
    await msg.answer("✅ Tizimdan chiqdingiz.", reply_markup=ReplyKeyboardRemove())

@dp.message()
async def fallback(msg: Message):
    await msg.answer("📋 Iltimos, menyudan tanlang.")

if __name__ == "__main__":
    print("[BOT] Started")
    asyncio.run(dp.start_polling(bot))
