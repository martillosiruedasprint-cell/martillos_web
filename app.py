from flask import Flask, render_template, request, session, redirect, jsonify, url_for
import sqlite3
from datetime import datetime
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'martillos_seguridad_alta_2026')

DB_PATH = 'database.db'
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Asegurar que la carpeta de subidas exista
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tabla de Usuarios
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL, -- 'pasajero', 'conductor', 'admin'
            saldo REAL DEFAULT 0.0
        )
    ''')
    
    # Tabla de Viajes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS viajes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pasajero_id INTEGER NOT NULL,
            origen TEXT NOT NULL,
            destino TEXT NOT NULL,
            fecha TEXT NOT NULL,
            estado TEXT DEFAULT 'Pendiente',
            FOREIGN KEY(pasajero_id) REFERENCES usuarios(id)
        )
    ''')
    
    # Tabla de Configuración Global del Sistema (Tarifas y Multimedia)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS configuracion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tasa_comision REAL DEFAULT 9.0, -- Entre 6% y 9%
            imagen_principal TEXT DEFAULT '',
            video_animacion TEXT DEFAULT ''
        )
    ''')
    
    # Insertar configuración inicial por defecto si está vacía
    cursor.execute("SELECT COUNT(*) FROM configuracion")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO configuracion (tasa_comision, imagen_principal, video_animacion) VALUES (9.0, '', '')")

    # Crear Administrador por defecto si no existe
    cursor.execute("SELECT * FROM usuarios WHERE email = 'admin@martillos.com'")
    if not cursor.fetchone():
        hashed_pw = generate_password_hash('admin123')
        cursor.execute("INSERT INTO usuarios (nombre, email, password, rol) VALUES (?, ?, ?, ?)",
                       ('Administrador', 'admin@martillos.com', hashed_pw, 'admin'))
                       
    conn.commit()
    conn.close()

init_db()

# Helper para obtener configuración
def get_config():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT tasa_comision, imagen_principal, video_animacion FROM configuracion WHERE id = 1")
    res = cursor.fetchone()
    conn.close()
    return {"tasa": res[0], "imagen": res[1], "video": res[2]}

# ==================== RUTAS DE AUTENTICACIÓN ====================

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect('/login')
    if session.get('rol') == 'conductor':
        return redirect('/conductor')
    elif session.get('rol') == 'admin':
        return redirect('/admin_historial')
    return redirect('/pasajero')

@app.route('/login', methods=['GET', 'POST'])
def login():
    config = get_config()
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre, email, password, rol, saldo FROM usuarios WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            session['nombre'] = user[1]
            session['email'] = user[2]
            session['rol'] = user[4]
            session['saldo'] = user[5]
            return redirect('/')
        return "Correo o contraseña incorrectos. <a href='/login'>Volver</a>"
        
    return render_template('login.html', config=config)

@app.route('/registro_pasajero', methods=['GET', 'POST'])
def registro_pasajero():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        email = request.form.get('email')
        password = request.form.get('password')
        
        hashed_pw = generate_password_hash(password)
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO usuarios (nombre, email, password, rol, saldo) VALUES (?, ?, ?, ?, ?)",
                           (nombre, email, hashed_pw, 'pasajero', 5.0))
            conn.commit()
            conn.close()
            return "Registro exitoso. <a href='/login'>Inicia sesión aquí</a>"
        except sqlite3.IntegrityError:
            return "El correo ya está registrado. <a href='/registro_pasajero'>Intentar de nuevo</a>"
            
    return render_template('registro_pasajero.html')

# ==================== CONTROLES EXCLUSIVOS DEL ADMINISTRADOR ====================

@app.route('/admin_historial')
def admin_historial():
    if session.get('rol') != 'admin': return redirect('/')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Obtener viajes
    cursor.execute('''
        SELECT viajes.id, usuarios.nombre, viajes.origen, viajes.destino, viajes.fecha, viajes.estado 
        FROM viajes JOIN usuarios ON viajes.pasajero_id = usuarios.id ORDER BY viajes.id DESC
    ''')
    viajes = cursor.fetchall()
    
    # 2. Monitorear cantidad de usuarios registrados por Rol
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE rol = 'pasajero'")
    total_pasajeros = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE rol = 'conductor'")
    total_conductores = cursor.fetchone()[0]
    
    conn.close()
    config = get_config()
    
    return render_template('admin_historial.html', viajes=viajes, total_pasajeros=total_pasajeros, total_conductores=total_conductores, config=config)

@app.route('/admin/crear_conductor', methods=['POST'])
def crear_conductor():
    if session.get('rol') != 'admin': return redirect('/')
    nombre = request.form.get('nombre')
    email = request.form.get('email')
    password = request.form.get('password')
    
    hashed_pw = generate_password_hash(password)
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO usuarios (nombre, email, password, rol) VALUES (?, ?, ?, ?)", (nombre, email, hashed_pw, 'conductor'))
        conn.commit()
        conn.close()
        return redirect('/admin_historial?status=conductor_creado')
    except sqlite3.IntegrityError:
        return "Error: El correo ya existe en el sistema."

@app.route('/admin/actualizar_tasa', methods=['POST'])
def actualizar_tasa():
    if session.get('rol') != 'admin': return redirect('/')
    tasa = float(request.form.get('tasa'))
    
    # Forzar el límite estricto entre 6% y 9%
    if tasa < 6.0: tasa = 6.0
    if tasa > 9.0: tasa = 9.0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE configuracion SET tasa_comision = ? WHERE id = 1", (tasa,))
    conn.commit()
    conn.close()
    return redirect('/admin_historial?status=tasa_actualizada')

@app.route('/admin/subir_multimedia', methods=['POST'])
def subir_multimedia():
    if session.get('rol') != 'admin': return redirect('/')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if 'imagen' in request.files and request.files['imagen'].filename != '':
        file = request.files['imagen']
        filename = secure_filename("logo_principal_" + file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        cursor.execute("UPDATE configuracion SET imagen_principal = ? WHERE id = 1", (filename,))
        
    if 'video' in request.files and request.files['video'].filename != '':
        file = request.files['video']
        filename = secure_filename("video_intro_" + file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        cursor.execute("UPDATE configuracion SET video_animacion = ? WHERE id = 1", (filename,))
        
    conn.commit()
    conn.close()
    return redirect('/admin_historial?status=multimedia_actualizada')

# ==================== OTRAS RUTAS OBLIGATORIAS ====================

@app.route('/pasajero')
def pasajero():
    if session.get('rol') != 'pasajero': return redirect('/')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT saldo FROM usuarios WHERE id = ?", (session['user_id'],))
    session['saldo'] = cursor.fetchone()[0]
    conn.close()
    return render_template('pasajero.html')

@app.route('/conductor')
def conductor():
    if session.get('rol') != 'conductor': return redirect('/')
    return render_template('conductor.html', driver_name=session.get('nombre'))

@app.route('/solicitar_viaje', methods=['POST'])
def solicitar_viaje():
    if session.get('rol') != 'pasajero': return redirect('/')
    origen = request.form.get('origen')
    destino = request.form.get('destino')
    fecha = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if origen and destino:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO viajes (pasajero_id, origen, destino, fecha) VALUES (?, ?, ?, ?)', (session['user_id'], origen, destino, fecha))
        conn.commit()
        conn.close()
        return redirect('/pasajero?status=success')
    return redirect('/pasajero?status=error')

@app.route('/api/check_ride')
def check_ride():
    if session.get('rol') != 'conductor': return jsonify({"status": "unauthorized"})
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT viajes.id, usuarios.nombre, viajes.origen, viajes.destino FROM viajes 
        JOIN usuarios ON viajes.pasajero_id = usuarios.id WHERE viajes.estado = 'Pendiente' ORDER BY viajes.id DESC LIMIT 1
    ''')
    viaje = cursor.fetchone()
    conn.close()
    if viaje:
        return jsonify({"status": "found", "ride_id": viaje[0], "pasajero": viaje[1], "origen": viaje[2], "destino": viaje[3]})
    return jsonify({"status": "searching"})

@app.route('/api/accept_ride', methods=['POST'])
def accept_ride():
    if session.get('rol') != 'conductor': return jsonify({"success": False})
    data = request.get_json()
    ride_id = data.get('ride_id')
    if ride_id:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE viajes SET estado = 'Aceptado' WHERE id = ?", (ride_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    app.run()
