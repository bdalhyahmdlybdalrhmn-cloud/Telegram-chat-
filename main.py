from flask import Flask, request, jsonify, render_template
import requests
from collections import defaultdict
import time

app = Flask(__name__)

# ⚠️ الأفضل تحطه في ENV مش هنا
import os

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# 🧠 ذاكرة لكل مستخدم
chat_history = defaultdict(list)
MAX_HISTORY = 10

# 🛡️ anti spam بسيط
last_request_time = defaultdict(float)
MIN_DELAY = 1.5  # ثانية بين كل رسالة


SYSTEM_PROMPT = """
أنت مساعد ذكي مثل ChatGPT.
- اشرح بشكل واضح وبسيط
- استخدم أمثلة عند الحاجة
- لو السؤال برمجة، أعطِ كود صحيح
- لا تختصر إلا إذا طلب المستخدم
"""


# 🧠 AI Router ذكي
def choose_model(msg: str):
    msg = msg.lower()

    coding = ["code", "python", "flask", "api", "bug", "error", "json", "sql"]
    reasoning = ["why", "explain", "how", "difference", "compare", "what is"]

    if any(x in msg for x in coding):
        return "llama-3.3-70b-versatile"

    if any(x in msg for x in reasoning):
        return "llama-3.1-70b-versatile"

    if len(msg) < 20:
        return "llama-3.1-8b-instant"

    return "llama-3.1-70b-versatile"


# 🔥 استدعاء API مع fallback
def call_groq(model, messages):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        res = requests.post(
            GROQ_URL,
            headers=headers,
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.7
            },
            timeout=25
        )

        data = res.json()

        if "error" in data:
            return None, data["error"]["message"]

        return data["choices"][0]["message"]["content"], None

    except Exception as e:
        return None, str(e)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()

    msg = data.get("message", "")
    user_id = data.get("user_id", "default")

    # 🛡️ anti spam
    now = time.time()
    if now - last_request_time[user_id] < MIN_DELAY:
        return jsonify({"reply": "❌ اهدى شوية بين الرسائل"}), 429

    last_request_time[user_id] = now

    if not msg:
        return jsonify({"reply": "اكتب رسالة أول"}), 400

    model = choose_model(msg)

    history = chat_history[user_id]

    # ➕ add user message
    history.append({"role": "user", "content": msg})

    # ✂️ limit history
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]

    chat_history[user_id] = history

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    # 🚀 1st attempt
    reply, error = call_groq(model, messages)

    # 🔁 fallback لو فشل
    if error:
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
        return jsonify({"reply": f"فشل الاتصال بالذكاء الاصطناعي: {error}"}), 500

    # ➕ save assistant reply
    chat_history[user_id].append({"role": "assistant", "content": reply})

    return jsonify({
        "reply": reply,
        "model_used": model
    })


if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)