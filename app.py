
from flask import Flask, request, jsonify, render_template, send_from_directory, Response
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os, csv, datetime, threading

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(APP_ROOT, 'uploads')
DATA_DIR = os.path.join(APP_ROOT, 'data')
CSV_PATH = os.path.join(DATA_DIR, 'submissions.csv')
ALLOWED_EXT = {'.png', '.jpg', '.jpeg', '.webp'}

REG_OPEN  = datetime.datetime(2025, 10, 2, 0, 0, 0)
REG_CLOSE = datetime.datetime(2025, 10, 14, 23, 59, 59)
EVENT_DAY = datetime.datetime(2025, 10, 17, 10, 0, 0)

MAX_TEAM_MEMBERS = 5
SERVICE_EMAIL = "nancy.lazaro@lacostena.com.mx"
SERVICE_EXTS = "5552, 5580, 5581, 5582 y 5583"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

lock = threading.Lock()

app = Flask(
    __name__,
    template_folder=os.path.join(APP_ROOT, 'templates'),
    static_folder=os.path.join(APP_ROOT, 'static')
)
CORS(app)

CATEGORIES = ['creatividad','mensaje','equipo']

def allowed_file(filename: str) -> bool:
    ext = os.path.splitext(filename.lower())[1]
    return ext in ALLOWED_EXT

def ensure_csv():
    if not os.path.isfile(CSV_PATH):
        with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['ts','equipo','participantes','departamento','hashtag','lema','dato','filename','ip'] + [f'votes_{c}' for c in CATEGORIES]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

def read_rows():
    ensure_csv()
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def write_rows(rows):
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['ts','equipo','participantes','hashtag','lema','dato','filename','ip'] + [f'votes_{c}' for c in CATEGORIES]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

def total_votes(row):
    return sum(int(row.get(f'votes_{c}', '0') or 0) for c in CATEGORIES)

def reg_state():
    now = datetime.datetime.now()
    if now < REG_OPEN:
        return 'pre'
    elif now > REG_CLOSE:
        return 'closed'
    else:
        return 'open'

@app.route('/')
def home():
    return render_template('index.html', categories=CATEGORIES)

@app.get('/bases')
def bases():
    return render_template('bases.html', service_email=SERVICE_EMAIL, service_exts=SERVICE_EXTS)

@app.get('/sopa')
def sopa():
    return render_template('sopa.html')

@app.get('/api/meta')
def api_meta():
    return jsonify({
        'ok': True,
        'state': reg_state(),
        'open': REG_OPEN.isoformat(),
        'close': REG_CLOSE.isoformat(),
        'event': EVENT_DAY.isoformat(),
        'max_team': MAX_TEAM_MEMBERS,
        'service_email': SERVICE_EMAIL,
        'service_exts': SERVICE_EXTS,
    })

@app.get('/api/list')
def api_list():
    rows = read_rows()
    for r in rows:
        r['total'] = str(total_votes(r))
    rows.sort(key=lambda r: r['ts'], reverse=True)
    top = sorted(rows, key=lambda r: int(r['total']), reverse=True)[:5]
    return jsonify({'ok': True, 'items': rows, 'top5': top, 'categories': CATEGORIES})

@app.post('/api/submissions')
def submit():
    if reg_state() != 'open':
        return jsonify({'ok': False, 'error': 'Recepción cerrada en este momento. Envía tu foto por email a %s.' % SERVICE_EMAIL}), 403

    equipo = (request.form.get('equipo') or 'Equipo Rosa').strip()
    participantes = (request.form.get('participantes') or '').strip()
    hashtag = (request.form.get('hashtag') or '#OctubreRosa').strip()
    lema = (request.form.get('lema') or '').strip()
    departamento = (request.form.get('departamento') or '').strip()
    dato = (request.form.get('dato') or '').strip()

    if participantes:
        members = [p.strip() for p in participantes.split(',') if p.strip()]
        if len(members) > MAX_TEAM_MEMBERS:
            return jsonify({'ok': False, 'error': f'Max. {MAX_TEAM_MEMBERS} participantes por equipo.'}), 400

    file = request.files.get('poster') or request.files.get('photo')
    if not file or file.filename == '':
        return jsonify({'ok': False, 'error': 'No se recibió archivo (poster/photo)'}), 400

    filename = secure_filename(file.filename)
    if not allowed_file(filename):
        return jsonify({'ok': False, 'error': 'Formato no permitido. Usa PNG/JPG/JPEG/WEBP'}), 400

    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    _, ext = os.path.splitext(filename)
    safe_team = ''.join(c for c in equipo if c.isalnum() or c in ('-','_')).strip('_') or 'EquipoRosa'
    server_filename = f"{ts}_{safe_team}{ext.lower()}"
    file.save(os.path.join(UPLOAD_DIR, server_filename))

    with lock:
        rows = read_rows()
        base = {'ts': ts, 'equipo': equipo, 'participantes': participantes, 'hashtag': hashtag,
                'lema': lema, 'dato': dato, 'filename': server_filename, 'ip': request.remote_addr or '-'}
        for c in CATEGORIES: base[f'votes_{c}'] = '0'
        rows.append(base); write_rows(rows)

    return jsonify({'ok': True, 'filename': server_filename})

@app.post('/api/vote')
def api_vote():
    filename = request.form.get('filename')
    category = (request.form.get('category') or '').strip().lower()
    if not filename or category not in CATEGORIES:
        return jsonify({'ok': False, 'error': 'Parámetros inválidos'}), 400

    with lock:
        rows = read_rows()
        for r in rows:
            if r['filename'] == filename:
                key = f'votes_{category}'
                r[key] = str(int(r.get(key, '0') or 0) + 1)
                write_rows(rows)
                return jsonify({'ok': True, 'votes': {c: int(r.get(f'votes_{c}',0)) for c in CATEGORIES}, 'total': total_votes(r)})
        return jsonify({'ok': False, 'error': 'No encontrado'}), 404

@app.get('/uploads/<path:filename>')
def serve_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)

@app.get('/admin')
def admin_list():
    rows = read_rows()
    rows.sort(key=lambda r: r['ts'], reverse=True)
    def td(x): return f"<td>{x}</td>"
    html = ['''<!doctype html><meta charset="utf-8"><title>Envíos</title>
    <style>body{font-family:system-ui;margin:24px} table{border-collapse:collapse;width:100%} th,td{border:1px solid #eee;padding:8px} img{height:100px;border-radius:8px}</style>
    <h1>Envíos</h1>
    <p><a href="/api/export_top" style="font-weight:800">⬇️ Exportar Top 5 (CSV)</a> · <a href="/api/export_all" style="font-weight:800">⬇️ Exportar todo (CSV)</a></p>
    <table><thead><tr>
    <th>Fecha</th><th>Equipo</th><th>Participantes</th><th>Hashtag</th><th>Lema</th><th>Dato</th>
    <th>Creatividad</th><th>Mensaje</th><th>Equipo</th><th>Total</th><th>Imagen</th></tr></thead><tbody>''']
    for r in rows:
        img = f"<a href='/uploads/{r['filename']}' target='_blank'><img src='/uploads/{r['filename']}' loading='lazy'></a>"
        total = total_votes(r)
        html.append(f"<tr>{td(r['ts'])}{td(r['equipo'])}{td(r.get('participantes',''))}{td(r['hashtag'])}{td(r['lema'])}{td(r['dato'])}{td(r.get('votes_creatividad','0'))}{td(r.get('votes_mensaje','0'))}{td(r.get('votes_equipo','0'))}{td(total)}{td(img)}</tr>")
    html.append('</tbody></table>')
    return ''.join(html)

@app.get('/api/export_top')
def export_top():
    rows = read_rows()
    rows = sorted(rows, key=lambda r: total_votes(r), reverse=True)[:5]
    output = ['equipo,participantes,hashtag,lema,dato,filename,creatividad,mensaje,equipo,total']
    for r in rows:
        total = total_votes(r)
        output.append(','.join([
            f'"{r.get("equipo","")}"',
            f'"{r.get("participantes","")}"',
            f'"{r.get("hashtag","")}"',
            f'"{r.get("lema","")}"',
            f'"{r.get("dato","")}"',
            f'"{r.get("filename","")}"',
            str(r.get('votes_creatividad','0') or 0),
            str(r.get('votes_mensaje','0') or 0),
            str(r.get('votes_equipo','0') or 0),
            str(total)
        ]))
    csv_data = '\n'.join(output)
    return Response(csv_data, mimetype='text/csv', headers={'Content-Disposition':'attachment; filename=top5.csv'})

@app.get('/api/export_all')
def export_all():
    rows = read_rows()
    output = ['ts,equipo,participantes,hashtag,lema,dato,filename,ip,creatividad,mensaje,equipo,total']
    for r in rows:
        total = total_votes(r)
        output.append(','.join([
            f'"{r.get("ts","")}"',
            f'"{r.get("equipo","")}"',
            f'"{r.get("participantes","")}"',
            f'"{r.get("hashtag","")}"',
            f'"{r.get("lema","")}"',
            f'"{r.get("dato","")}"',
            f'"{r.get("filename","")}"',
            f'"{r.get("ip","")}"',
            str(r.get('votes_creatividad','0') or 0),
            str(r.get('votes_mensaje','0') or 0),
            str(r.get('votes_equipo','0') or 0),
            str(total)
        ]))
    csv_data = '\n'.join(output)
    return Response(csv_data, mimetype='text/csv', headers={'Content-Disposition':'attachment; filename=submissions.csv'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)


# Exportación CSV estable
@app.get('/export.csv')
def export_csv():
    import csv
    from io import StringIO
    PIN = os.environ.get('ADMIN_PIN', 'serviciomedico')
    if request.args.get('pin') != PIN:
        return Response('No autorizado. Agrega ?pin=TU_PIN', status=401)
    rows = read_rows()
    headers = ['ts','equipo','participantes','departamento','hashtag','lema','dato','filename','ip'] + [f'votes_{c}' for c in CATEGORIES] + ['total']
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction='ignore')
    writer.writeheader()
    for r in rows:
        writer.writerow({h: r.get(h, '') for h in headers})
    return Response(buf.getvalue(), mimetype='text/csv', headers={'Content-Disposition':'attachment; filename=listado.csv'})
