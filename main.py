from flask import Flask, request, jsonify, render_template
import requests
from collections import defaultdict
import time
import os
import uuid

app = Flask(__name__)

# =========================
# 🔐 CONFIG
# =========================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# =========================
# 🧠 MEMORY SYSTEM (FIXED)
# =========================
chat_history = defaultdict(list)
history_time = defaultdict(float)
last_request_time = defaultdict(float)

MAX_HISTORY = 12
EXPIRY_TIME = 3600
MIN_DELAY = 1.2

# =========================
SYSTEM_PROMPT = """
أنت مساعد ذكي احترافي مثل ChatGPT.
- إجابات واضحة ومباشرة
- كود كامل قابل للتشغيل عند البرمجة
- لا تخترع معلومات
- اسأل لو السؤال غير واضح
"""

# =========================
# 🧹 CLEAN MEMORY
# =========================
def clean_memory(user_id):
    now = time.time()
    if history_time[user_id] == 0:
        history_time[user_id] = now
        return

    if now - history_time[user_id] > EXPIRY_TIME:
        chat_history[user_id].clear()
        history_time[user_id] = now

# =========================
# 🧠 USER ID FIX (IMPORTANT)
# =========================
def get_user_id():
    # 1) من الريكوست
    user_id = request.json.get("user_id")

    # 2) لو مش موجود → نستخدم IP + UUID صغير
    if not user_id:
        ip = request.remote_addr
        user_id = f"{ip}-{uuid.uuid4().hex[:6]}"

    return user_id

# =========================
def choose_model(msg: str):
    msg = msg.lower()

    if any(x in msg for x in ["code","python","flask","api","error","bug"]):
        return "llama-3.3-70b-versatile"

    if any(x in msg for x in ["why","how","explain","difference"]):
        return "llama-3.1-70b-versatile"

    if len(msg) < 25:
        return "llama-3.1-8b-instant"

    return "llama-3.1-70b-versatile"

# =========================
def call_groq(model, messages):
    try:
        res = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.7
            },
            timeout=30
        )

        data = res.json()

        if "error" in data:
            return None, data["error"]["message"]

        return data["choices"][0]["message"]["content"], None

    except Exception as e:
        return None, str(e)

# =========================
@app.route("/")
def home():
    return render_template("index.html")

# =========================
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()

    msg = data.get("message", "")
    user_id = get_user_id()

    clean_memory(user_id)

    # 🛡️ anti spam
    now = time.time()
    if now - last_request_time[user_id] < MIN_DELAY:
        return jsonify({"reply": "❌ استنى شوية"}), 429

    last_request_time[user_id] = now

    if not msg.strip():
        return jsonify({"reply": "اكتب رسالة"}), 400

    model = choose_model(msg)

    history = chat_history[user_id]
    history.append({"role": "user", "content": msg})

    chat_history[user_id] = history[-MAX_HISTORY:]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + chat_history[user_id]

    reply, error = call_groq(model, messages)

    if error or not reply:
        for fallback in ["llama-3.1-70b-versatile","llama-3.1-8b-instant"]:
            reply, error = call_groq(fallback, messages)
            if reply:
                model = fallback
                break

    if not reply:
        return jsonify({"reply": f"Error: {error}"}), 500

    chat_history[user_id].append({"role": "assistant", "content": reply})

    return jsonify({
        "reply": reply,
        "model": model,
        "user_id": user_id
    })

# =========================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)