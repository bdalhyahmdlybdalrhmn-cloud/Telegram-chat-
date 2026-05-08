from flask import Flask, request, jsonify, render_template
from openai import OpenAI
from collections import defaultdict
import time

app = Flask(__name__)

# ⚠️ حط المفتاح في ENV أفضل
import os
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 🧠 ذاكرة لكل مستخدم
chat_history = defaultdict(list)
MAX_HISTORY = 10

# 🛡️ anti spam
last_request_time = defaultdict(float)
MIN_DELAY = 1.5

SYSTEM_PROMPT = """
أنت مساعد ذكي مثل ChatGPT.
- اشرح بشكل واضح وبسيط
- استخدم أمثلة عند الحاجة
- لو السؤال برمجة، أعطِ كود صحيح
- لا تختصر إلا إذا طلب المستخدم
"""


# 🧠 اختيار موديل (OpenAI فقط)
def choose_model(msg: str):
    msg = msg.lower()

    coding = ["code", "python", "flask", "api", "bug", "error", "json", "sql"]
    reasoning = ["why", "explain", "how", "difference", "compare", "what is"]

    if any(x in msg for x in coding):
        return "gpt-4o"

    if any(x in msg for x in reasoning):
        return "gpt-4o-mini"

    if len(msg) < 20:
        return "gpt-4o-mini"

    return "gpt-4o"


# 🤖 OpenAI call
def ask_openai(messages, model):
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.7
    )
    return response.choices[0].message.content


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

    # 🧠 اختيار موديل
    model = choose_model(msg)

    # 📚 history
    history = chat_history[user_id]

    history.append({"role": "user", "content": msg})

    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]

    chat_history[user_id] = history

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    try:
        reply = ask_openai(messages, model)

        chat_history[user_id].append({
            "role": "assistant",
            "content": reply
        })

        return jsonify({
            "reply": reply,
            "model_used": model
        })

    except Exception as e:
        return jsonify({
            "reply": f"Error: {str(e)}"
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)