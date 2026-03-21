from flask import Flask, render_template_string, request, redirect, session
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "vika_leadbot_secret_2024"

ADMIN_PASSWORD = "vika2024"

def get_db():
    conn = sqlite3.connect("leads.db")
    conn.row_factory = sqlite3.Row
    return conn

def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    today = conn.execute(
        "SELECT COUNT(*) FROM leads WHERE joined_at LIKE ?",
        (datetime.now().strftime("%Y-%m-%d") + "%",)
    ).fetchone()[0]
    by_keyword = conn.execute(
        "SELECT keyword, COUNT(*) as cnt FROM leads GROUP BY keyword ORDER BY cnt DESC"
    ).fetchall()
    broadcasts = conn.execute("SELECT COUNT(*) FROM broadcasts").fetchone()[0]
    conn.close()
    return {"total": total, "today": today, "by_keyword": by_keyword, "broadcasts": broadcasts}

HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LeadBot Admin</title>
<link href="https://fonts.googleapis.com/css2?family=Onest:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0c0c10; --surface: #14141a; --surface2: #1c1c24;
    --border: #26263a; --accent: #8b5cf6; --accent2: #a78bfa;
    --green: #34d399; --red: #f87171; --yellow: #fbbf24; --blue: #60a5fa;
    --text: #e8e8f2; --muted: #64648a;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:'Onest',sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }

  .login-wrap { min-height:100vh; display:flex; align-items:center; justify-content:center; background: radial-gradient(ellipse at 50% 0%, rgba(139,92,246,.15) 0%, transparent 70%); }
  .login-card { background:var(--surface); border:1px solid var(--border); border-radius:24px; padding:48px; width:360px; }
  .login-card h1 { font-size:22px; font-weight:700; margin-bottom:6px; }
  .login-card p { color:var(--muted); font-size:13px; margin-bottom:28px; }
  input { width:100%; background:var(--surface2); border:1px solid var(--border); color:var(--text); border-radius:12px; padding:13px 16px; font-family:inherit; font-size:14px; margin-bottom:12px; transition:border-color .2s; }
  input:focus { outline:none; border-color:var(--accent); }
  .btn-main { width:100%; background:var(--accent); color:#fff; border:none; border-radius:12px; padding:13px; font-family:inherit; font-size:15px; font-weight:600; cursor:pointer; transition:opacity .2s; }
  .btn-main:hover { opacity:.85; }
  .error { background:rgba(248,113,113,.1); border:1px solid rgba(248,113,113,.3); color:var(--red); padding:12px 16px; border-radius:10px; margin-bottom:16px; font-size:13px; }

  .layout { display:flex; min-height:100vh; }
  .sidebar { width:230px; background:var(--surface); border-right:1px solid var(--border); padding:24px 14px; display:flex; flex-direction:column; position:fixed; height:100vh; }
  .logo { font-size:17px; font-weight:700; padding:4px 10px 22px; }
  .logo span { color:var(--accent2); }
  .nav-item { display:flex; align-items:center; gap:9px; padding:9px 10px; border-radius:10px; font-size:13px; font-weight:500; color:var(--muted); text-decoration:none; transition:all .15s; }
  .nav-item:hover,.nav-item.active { background:var(--surface2); color:var(--text); }
  .logout { margin-top:auto; color:var(--red) !important; }

  .main { margin-left:230px; padding:36px; }
  .page-title { font-size:26px; font-weight:700; margin-bottom:4px; }
  .page-sub { color:var(--muted); font-size:13px; margin-bottom:32px; }

  .stats-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:32px; }
  .stat-card { background:var(--surface); border:1px solid var(--border); border-radius:16px; padding:22px; }
  .stat-label { font-size:12px; color:var(--muted); font-weight:500; margin-bottom:8px; text-transform:uppercase; letter-spacing:.4px; }
  .stat-value { font-size:32px; font-weight:700; letter-spacing:-1px; }
  .c-purple { color:var(--accent2); } .c-green { color:var(--green); } .c-yellow { color:var(--yellow); } .c-blue { color:var(--blue); }

  .kw-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:12px; margin-bottom:32px; }
  .kw-card { background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:18px; }
  .kw-word { font-size:16px; font-weight:700; color:var(--accent2); margin-bottom:6px; }
  .kw-count { font-size:28px; font-weight:700; color:var(--green); }
  .kw-label { font-size:11px; color:var(--muted); margin-top:2px; }
  .kw-link { font-size:11px; color:var(--muted); margin-top:8px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }

  .card { background:var(--surface); border:1px solid var(--border); border-radius:16px; overflow:hidden; margin-bottom:24px; }
  .card-header { padding:18px 22px; border-bottom:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; }
  .card-header h3 { font-size:15px; font-weight:600; }
  .badge { background:var(--accent); color:#fff; font-size:11px; font-weight:600; padding:3px 10px; border-radius:20px; }
  table { width:100%; border-collapse:collapse; }
  th { text-align:left; padding:11px 22px; font-size:11px; font-weight:600; color:var(--muted); text-transform:uppercase; letter-spacing:.5px; border-bottom:1px solid var(--border); }
  td { padding:13px 22px; font-size:13px; border-bottom:1px solid rgba(38,38,58,.5); }
  tr:last-child td { border-bottom:none; }
  tr:hover td { background:var(--surface2); }
  .tg-link { color:var(--accent2); text-decoration:none; }
  .kw-tag { background:rgba(139,92,246,.15); color:var(--accent2); padding:2px 8px; border-radius:6px; font-size:11px; font-weight:600; }

  .broadcast-card { background:var(--surface); border:1px solid var(--border); border-radius:16px; padding:28px; }
  .broadcast-card h3 { font-size:17px; font-weight:600; margin-bottom:6px; }
  .broadcast-card p { color:var(--muted); font-size:13px; margin-bottom:22px; }
  textarea { width:100%; background:var(--surface2); border:1px solid var(--border); color:var(--text); border-radius:12px; padding:14px; font-family:inherit; font-size:14px; resize:vertical; min-height:120px; margin-bottom:14px; transition:border-color .2s; }
  textarea:focus { outline:none; border-color:var(--accent); }
  .btn-send { background:var(--accent); color:#fff; border:none; border-radius:12px; padding:13px 24px; font-family:inherit; font-size:14px; font-weight:600; cursor:pointer; transition:opacity .2s; }
  .btn-send:hover { opacity:.85; }
  .alert-ok { background:rgba(52,211,153,.1); border:1px solid rgba(52,211,153,.3); color:var(--green); padding:13px 16px; border-radius:10px; margin-bottom:18px; font-size:13px; font-weight:500; }
  .alert-err { background:rgba(248,113,113,.1); border:1px solid rgba(248,113,113,.3); color:var(--red); padding:13px 16px; border-radius:10px; margin-bottom:18px; font-size:13px; font-weight:500; }
  .dot { width:7px; height:7px; background:var(--green); border-radius:50%; display:inline-block; margin-right:5px; }
</style>
</head>
<body>

{% if not session.get('logged_in') %}
<div class="login-wrap">
  <div class="login-card">
    <h1>🔐 Войти</h1>
    <p>Панель управления @ai_topkontentbot</p>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="POST" action="/login">
      <input type="password" name="password" placeholder="Пароль" autofocus>
      <button type="submit" class="btn-main">Войти →</button>
    </form>
  </div>
</div>

{% else %}
<div class="layout">
  <aside class="sidebar">
    <div class="logo">Lead<span>Bot</span></div>
    <a class="nav-item {% if page=='dashboard' %}active{% endif %}" href="/">📊 Дашборд</a>
    <a class="nav-item {% if page=='leads' %}active{% endif %}" href="/leads">👥 Контакты</a>
    <a class="nav-item {% if page=='keywords' %}active{% endif %}" href="/keywords">🔑 Кодовые слова</a>
    <a class="nav-item {% if page=='broadcast' %}active{% endif %}" href="/broadcast">📨 Рассылка</a>
    <a class="nav-item logout" href="/logout">🚪 Выйти</a>
  </aside>

  <main class="main">

  {% if page == 'dashboard' %}
    <div class="page-title">Дашборд</div>
    <div class="page-sub">Статистика по всем кодовым словам</div>

    <div class="stats-grid">
      <div class="stat-card"><div class="stat-label">Всего лидов</div><div class="stat-value c-purple">{{ stats.total }}</div></div>
      <div class="stat-card"><div class="stat-label">Сегодня</div><div class="stat-value c-green">{{ stats.today }}</div></div>
      <div class="stat-card"><div class="stat-label">Кодовых слов</div><div class="stat-value c-yellow">{{ stats.by_keyword|length }}</div></div>
      <div class="stat-card"><div class="stat-label">Рассылок</div><div class="stat-value c-blue">{{ stats.broadcasts }}</div></div>
    </div>

    {% if stats.by_keyword %}
    <div style="margin-bottom:8px; font-size:14px; font-weight:600; color:var(--muted)">🔑 ПО КОДОВЫМ СЛОВАМ</div>
    <div class="kw-grid" style="margin-bottom:32px;">
      {% for row in stats.by_keyword %}
      <div class="kw-card">
        <div class="kw-word">{{ row.keyword }}</div>
        <div class="kw-count">{{ row.cnt }}</div>
        <div class="kw-label">человек получили подарок</div>
      </div>
      {% endfor %}
    </div>
    {% endif %}

    <div class="card">
      <div class="card-header"><h3>Последние лиды</h3><span class="badge">{{ stats.total }} всего</span></div>
      <table>
        <thead><tr><th>Имя</th><th>Telegram</th><th>Email</th><th>Слово</th><th>Дата</th></tr></thead>
        <tbody>
          {% for lead in leads[:10] %}
          <tr>
            <td><span class="dot"></span>{{ lead.first_name or '—' }}</td>
            <td>{% if lead.username %}<a href="https://t.me/{{ lead.username }}" target="_blank" class="tg-link">@{{ lead.username }}</a>{% else %}<span style="color:var(--muted)">id{{ lead.telegram_id }}</span>{% endif %}</td>
            <td>{{ lead.email }}</td>
            <td><span class="kw-tag">{{ lead.keyword }}</span></td>
            <td style="color:var(--muted)">{{ lead.joined_at }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>

  {% elif page == 'leads' %}
    <div class="page-title">База контактов</div>
    <div class="page-sub">Все {{ leads|length }} лидов</div>
    <div class="card">
      <div class="card-header"><h3>Все контакты</h3><span class="badge">{{ leads|length }}</span></div>
      <table>
        <thead><tr><th>#</th><th>Имя</th><th>Telegram</th><th>Email</th><th>Слово</th><th>Дата</th></tr></thead>
        <tbody>
          {% for lead in leads %}
          <tr>
            <td style="color:var(--muted)">{{ loop.index }}</td>
            <td>{{ lead.first_name or '—' }}</td>
            <td>{% if lead.username %}<a href="https://t.me/{{ lead.username }}" target="_blank" class="tg-link">@{{ lead.username }}</a>{% else %}<span style="color:var(--muted)">id{{ lead.telegram_id }}</span>{% endif %}</td>
            <td>{{ lead.email }}</td>
            <td><span class="kw-tag">{{ lead.keyword }}</span></td>
            <td style="color:var(--muted)">{{ lead.joined_at }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>

  {% elif page == 'keywords' %}
    <div class="page-title">Кодовые слова</div>
    <div class="page-sub">Управляй словами прямо в Telegram через /addkeyword и /delkeyword</div>
    <div class="card">
      <div class="card-header"><h3>Активные слова</h3><span class="badge">{{ keywords|length }}</span></div>
      <table>
        <thead><tr><th>Слово</th><th>Подарок (ссылка)</th><th>Добавлено</th><th>Получили</th></tr></thead>
        <tbody>
          {% for kw in keywords %}
          <tr>
            <td><span class="kw-tag">{{ kw.word }}</span></td>
            <td><a href="{{ kw.gift_link }}" target="_blank" class="tg-link" style="font-size:12px">{{ kw.gift_link[:50] }}{% if kw.gift_link|length > 50 %}...{% endif %}</a></td>
            <td style="color:var(--muted)">{{ kw.created_at }}</td>
            <td style="color:var(--green); font-weight:600;">
              {% for row in stats.by_keyword %}{% if row.keyword == kw.word %}{{ row.cnt }}{% endif %}{% endfor %}
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>

  {% elif page == 'broadcast' %}
    <div class="page-title">Рассылка</div>
    <div class="page-sub">Отправить сообщение всем {{ stats.total }} людям в базе</div>
    {% if flash_ok %}<div class="alert-ok">{{ flash_ok }}</div>{% endif %}
    {% if flash_err %}<div class="alert-err">{{ flash_err }}</div>{% endif %}
    <div class="broadcast-card">
      <h3>📝 Новое сообщение</h3>
      <p>Поддерживается HTML: &lt;b&gt;жирный&lt;/b&gt;, &lt;i&gt;курсив&lt;/i&gt;, &lt;a href="..."&gt;ссылка&lt;/a&gt;</p>
      <form method="POST" action="/broadcast">
        <textarea name="message" placeholder="Привет! 👋 Вот что нового...">{{ prev_message or '' }}</textarea>
        <button type="submit" class="btn-send">📨 Отправить всем ({{ stats.total }})</button>
      </form>
    </div>
    {% if broadcasts %}
    <div style="margin-top:28px;">
      <div class="card">
        <div class="card-header"><h3>История рассылок</h3></div>
        <table>
          <thead><tr><th>Дата</th><th>Отправлено</th><th>Текст</th></tr></thead>
          <tbody>
            {% for b in broadcasts %}
            <tr>
              <td style="color:var(--muted);white-space:nowrap">{{ b.sent_at }}</td>
              <td style="color:var(--green);font-weight:600;">{{ b.sent_count }}</td>
              <td style="max-width:400px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ b.message }}</td>
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
    if not session.get("logged_in"): return redirect("/")
    conn = get_db()
    leads = conn.execute("SELECT * FROM leads ORDER BY joined_at DESC").fetchall()
    conn.close()
    return render_template_string(HTML, page="leads", session=session, leads=leads, stats=get_stats())

@app.route("/keywords")
def keywords_page():
    if not session.get("logged_in"): return redirect("/")
    conn = get_db()
    keywords = conn.execute("SELECT * FROM keywords WHERE is_active=1 ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template_string(HTML, page="keywords", session=session, keywords=keywords, stats=get_stats())

@app.route("/broadcast", methods=["GET", "POST"])
def broadcast_page():
    if not session.get("logged_in"): return redirect("/")
    conn = get_db()
    broadcasts = conn.execute("SELECT * FROM broadcasts ORDER BY sent_at DESC").fetchall()
    conn.close()
    flash_ok = flash_err = prev_message = None

    if request.method == "POST":
        message = request.form.get("message", "").strip()
        if not message:
            flash_err = "⚠️ Нельзя отправить пустое сообщение!"
        else:
            try:
                from broadcast_runner import send_broadcast_sync
                count = send_broadcast_sync(message)
                flash_ok = f"✅ Готово! Отправлено: {count} человек"
                conn = get_db()
                broadcasts = conn.execute("SELECT * FROM broadcasts ORDER BY sent_at DESC").fetchall()
                conn.close()
            except Exception as e:
                flash_err = f"Ошибка: {e}"
            prev_message = message

    return render_template_string(HTML, page="broadcast", session=session,
                                   stats=get_stats(), broadcasts=broadcasts,
                                   flash_ok=flash_ok, flash_err=flash_err, prev_message=prev_message)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
