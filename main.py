from flask import Flask, request, jsonify, render_template
import requests
from collections import defaultdict
import time
import os

app = Flask(__name__)

# =========================
# 🔐 CONFIG
# =========================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# =========================
# 🧠 MEMORY SYSTEM
# =========================
chat_history = defaultdict(list)
history_time = defaultdict(float)
last_request_time = defaultdict(float)

MAX_HISTORY = 12
EXPIRY_TIME = 3600      # ساعة
MIN_DELAY = 1.2         # anti spam أقوى

# =========================
# 🧠 SYSTEM PROMPT (محسن)
# =========================
SYSTEM_PROMPT = """
أنت مساعد ذكي احترافي مثل ChatGPT.

قواعدك:
- اشرح بوضوح وبأسلوب بسيط
- حل المشاكل خطوة خطوة
- لو برمجة: اعطِ كود كامل قابل للتشغيل
- لا تخترع معلومات غير مؤكدة
- ركّز على الحلول العملية
- لو السؤال غامض اسأل توضيح
- استخدم تنسيق منظم في الإجابة
"""

# =========================
# 🧹 CLEAN MEMORY
# =========================
def clean_memory(user_id):
    now = time.time()

    if now - history_time[user_id] > EXPIRY_TIME:
        chat_history[user_id].clear()
        history_time[user_id] = now

# =========================
# 🧠 SMART MODEL SELECTOR
# =========================
def choose_model(msg: str):
    msg = msg.lower()

    coding_keywords = [
        "code", "python", "flask", "api", "bug",
        "error", "json", "sql", "javascript", "html"
    ]

    reasoning_keywords = [
        "why", "explain", "how", "difference",
        "compare", "what is", "logic"
    ]

    if any(k in msg for k in coding_keywords):
        return "llama-3.3-70b-versatile"

    if any(k in msg for k in reasoning_keywords):
        return "llama-3.1-70b-versatile"

    if len(msg) < 25:
        return "llama-3.1-8b-instant"

    return "llama-3.1-70b-versatile"

# =========================
# 🔥 CALL GROQ API
# =========================
def call_groq(model, messages):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7
    }

    try:
        res = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
        data = res.json()

        if "error" in data:
            return None, data["error"]["message"]

        return data["choices"][0]["message"]["content"], None

    except Exception as e:
        return None, str(e)

# =========================
# 🌐 ROUTES
# =========================
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()

    msg = data.get("message", "")
    user_id = data.get("user_id", "default")

    # 🧹 تنظيف الذاكرة
    clean_memory(user_id)

    # 🛡️ anti spam
    now = time.time()
    if now - last_request_time[user_id] < MIN_DELAY:
        return jsonify({"reply": "❌ استنى شوية بين الرسائل"}), 429

    last_request_time[user_id] = now

    if not msg.strip():
        return jsonify({"reply": "اكتب رسالة أول"}), 400

    # 🧠 اختيار موديل
    model = choose_model(msg)

    # 📚 history
    history = chat_history[user_id]

    history.append({"role": "user", "content": msg})

    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]

    chat_history[user_id] = history

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    # 🚀 محاولة أولى
    reply, error = call_groq(model, messages)

    # 🔁 fallback ذكي
    if error or not reply:
        fallback_models = [
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant"
        ]

        for m in fallback_models:
            reply, error = call_groq(m, messages)
            if reply:
                model = m
                break

    if not reply:
        return jsonify({
            "reply": f"❌ فشل الاتصال: {error}"
        }), 500

    # 💾 حفظ الرد
    chat_history[user_id].append({
        "role": "assistant",
        "content": reply
    })

    return jsonify({
        "reply": reply,
        "model_used": model,
        "history_length": len(chat_history[user_id])
    })

# =========================
# 🚀 RUN
# =========================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)