import os
import logging
import time
import math
import pandas as pd
from datetime import datetime
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("8395935198:AAEGWdTShxqr1akwTq0bwKZSMcgQu5lLtVc")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

state = {
    "train_name": None,
    "loco": None,
    "bpc": None,
    "log": [],
    "last_station": None,
    "last_event": None,
    "stop_start": None
}

STATIONS = []
if os.path.exists("stations_sample.csv"):
    import csv
    with open("stations_sample.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            STATIONS.append({
                "name": row["Name"],
                "lat": float(row["Lat"]),
                "lon": float(row["Lon"])
            })

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2*R*math.atan2(math.sqrt(a), math.sqrt(1 - a))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚂 Train Journey Logger Bot Started!\n"
        "Commands:\n"
        "/train <Name> | <Loco> | <BPC> - Start journey\n"
        "/status - Current status\n"
        "/report - Excel report\n"
        "/reset - Reset state\n"
        "Send Live Location to track journey."
    )

async def train(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = " ".join(context.args).split("|")
    if len(parts) >= 3:
        state["train_name"] = parts[0].strip()
        state["loco"] = parts[1].strip()
        state["bpc"] = parts[2].strip()
        await update.message.reply_text(f"✅ Journey set: {state['train_name']} | {state['loco']} | {state['bpc']}")
    else:
        await update.message.reply_text("Usage: /train Name | Loco | BPC")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if state["train_name"]:
        await update.message.reply_text(f"🚉 {state['train_name']} | {state['loco']} | {state['bpc']}")
    else:
        await update.message.reply_text("No journey set. Use /train")

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not state["log"]:
        await update.message.reply_text("No log yet.")
        return
    df = pd.DataFrame(state["log"])
    fn = f"report_{int(time.time())}.xlsx"
    df.to_excel(fn, index=False)
    with open(fn, "rb") as f:
        await update.message.reply_document(InputFile(f, fn))
    os.remove(fn)

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state.update({"train_name": None, "loco": None, "bpc": None, "log": [], "last_station": None, "last_event": None, "stop_start": None})
    await update.message.reply_text("State reset.")

async def location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    lat, lon = loc.latitude, loc.longitude
    spd = loc.speed if loc.speed else 0
    nearest, dist = None, 999
    for s in STATIONS:
        d = haversine(lat, lon, s["lat"], s["lon"])
        if d < dist:
            dist, nearest = d, s
    if nearest and dist < 1.0:
        if spd < 2:
            if state["last_event"] != "arrived":
                state["stop_start"] = datetime.now()
                state["last_event"] = "arrived"
                state["last_station"] = nearest["name"]
                msg = f"🛑 Arrived {nearest['name']}"
                await update.message.reply_text(msg)
                state["log"].append({"time": datetime.now(), "event": msg})
        else:
            if state["last_event"] == "arrived":
                halt = (datetime.now() - state["stop_start"]).seconds//60
                msg = f"▶️ Departed {nearest['name']} (Halt {halt} min)"
                await update.message.reply_text(msg)
                state["log"].append({"time": datetime.now(), "event": msg})
                state["last_event"] = "departed"
    else:
        if nearest and state["last_station"] != nearest["name"]:
            msg = f"🚄 Passed {nearest['name']}"
            await update.message.reply_text(msg)
            state["log"].append({"time": datetime.now(), "event": msg})
            state["last_station"] = nearest["name"]
            state["last_event"] = "passed"
    await update.message.reply_text(f"📍 Speed: {round(spd*3.6,1)} km/h")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("train", train))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.LOCATION, location))
    app.run_polling()

if __name__ == "__main__":
    main()
