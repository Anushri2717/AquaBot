from flask import Flask, request, jsonify, render_template
import sqlite3, json, ast, operator as op
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from io import BytesIO
import base64
import re

app = Flask(__name__, template_folder="templates")
with open("data/knowledge.json", "r", encoding="utf-8") as f:
    KNOWLEDGE = json.load(f)

with open("data/i18n_resources.json", "r", encoding="utf-8") as f:
    I18N = json.load(f)
ALLOWED_OPERATORS = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
                     ast.Div: op.truediv, ast.Pow: op.pow, ast.USub: op.neg, ast.Mod: op.mod}

def safe_eval(node):
    if isinstance(node, ast.Constant): return node.value
    if isinstance(node, ast.Num): return node.n
    if isinstance(node, ast.BinOp):
        func = ALLOWED_OPERATORS.get(type(node.op))
        return func(safe_eval(node.left), safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        func = ALLOWED_OPERATORS.get(type(node.op))
        return func(safe_eval(node.operand))
    raise ValueError("Unsupported expression")

def evaluate_math(expr):
    return safe_eval(ast.parse(expr, mode="eval").body)
DB_FILE = "groundwater.db"

def query_data(text):
    text_norm = text.lower().replace("-", "").replace(" ", "")
    years = 10
    match = re.search(r'last (\d+) years', text)
    if match:
        years = int(match.group(1))
    cutoff = (datetime.now() - timedelta(days=years*365)).date().isoformat()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT location FROM groundwater_data")
    wells = [r[0] for r in cursor.fetchall()]
    cursor.execute("SELECT DISTINCT measurement_type FROM groundwater_data")
    measurements = [r[0] for r in cursor.fetchall()]

    mentioned_wells = [w for w in wells if w.replace("-", "").replace(" ", "") in text_norm or text_norm in w.replace("-", "").replace(" ", "")] or wells
    mentioned_measurements = [m for m in measurements if m.replace("-", "").replace(" ", "") in text_norm or text_norm in m.replace("-", "").replace(" ", "")] or measurements

    results = []
    data_rows = []

    for well in mentioned_wells:
        for meas in mentioned_measurements:
            cursor.execute('''
                SELECT location, measurement_type, value, date
                FROM groundwater_data
                WHERE location=? AND measurement_type=? AND date>=?
                ORDER BY date
            ''', (well, meas, cutoff))
            rows = cursor.fetchall()
            for row in rows:
                results.append(f"{row[0]} {row[1]}: {row[2]} on {row[3]}")
            if rows:
                data_rows.append((well, meas, rows))
    conn.close()
    return results, data_rows, years

def generate_graph_base64(well, meas, rows):
    dates = [datetime.fromisoformat(r[3]) for r in rows]
    values = [r[2] for r in rows]
    if not dates:
        return None
    plt.figure(figsize=(8,4))
    plt.plot(dates, values, marker='o')
    plt.title(f"{meas} at {well}")
    plt.xlabel("Date")
    plt.ylabel("Value")
    plt.xticks(rotation=45)
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def handle_complex(text):
    text_lower = text.lower()
    for k,v in KNOWLEDGE.items():
        if k in text_lower:
            return v
    try:
        if all(c in '0123456789.+-*/()% ^' for c in text_lower):
            return str(evaluate_math(text_lower))
    except:
        pass
    results, data_rows, years = query_data(text)
    if not results:
        return "No matching data found. Mention well name or measurement type."
    graph_html = []
    for well, meas, rows in data_rows:
        img_b64 = generate_graph_base64(well, meas, rows)
        if img_b64:
            graph_html.append(f'<img src="data:image/png;base64,{img_b64}" style="max-width:100%; margin-top:10px;">')

    return "<br>".join(results + graph_html)
@app.route('/')
def index():
    return render_template("index.html", i18n=I18N)

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json() or {}
    text = data.get("message", "")
    answer = handle_complex(text)
    return jsonify(response=answer)

if __name__ == "__main__":
    print("Chatbot running at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
