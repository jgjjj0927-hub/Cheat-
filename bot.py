# language: python, file: bot.py — offsets bot + /build, repo Cheat-
# Все значения вписаны прямо сюда. .env не нужен.
import os
import json
import sys
import base64
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8922901262:AAEu6Q5V-fo2GAdGQN6Y8qLJ4hNo9b7iZxI"
BOT_CHAT_ID = "8224529588"
GH_TOKEN = "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"
GH_REPO = "jgjjj0927-hub/Cheat-"
GH_BRANCH = "main"
WORKFLOW = "build.yml"
# ==============================================

ALLOWED = {int(x) for x in BOT_CHAT_ID.split(",") if x.strip()}
OFFSETS_KEY_PREFIX = ("DW_", "M_", "BONE_")


def is_allowed(update: Update) -> bool:
    return update.effective_chat.id in ALLOWED


def _gh_headers():
    return {"Authorization": f"Bearer {GH_TOKEN}",
            "Accept": "application/vnd.github+json"}


def _gh_get_file(path):
    url = f"https://api.github.com/repos/{GH_REPO}/contents/{path}"
    r = requests.get(url, headers=_gh_headers(), params={"ref": GH_BRANCH}, timeout=10)
    if r.status_code != 200:
        return None, None
    data = r.json()
    return data["sha"], json.loads(base64.b64decode(data["content"]).decode("utf-8"))


def _gh_put_file(path, sha, payload, message):
    url = f"https://api.github.com/repos/{GH_REPO}/contents/{path}"
    content = base64.b64encode(json.dumps(payload, indent=2).encode("utf-8")).decode("ascii")
    body = {"message": message, "content": content, "branch": GH_BRANCH}
    if sha:
        body["sha"] = sha
    r = requests.put(url, headers=_gh_headers(), json=body, timeout=10)
    return r.status_code in (200, 201)


def load_offsets():
    _, offs = _gh_get_file("offsets.json")
    return offs or {}


def save_offsets(offs, message="bot: update offsets"):
    sha, _ = _gh_get_file("offsets.json")
    return _gh_put_file("offsets.json", sha, offs, message)


def _valid_key(k):
    return any(k.startswith(p) for p in OFFSETS_KEY_PREFIX)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    kb = [
        [InlineKeyboardButton("📋 Список оффсетов", callback_data="list")],
        [InlineKeyboardButton("📥 Загрузить JSON", callback_data="show_json")],
        [InlineKeyboardButton("🔨 Собрать .exe", callback_data="build")],
    ]
    await update.message.reply_text(
        f"CS&SOFT bot (repo: {GH_REPO})\n/set KEY VALUE\n/get\n/build",
        reply_markup=InlineKeyboardMarkup(kb))


async def cmd_set(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    if len(ctx.args) != 2:
        await update.message.reply_text("Использование: /set KEY VALUE")
        return
    key, val = ctx.args
    if not _valid_key(key):
        await update.message.reply_text(f"Ключ {key} не разрешён (DW_/M_/BONE_)")
        return
    try:
        num = int(val, 0)
    except ValueError:
        await update.message.reply_text(f"Значение {val} не число")
        return
    offs = load_offsets()
    offs[key] = num
    ok = save_offsets(offs, message=f"bot: {key}={num}")
    await update.message.reply_text(f"{key} = {num}" if ok else "Ошибка записи")


async def cmd_get(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    offs = load_offsets()
    await update.message.reply_text("```\n" + json.dumps(offs, indent=2) + "\n```",
                                    parse_mode="Markdown")


async def cmd_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    offs = load_offsets()
    lines = [f"{k} = {v}" for k, v in sorted(offs.items())]
    await update.message.reply_text("\n".join(lines) or "пусто")


async def cmd_build(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    url = f"https://api.github.com/repos/{GH_REPO}/actions/workflows/{WORKFLOW}/dispatches"
    r = requests.post(url, headers=_gh_headers(),
                      json={"ref": GH_BRANCH}, timeout=10)
    if r.status_code == 204:
        await update.message.reply_text("Сборка запущена. Артефакт — в Actions.")
    elif r.status_code == 422:
        await update.message.reply_text("422: нет workflow_dispatch в build.yml")
    else:
        await update.message.reply_text(f"Ошибка: {r.status_code} {r.text[:200]}")


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_allowed(update):
        return
    if q.data == "list":
        offs = load_offsets()
        lines = [f"{k} = {v}" for k, v in sorted(offs.items())]
        await q.message.reply_text("\n".join(lines) or "пусто")
    elif q.data == "show_json":
        offs = load_offsets()
        await q.message.reply_text("```\n" + json.dumps(offs, indent=2) + "\n```",
                                   parse_mode="Markdown")
    elif q.data == "build":
        url = f"https://api.github.com/repos/{GH_REPO}/actions/workflows/{WORKFLOW}/dispatches"
        r = requests.post(url, headers=_gh_headers(),
                          json={"ref": GH_BRANCH}, timeout=10)
        if r.status_code == 204:
            await q.message.reply_text("Сборка запущена.")
        else:
            await q.message.reply_text(f"Ошибка: {r.status_code}")


def main():
    if BOT_TOKEN.startswith("ВСТАВЬ"):
        print("BOT_TOKEN не задан"); sys.exit(1)
    if not ALLOWED:
        print("BOT_CHAT_ID не задан"); sys.exit(1)
    if GH_TOKEN.startswith("ВСТАВЬ"):
        print("GH_TOKEN не задан"); sys.exit(1)
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("set", cmd_set))
    app.add_handler(CommandHandler("get", cmd_get))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("build", cmd_build))
    app.add_handler(CallbackQueryHandler(on_button))
    app.run_polling()


if __name__ == "__main__":
    main()
