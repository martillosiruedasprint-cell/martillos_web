from flask import Flask, render_template, request, session, redirect, jsonify
import sqlite3
from datetime import datetime
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'martillos_seguridad_alta_2026')

DB_PATH = 'database.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Tabla de Usuarios (Pasajeros, Conductores y Admin)
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
    
    # Crear Administrador por defecto si no existe (Usuario: admin@martillos.com / Clave: admin123)
    cursor.execute("SELECT * FROM usuarios WHERE email = 'admin@martillos.com'")
    if not cursor.fetchone():
        hashed_pw = generate_password_hash('admin123')
        cursor.execute("INSERT INTO usuarios (nombre, email, password, rol) VALUES (?, ?, ?, ?)",
                       ('Administrador', 'admin@martillos.com', hashed_pw, 'admin'))
                       
    conn.commit()
    conn.close()

init_db()

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
    return '''
        <body style="background:#000; color:#fff; font-family:sans-serif; display:flex; justify-content:center; align-items:center; height:100vh; margin:0;">
            <form method="POST" style="background:#111; padding:30px; border-radius:10px; border:1px solid #ffeb3b; width:300px;">
                <h2 style="color:#ffeb3b; text-align:center; margin-top:0;">Iniciar Sesión</h2>
                Correo:<br><input type="email" name="email" required style="width:100%; padding:8px; margin:8px 0; background:#222; border:1px solid #444; color:#fff;"><br>
                Contraseña:<br><input type="password" name="password" required style="width:100%; padding:8px; margin:8px 0; background:#222; border:1px solid #444; color:#fff;"><br><br>
                <button type="submit" style="width:100%; padding:10px; background:#ffeb3b; color:#000; border:none; font-weight:bold; cursor:pointer;">ENTRAR</button>
                <p style="font-size:12px; text-align:center; margin-top:15px;">¿Eres pasajero nuevo? <a href="/registro_pasajero" style="color:#ffeb3b;">Regístrate aquí</a></p>
            </form>
        </body>
    '''

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
                           (nombre, email, hashed_pw, 'pasajero', 5.0)) # Le regalamos $5 de saldo inicial para probar
            conn.commit()
            conn.close()
            return "Registro exitoso. <a href='/login'>Inicia sesión aquí</a>"
        except sqlite3.IntegrityError:
            return "El correo ya está registrado. <a href='/registro_pasajero'>Intentar de nuevo</a>"
            
    return '''
        <body style="background:#000; color:#fff; font-family:sans-serif; display:flex; justify-content:center; align-items:center; height:100vh; margin:0;">
            <form method="POST" style="background:#111; padding:30px; border-radius:10px; border:1px solid #ffeb3b; width:300px;">
                <h2 style="color:#ffeb3b; text-align:center; margin-top:0;">Registro de Pasajero</h2>
                Nombre Completo:<br><input type="text" name="nombre" required style="width:100%; padding:8px; margin:8px 0; background:#222; border:1px solid #444; color:#fff;"><br>
                Correo Electrónico:<br><input type="email" name="email" required style="width:100%; padding:8px; margin:8px 0; background:#222; border:1px solid #444; color:#fff;"><br>
                Contraseña:<br><input type="password" name="password" required style="width:100%; padding:8px; margin:8px 0; background:#222; border:1px solid #444; color:#fff;"><br><br>
                <button type="submit" style="width:100%; padding:10px; background:#ffeb3b; color:#000; border:none; font-weight:bold; cursor:pointer;">REGISTRARME</button>
            </form>
        </body>
    '''

# ==================== CREACIÓN DE CONDUCTORES DESDE EL ADMIN ====================

@app.route('/admin/crear_conductor', methods=['POST'])
def crear_conductor():
    if session.get('rol') != 'admin':
        return jsonify({"success": False, "error": "No autorizado"}), 403
        
    nombre = request.form.get('nombre')
    email = request.form.get('email')
    password = request.form.get('password')
    
    hashed_pw = generate_password_hash(password)
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO usuarios (nombre, email, password, rol) VALUES (?, ?, ?, ?)",
                       (nombre, email, hashed_pw, 'conductor'))
        conn.commit()
        conn.close()
        return redirect('/admin_historial?status=conductor_creado')
    except sqlite3.IntegrityError:
        return "Error: El correo ya existe."

# ==================== VISTAS DE INTERFAZ ====================

@app.route('/pasajero')
def pasajero():
    if session.get('rol') != 'pasajero': return redirect('/')
    # Actualizar saldo en tiempo real desde la BD
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

@app.route('/admin_historial')
def admin_historial():
    if session.get('rol') != 'admin': return redirect('/')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT viajes.id, usuarios.nombre, viajes.origen, viajes.destino, viajes.fecha, viajes.estado 
        FROM viajes 
        JOIN usuarios ON viajes.pasajero_id = usuarios.id 
        ORDER BY viajes.id DESC
    ''')
    viajes = cursor.fetchall()
    conn.close()
    return render_template('admin_historial.html', viajes=viajes)

@app.route('/solicitar_viaje', methods=['POST'])
def solicitar_viaje():
    if session.get('rol') != 'pasajero': return redirect('/')
    origen = request.form.get('origen')
    destino = request.form.get('destino')
    fecha = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if origen and destino:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO viajes (pasajero_id, origen, destino, fecha) VALUES (?, ?, ?, ?)',
                       (session['user_id'], origen, destino, fecha))
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
        SELECT viajes.id, usuarios.nombre, viajes.origen, viajes.destino 
        FROM viajes 
        JOIN usuarios ON viajes.pasajero_id = usuarios.id 
        WHERE viajes.estado = 'Pendiente' ORDER BY viajes.id DESC LIMIT 1
    ''')
    viaje = cursor.fetchone()
    conn.close()
    
    if viaje:
        return jsonify({
            "status": "found",
            "ride_id": viaje[0],
            "pasajero": viaje[1],
            "origen": viaje[2],
            "destino": viaje[3]
        })
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
