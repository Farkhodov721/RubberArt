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


def main_menu(session):
    kb = ReplyKeyboardBuilder()

    if session.get("is_admin"):
        kb.button(text="📊 Barcha Ma'lumotlar")
        kb.button(text="🗓 Kunlik Hisobot")
        kb.button(text="👥 Foydalanuvchilarni Boshqarish")
        kb.button(text="➕ Foydalanuvchi Qo‘shish")
        kb.adjust(2, 2)  # Admin: first 2 buttons in one row, next 2 in another
    else:
        kb.button(text="➕ Ishlab chiqarishni Qo‘shish")
        kb.button(text="📝 Mening Yozuvlarim")
        kb.adjust(1, 1)  # Workers: each on separate row

    kb.button(text="⚙ Profilni Tahrirlash")
    kb.button(text="🚪 Chiqish")
    kb.adjust(1, 1)  # Profile & Logout each on its own row

    return kb.as_markup(resize_keyboard=True)



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


@dp.message(F.text == "➕ Ishlab chiqarishni Qo‘shish")
async def add_prod(msg: Message):
    sess = user_sessions[msg.from_user.id]
    sess["state"] = "awaiting_prod_type"
    await msg.answer(
        "Ishlab chiqarish turini kiriting:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[CANCEL_BUTTON]],
            resize_keyboard=True
        )
    )


@dp.message(lambda m: user_sessions.get(m.from_user.id, {}).get("state") == "awaiting_prod_type")
async def prod_type(msg: Message):
    if msg.text == "❌ Bekor qilish":
        await cancel_prod(msg)
        return

    sess = user_sessions[msg.from_user.id]
    sess["production_type"] = msg.text.strip()
    sess["state"] = "awaiting_quantity"
    await msg.answer(
        "Miqdorni kiriting:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[CANCEL_BUTTON]],
            resize_keyboard=True
        )
    )


@dp.message(lambda m: user_sessions.get(m.from_user.id, {}).get("state") == "awaiting_quantity")
async def prod_qty(msg: Message):
    if msg.text == "❌ Bekor qilish":
        await cancel_prod(msg)
        return

    if not msg.text.isdigit():
        return await msg.answer("Miqdor faqat raqam bo‘lishi kerak.")

    sess = user_sessions[msg.from_user.id]
    sess["quantity"] = int(msg.text.strip())
    sess["state"] = "confirming"
    await msg.answer(
        f"Tasdiqlang:\nTuri: {sess['production_type']}\nMiqdor: {sess['quantity']}",
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

    # Check if all required fields are present
    if not sess.get("production_type") or not sess.get("quantity"):
        return await msg.answer("❌ Ma'lumotlar to‘liq emas. Iltimos, qaytadan boshlang.")

    # Save to database
    db.save_production({
        "name": sess["name"],
        "production_type": sess["production_type"],
        "quantity": sess["quantity"],
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    # Prepare alert text BEFORE clearing keys
    alert_text = (
        f"📢 Yangi ishlab chiqarish yozuvi\n"
        f"👤 Ishchi: {sess['name']}\n"
        f"🆔 Foydalanuvchi nomi: @{msg.from_user.username or 'N/A'}\n"
        f"🚗 Turi: {sess['production_type']}\n"
        f"📦 Miqdor: {sess['quantity']}\n"
        f"🕒 Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

    # Update state
    sess["state"] = "logged_in"

    # Clear production keys to be safe
    sess.pop("production_type", None)
    sess.pop("quantity", None)

    # Confirm to user
    await msg.answer("✅ Saqlandi!", reply_markup=main_menu(sess))

    # Send to admins
    admins = [uid for uid, data in user_sessions.items() if data.get("is_admin")]
    for admin_id in admins:
        try:
            await bot.send_message(admin_id, alert_text)
        except Exception as e:
            print(f"Admin {admin_id} ga xabar yuborilmadi: {e}")

@dp.message(F.text == "❌ Bekor qilish")
async def cancel_prod(msg: Message):
    sess = user_sessions.get(msg.from_user.id)
    if not sess:
        user_sessions[msg.from_user.id] = {"state": "logged_in"}
        sess = user_sessions[msg.from_user.id]

    # Only cancel if user is inside production flow
    if sess.get("state") and sess.get("state") != "logged_in":
        # Remove production keys but keep user logged_in
        for key in ["state", "production_type", "quantity"]:
            sess.pop(key, None)
        sess["state"] = "logged_in"
        await msg.answer("Bekor qilindi.", reply_markup=main_menu(sess))
    else:
        # If not in production flow, just ignore or say already logged in
        await msg.answer("Bekor qilish mumkin emas yoki siz tizimdasiz.", reply_markup=main_menu(sess))

# 📝 Mening yozuvlarim
@dp.message(F.text == "📝 Mening Yozuvlarim")
async def my_entries(msg: Message):
    sess = user_sessions[msg.from_user.id]
    records = [r for r in db.get_productions() if r["name"] == sess["name"]]
    if not records:
        return await msg.answer("Hozircha yozuvlar yo‘q.")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{i+1}: {r.get('production_type', '—')} ×{r.get('quantity', 0)}", callback_data=f"edit:{i}")]
        for i, r in enumerate(records)
    ])
    await msg.answer("Tahrirlash uchun yozuvni tanlang:", reply_markup=kb)


@dp.callback_query(F.data.startswith("edit:"))
async def edit_entry(call: CallbackQuery):
    sess = user_sessions[call.from_user.id]
    idx = int(call.data.split(":")[1])
    records = [r for r in db.get_productions() if r["name"] == sess["name"]]
    rec = records[idx]

    sess["editing"] = {"id": rec.get("id"), "idx": idx}

    # Inline buttons for choosing what to edit
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Model", callback_data=f"edit_model:{idx}")],
        [InlineKeyboardButton(text="🔢 Miqdor", callback_data=f"edit_qty:{idx}")]
    ])

    await call.message.answer(
        f"📦 Model: {rec.get('model', '—')}\n🔢 Miqdor: {rec.get('quantity', 0)}\n\nQaysi maydonni o‘zgartirmoqchisiz?",
        reply_markup=kb
    )
    await call.answer()


@dp.callback_query(F.data.startswith("edit_model:"))
async def edit_model(call: CallbackQuery):
    idx = int(call.data.split(":")[1])
    sess = user_sessions[call.from_user.id]
    records = [r for r in db.get_productions() if r["name"] == sess["name"]]
    rec = records[idx]
    sess["editing"] = {"id": rec.get("id"), "field": "model"}
    await call.message.answer("✏️ Yangi model nomini kiriting:")
    await call.answer()


@dp.callback_query(F.data.startswith("edit_qty:"))
async def edit_qty(call: CallbackQuery):
    idx = int(call.data.split(":")[1])
    sess = user_sessions[call.from_user.id]
    records = [r for r in db.get_productions() if r["name"] == sess["name"]]
    rec = records[idx]
    sess["editing"] = {"id": rec.get("id"), "field": "quantity"}
    await call.message.answer("🔢 Yangi miqdorni kiriting:")
    await call.answer()


@dp.message(lambda m: "editing" in user_sessions.get(m.from_user.id, {}))
async def process_edit(msg: Message):
    sess = user_sessions[msg.from_user.id]
    rec = sess["editing"]

    if rec["field"] == "quantity":
        if not msg.text.strip().isdigit():
            return await msg.answer("Miqdor faqat raqam bo‘lishi kerak.")
        db.update_production(rec["id"], {"quantity": int(msg.text.strip())})

    elif rec["field"] == "model":
        new_model = msg.text.strip()
        if not new_model:
            return await msg.answer("Model nomi bo‘sh bo‘lishi mumkin emas.")
        # ✅ Use correct column name so it's updated everywhere
        db.update_production(rec["id"], {"production_type": new_model})

    sess.pop("editing")
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

        # Refresh worker names
        users_map = {username: info["name"] for username, info in db.get_all_users().items()}
        if "name" in df.columns:
            df["name"] = df["name"].map(lambda x: users_map.get(x, x))

        # We DO NOT call db.get_models() because it does not exist.
        # Just keep production_type column as string (no mapping).
        if "production_type" in df.columns:
            df["production_type"] = df["production_type"].astype(str)

        if 'date' not in df.columns:
            return await msg.answer("⚠️ Ma'lumotlar bazasida 'date' ustuni yo‘q.")

        df['date_parsed'] = pd.to_datetime(df['date'], errors='coerce')

        now = datetime.now()
        df_month = df[
            (df['date_parsed'].dt.year == now.year) &
            (df['date_parsed'].dt.month == now.month)
        ].copy()

        if df_month.empty:
            return await msg.answer(f"📭 {now.strftime('%B %Y')} oyida ma'lumotlar topilmadi.")

        df_month['kun'] = df_month['date_parsed'].dt.day
        df_month['quantity'] = pd.to_numeric(df_month['quantity'], errors='coerce').fillna(0).astype(int)

        text_lines = []
        text_lines.append(f"📊 Ishlab chiqarish hisobot — {now.strftime('%B %Y')}\n")

        for day in sorted(df_month['kun'].unique()):
            df_day = df_month[df_month['kun'] == day]
            day_total = int(df_day['quantity'].sum())
            text_lines.append(f"📅 {day}-kun — Jami: {day_total} dona")

            worker_totals = df_day.groupby('name')['quantity'].sum().sort_values(ascending=False)
            for worker, wtot in worker_totals.items():
                text_lines.append(f"  👤 {worker}: {int(wtot)} dona")
                df_w = df_day[df_day['name'] == worker]
                model_totals = df_w.groupby('production_type')['quantity'].sum()
                for model, mqty in model_totals.items():
                    text_lines.append(f"    • {model}: {int(mqty)} dona")
            text_lines.append("")

        text_lines.append("📈 Oylik jami (ishchi bo‘yicha):")
        worker_month = df_month.groupby('name')['quantity'].sum().sort_values(ascending=False)
        for worker, qty in worker_month.items():
            text_lines.append(f"  👤 {worker}: {int(qty)} dona")

        text_lines.append("\n📦 Oylik jami (model bo‘yicha):")
        model_month = df_month.groupby('production_type')['quantity'].sum().sort_values(ascending=False)
        for model, qty in model_month.items():
            text_lines.append(f"  • {model}: {int(qty)} dona")

        total_month = int(df_month['quantity'].sum())
        text_lines.append(f"\n🧾 Umumiy jami (oy): {total_month} dona")

        excel_df = df_month.copy()

        cols_for_raw = []
        if 'id' in excel_df.columns:
            cols_for_raw.append('id')
        cols_for_raw += ['name', 'production_type', 'quantity', 'date']

        for c in ['name', 'production_type', 'quantity', 'date']:
            if c not in excel_df.columns:
                excel_df[c] = ''

        raw_sheet = excel_df[cols_for_raw].sort_values('date')
        raw_sheet = raw_sheet.rename(columns={
            'id': 'ID',
            'name': 'Ishchi',
            'production_type': 'Model',
            'quantity': 'Soni',
            'date': 'Sana'
        })

        daily_wm = df_month.groupby(['kun', 'name', 'production_type'])['quantity'].sum().reset_index()
        daily_wm = daily_wm.rename(columns={
            'kun': 'Kun',
            'name': 'Ishchi',
            'production_type': 'Model',
            'quantity': 'Soni'
        })

        daily_ws = df_month.groupby(['kun', 'name'])['quantity'].sum().reset_index()
        daily_ws = daily_ws.rename(columns={
            'kun': 'Kun',
            'name': 'Ishchi',
            'quantity': 'JamiSoni'
        })

        worker_totals_df = worker_month.reset_index().rename(columns={
            'name': 'Ishchi',
            'quantity': 'Soni'
        })

        model_totals_df = model_month.reset_index().rename(columns={
            'production_type': 'Model',
            'quantity': 'Soni'
        })

        fname = f"Barcha_Malumotlar_{now.strftime('%Y-%m')}.xlsx"
        with pd.ExcelWriter(fname, engine='openpyxl') as writer:
            raw_sheet.to_excel(writer, sheet_name='Xom', index=False)
            daily_wm.to_excel(writer, sheet_name='Kunlik_Ishchi_Model', index=False)
            daily_ws.to_excel(writer, sheet_name='Kunlik_Ishchi_Jami', index=False)
            worker_totals_df.to_excel(writer, sheet_name='Oylik_Ishchi_Jami', index=False)
            model_totals_df.to_excel(writer, sheet_name='Oylik_Model_Jami', index=False)

        assembled = "\n".join(text_lines)
        max_len = 3900
        if len(assembled) <= max_len:
            await msg.answer(assembled)
        else:
            start = 0
            while start < len(assembled):
                await msg.answer(assembled[start:start+max_len])
                start += max_len

        await msg.answer_document(FSInputFile(fname))

    except Exception as e:
        print("Xatolik (all_data):", e)
        await msg.answer(f"⚠️ Hisobot yaratishda xatolik: {e}")


@dp.message(F.text == "🗓 Kunlik Hisobot")
async def daily_report(msg: Message):
    sess = user_sessions.get(msg.from_user.id)
    if not sess or not sess.get("is_admin"):
        return await msg.answer("🚫 Ruxsat etilmagan.")

    today = datetime.now().date()
    recs = [
        r for r in db.get_productions()
        if r["date"].startswith(today.strftime("%Y-%m-%d"))
    ]
    if not recs:
        return await msg.answer("📭 Bugun hech qanday yozuv yo‘q.")

    # Refresh worker names
    users = db.get_all_users()
    # users is dict: username → {..., "name": real name, ...}
    for rec in recs:
        if rec["name"] in users:
            rec["name"] = users[rec["name"]]["name"]

    df = pd.DataFrame(recs)

    # Drop 'id' if exists
    if "id" in df.columns:
        df.drop(columns=["id"], inplace=True)

    # Rename columns for Uzbek display, only those that exist
    rename_map = {
        "name": "👤 Ishchi",
        "production_type": "📦 Model turi",
        "quantity": "🔢 Miqdor",
        "date": "📅 Sana",
        "model": "🆕 Model nomi"
    }
    df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)

    # Clean quantity type
    df["🔢 Miqdor"] = pd.to_numeric(df["🔢 Miqdor"], errors="coerce").fillna(0).astype(int)

    # Prepare text report
    text_lines = [f"📊 **Kunlik Ishlab Chiqarish Hisoboti — {today.strftime('%d.%m.%Y')}**\n"]

    # Group by worker & model, sum quantity
    group = df.groupby(["👤 Ishchi", "📦 Model turi"])["🔢 Miqdor"].sum().reset_index()

    workers = group["👤 Ishchi"].unique()
    for worker in workers:
        text_lines.append(f"👤 {worker}:")
        models_for_worker = group[group["👤 Ishchi"] == worker]
        total_worker = 0
        for _, row in models_for_worker.iterrows():
            model = row["📦 Model turi"]
            qty = int(row["🔢 Miqdor"])
            total_worker += qty
            text_lines.append(f"    • {model}: {qty} dona")
        text_lines.append(f"  Jami: {total_worker} dona\n")

    # Total for all workers
    total_qty = df["🔢 Miqdor"].sum()
    text_lines.append(f"🛠 **Jami (kunlik)**: {total_qty} dona")

    # Save Excel with full detailed raw data for the day
    fname = f"Kunlik_Hisobot_{today.strftime('%Y-%m-%d')}.xlsx"
    df.to_excel(fname, index=False)

    # Send messages
    await msg.answer("\n".join(text_lines))
    await msg.answer_document(FSInputFile(fname))


# ⚙ Edit Profile
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# ⚙ Profilni Tahrirlash
@dp.message(F.text == "⚙ Profilni Tahrirlash")
async def edit_profile(msg: Message):
    sess = user_sessions[msg.from_user.id]
    sess["state"] = "editing_profile"

    # Bekor qilish tugmasi bilan klaviatura
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


# ❌ Profil tahririni bekor qilish
@dp.message(F.text == "❌ Bekor qilish")
async def cancel_edit_profile(msg: Message):
    sess = user_sessions.get(msg.from_user.id)
    if sess and sess.get("state") == "editing_profile":
        sess["state"] = "logged_in"
        await msg.answer("✅ Profil tahriri bekor qilindi.", reply_markup=main_menu(sess))
    else:
        await msg.answer("⚠️ Hozir profil tahriri jarayoni mavjud emas.")


@dp.message(lambda m: user_sessions.get(m.from_user.id, {}).get("state") == "editing_profile")
async def save_profile(msg: Message):
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
