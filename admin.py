from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
import sqlite3
from datetime import datetime
import subprocess
import threading
from config import ADMIN_IDS

app = Flask(__name__)
app.secret_key = "change_this_to_random_secret_key_123"

ADMIN_PASSWORD = "vika2024"  # Смени на свой пароль!

def get_db():
    conn = sqlite3.connect("leads.db")
    conn.row_factory = sqlite3.Row
    return conn

HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Панель управления</title>
<link href="https://fonts.googleapis.com/css2?family=Onest:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0e0e12;
    --surface: #16161d;
    --surface2: #1e1e28;
    --border: #2a2a38;
    --accent: #7c6af7;
    --accent2: #a78bfa;
    --green: #34d399;
    --red: #f87171;
    --yellow: #fbbf24;
    --text: #e8e8f0;
    --muted: #6b6b85;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Onest', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }

  /* LOGIN */
  .login-wrap { min-height: 100vh; display: flex; align-items: center; justify-content: center; }
  .login-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 20px; padding: 48px; width: 380px;
    box-shadow: 0 0 60px rgba(124,106,247,0.08);
  }
  .login-card h1 { font-size: 24px; font-weight: 700; margin-bottom: 8px; }
  .login-card p { color: var(--muted); font-size: 14px; margin-bottom: 32px; }
  .login-card input {
    width: 100%; background: var(--surface2); border: 1px solid var(--border);
    color: var(--text); border-radius: 12px; padding: 14px 16px;
    font-family: inherit; font-size: 15px; margin-bottom: 16px;
    transition: border-color .2s;
  }
  .login-card input:focus { outline: none; border-color: var(--accent); }
  .btn {
    width: 100%; background: var(--accent); color: #fff; border: none;
    border-radius: 12px; padding: 14px; font-family: inherit;
    font-size: 15px; font-weight: 600; cursor: pointer; transition: opacity .2s;
  }
  .btn:hover { opacity: .85; }

  /* LAYOUT */
  .layout { display: flex; min-height: 100vh; }
  .sidebar {
    width: 240px; background: var(--surface); border-right: 1px solid var(--border);
    padding: 28px 16px; display: flex; flex-direction: column; gap: 4px; position: fixed;
    height: 100vh;
  }
  .logo { font-size: 18px; font-weight: 700; padding: 0 12px 24px; letter-spacing: -.3px; }
  .logo span { color: var(--accent2); }
  .nav-item {
    display: flex; align-items: center; gap: 10px; padding: 10px 12px;
    border-radius: 10px; font-size: 14px; font-weight: 500; color: var(--muted);
    text-decoration: none; transition: all .15s; cursor: pointer;
  }
  .nav-item:hover, .nav-item.active { background: var(--surface2); color: var(--text); }
  .nav-item .icon { font-size: 18px; }
  .logout { margin-top: auto; color: var(--red) !important; }

  .main { margin-left: 240px; padding: 40px; flex: 1; }
  .page-title { font-size: 28px; font-weight: 700; margin-bottom: 8px; }
  .page-sub { color: var(--muted); font-size: 14px; margin-bottom: 36px; }

  /* STATS CARDS */
  .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 40px; }
  .stat-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 16px; padding: 24px; position: relative; overflow: hidden;
  }
  .stat-card::before {
    content: ''; position: absolute; top: -30px; right: -30px;
    width: 100px; height: 100px; border-radius: 50%;
    background: var(--accent); opacity: .06;
  }
  .stat-label { font-size: 13px; color: var(--muted); font-weight: 500; margin-bottom: 10px; }
  .stat-value { font-size: 36px; font-weight: 700; letter-spacing: -1px; }
  .stat-value.green { color: var(--green); }
  .stat-value.purple { color: var(--accent2); }
  .stat-value.yellow { color: var(--yellow); }

  /* TABLE */
  .table-wrap { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; overflow: hidden; }
  .table-header { padding: 20px 24px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
  .table-header h3 { font-size: 16px; font-weight: 600; }
  .badge { background: var(--accent); color: #fff; font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 20px; }
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; padding: 12px 24px; font-size: 12px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .5px; border-bottom: 1px solid var(--border); }
  td { padding: 14px 24px; font-size: 14px; border-bottom: 1px solid rgba(42,42,56,.5); }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: var(--surface2); }
  .tg-link { color: var(--accent2); text-decoration: none; }
  .tg-link:hover { text-decoration: underline; }
  .dot { width: 8px; height: 8px; background: var(--green); border-radius: 50%; display: inline-block; margin-right: 6px; }

  /* BROADCAST */
  .broadcast-card { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 32px; }
  .broadcast-card h3 { font-size: 18px; font-weight: 600; margin-bottom: 8px; }
  .broadcast-card p { color: var(--muted); font-size: 14px; margin-bottom: 24px; }
  textarea {
    width: 100%; background: var(--surface2); border: 1px solid var(--border);
    color: var(--text); border-radius: 12px; padding: 16px;
    font-family: inherit; font-size: 15px; resize: vertical; min-height: 140px;
    margin-bottom: 16px; transition: border-color .2s;
  }
  textarea:focus { outline: none; border-color: var(--accent); }
  .btn-send {
    background: var(--accent); color: #fff; border: none; border-radius: 12px;
    padding: 14px 28px; font-family: inherit; font-size: 15px; font-weight: 600;
    cursor: pointer; transition: opacity .2s; display: inline-flex; align-items: center; gap: 8px;
  }
  .btn-send:hover { opacity: .85; }
  .alert { padding: 14px 18px; border-radius: 10px; margin-bottom: 20px; font-size: 14px; font-weight: 500; }
  .alert-success { background: rgba(52,211,153,.1); border: 1px solid rgba(52,211,153,.3); color: var(--green); }
  .alert-error { background: rgba(248,113,113,.1); border: 1px solid rgba(248,113,113,.3); color: var(--red); }

  /* HISTORY TABLE */
  .history-table { margin-top: 32px; }
  .section-title { font-size: 16px; font-weight: 600; margin-bottom: 16px; }

  @media (max-width: 768px) {
    .sidebar { display: none; }
    .main { margin-left: 0; padding: 20px; }
    .stats-grid { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>

{% if not session.get('logged_in') %}
<div class="login-wrap">
  <div class="login-card">
    <h1>🔐 Войти</h1>
    <p>Панель управления ботом</p>
    {% if error %}<div class="alert alert-error">{{ error }}</div>{% endif %}
    <form method="POST" action="/login">
      <input type="password" name="password" placeholder="Пароль" autofocus>
      <button type="submit" class="btn">Войти →</button>
    </form>
  </div>
</div>

{% else %}
<div class="layout">
  <aside class="sidebar">
    <div class="logo">Lead<span>Bot</span> ✦</div>
    <a class="nav-item {% if page == 'dashboard' %}active{% endif %}" href="/">
      <span class="icon">📊</span> Дашборд
    </a>
    <a class="nav-item {% if page == 'leads' %}active{% endif %}" href="/leads">
      <span class="icon">👥</span> База контактов
    </a>
    <a class="nav-item {% if page == 'broadcast' %}active{% endif %}" href="/broadcast">
      <span class="icon">📨</span> Рассылка
    </a>
    <a class="nav-item logout" href="/logout">
      <span class="icon">🚪</span> Выйти
    </a>
  </aside>

  <main class="main">

    {% if page == 'dashboard' %}
    <div class="page-title">Дашборд</div>
    <div class="page-sub">Обзор твоей базы лидов</div>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">👥 Всего лидов</div>
        <div class="stat-value purple">{{ stats.total }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">📅 Сегодня</div>
        <div class="stat-value green">{{ stats.today }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">📨 Рассылок отправлено</div>
        <div class="stat-value yellow">{{ stats.broadcasts }}</div>
      </div>
    </div>

    <div class="table-wrap">
      <div class="table-header">
        <h3>Последние 10 лидов</h3>
        <span class="badge">{{ stats.total }} всего</span>
      </div>
      <table>
        <thead>
          <tr>
            <th>Имя</th>
            <th>Telegram</th>
            <th>Email</th>
            <th>Дата</th>
          </tr>
        </thead>
        <tbody>
          {% for lead in leads[:10] %}
          <tr>
            <td><span class="dot"></span>{{ lead.first_name or '—' }}</td>
            <td>
              {% if lead.username %}
              <a href="https://t.me/{{ lead.username }}" target="_blank" class="tg-link">@{{ lead.username }}</a>
              {% else %}
              <span style="color:var(--muted)">id{{ lead.telegram_id }}</span>
              {% endif %}
            </td>
            <td>{{ lead.email }}</td>
            <td style="color:var(--muted)">{{ lead.joined_at }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>

    {% elif page == 'leads' %}
    <div class="page-title">База контактов</div>
    <div class="page-sub">Все лиды, собранные ботом</div>

    <div class="table-wrap">
      <div class="table-header">
        <h3>Все контакты</h3>
        <span class="badge">{{ leads|length }} человек</span>
      </div>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Имя</th>
            <th>Telegram</th>
            <th>Email</th>
            <th>Дата</th>
          </tr>
        </thead>
        <tbody>
          {% for lead in leads %}
          <tr>
            <td style="color:var(--muted)">{{ loop.index }}</td>
            <td>{{ lead.first_name or '—' }}</td>
            <td>
              {% if lead.username %}
              <a href="https://t.me/{{ lead.username }}" target="_blank" class="tg-link">@{{ lead.username }}</a>
              {% else %}
              <span style="color:var(--muted)">id{{ lead.telegram_id }}</span>
              {% endif %}
            </td>
            <td>{{ lead.email }}</td>
            <td style="color:var(--muted)">{{ lead.joined_at }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>

    {% elif page == 'broadcast' %}
    <div class="page-title">Рассылка</div>
    <div class="page-sub">Отправить сообщение всем лидам в базе ({{ stats.total }} человек)</div>

    {% if flash %}
    <div class="alert {% if 'Ошибка' in flash %}alert-error{% else %}alert-success{% endif %}">{{ flash }}</div>
    {% endif %}

    <div class="broadcast-card">
      <h3>📝 Новое сообщение</h3>
      <p>Поддерживается HTML: &lt;b&gt;жирный&lt;/b&gt;, &lt;i&gt;курсив&lt;/i&gt;, &lt;a href="..."&gt;ссылка&lt;/a&gt;</p>
      <form method="POST" action="/broadcast">
        <textarea name="message" placeholder="Привет! 👋 Вот что нового...">{{ prev_message or '' }}</textarea>
        <button type="submit" class="btn-send">📨 Отправить всем ({{ stats.total }})</button>
      </form>
    </div>

    {% if broadcasts %}
    <div class="history-table">
      <div class="section-title">📋 История рассылок</div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Дата</th>
              <th>Отправлено</th>
              <th>Текст</th>
            </tr>
          </thead>
          <tbody>
            {% for b in broadcasts %}
            <tr>
              <td style="color:var(--muted); white-space:nowrap">{{ b.sent_at }}</td>
              <td><span style="color:var(--green)">{{ b.sent_count }}</span></td>
              <td style="max-width:400px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap">{{ b.message }}</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
    {% endif %}

    {% endif %}

  </main>
</div>
{% endif %}

</body>
</html>
"""

def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    today = conn.execute(
        "SELECT COUNT(*) FROM leads WHERE joined_at LIKE ?",
        (datetime.now().strftime("%Y-%m-%d") + "%",)
    ).fetchone()[0]
    try:
        broadcasts = conn.execute("SELECT COUNT(*) FROM broadcasts").fetchone()[0]
    except:
        broadcasts = 0
    conn.close()
    return {"total": total, "today": today, "broadcasts": broadcasts}

@app.route("/login", methods=["POST"])
def login():
    if request.form.get("password") == ADMIN_PASSWORD:
        session["logged_in"] = True
        return redirect("/")
    return render_template_string(HTML, page="login", session=session, error="Неверный пароль")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/")
def dashboard():
    if not session.get("logged_in"):
        return render_template_string(HTML, page="login", session=session, error=None)
    conn = get_db()
    leads = conn.execute("SELECT * FROM leads ORDER BY joined_at DESC").fetchall()
    conn.close()
    return render_template_string(HTML, page="dashboard", session=session, leads=leads, stats=get_stats())

@app.route("/leads")
def leads_page():
    if not session.get("logged_in"):
        return redirect("/")
    conn = get_db()
    leads = conn.execute("SELECT * FROM leads ORDER BY joined_at DESC").fetchall()
    conn.close()
    return render_template_string(HTML, page="leads", session=session, leads=leads, stats=get_stats())

@app.route("/broadcast", methods=["GET", "POST"])
def broadcast_page():
    if not session.get("logged_in"):
        return redirect("/")
    conn = get_db()
    try:
        broadcasts = conn.execute("SELECT * FROM broadcasts ORDER BY sent_at DESC").fetchall()
    except:
        broadcasts = []
    conn.close()
    flash = None
    prev_message = None

    if request.method == "POST":
        message = request.form.get("message", "").strip()
        if not message:
            flash = "⚠️ Нельзя отправить пустое сообщение!"
        else:
            # Run broadcast via subprocess to avoid blocking
            try:
                from broadcast_runner import send_broadcast_sync
                count = send_broadcast_sync(message)
                flash = f"✅ Рассылка завершена! Отправлено: {count} человек"
            except Exception as e:
                flash = f"Ошибка: {e}"
            prev_message = message
            # Refresh broadcasts
            conn = get_db()
            try:
                broadcasts = conn.execute("SELECT * FROM broadcasts ORDER BY sent_at DESC").fetchall()
            except:
                broadcasts = []
            conn.close()

    return render_template_string(HTML, page="broadcast", session=session,
                                   stats=get_stats(), broadcasts=broadcasts,
                                   flash=flash, prev_message=prev_message)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
