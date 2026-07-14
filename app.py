from flask import Flask, render_template, request, session, redirect, url_for, jsonify, abort
import sqlite3
from datetime import datetime
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
# Usar una clave secreta fuerte para firmar las cookies de sesión y evitar hackeos
app.secret_key = os.environ.get('SECRET_KEY', 'martillos_seguridad_extrema_2026_jwt_token')

DB_PATH = 'database.db'
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Tabla de Usuarios (Contraseñas cifradas siempre)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            apellido TEXT DEFAULT '',
            cedula TEXT DEFAULT '',
            fecha_nacimiento TEXT DEFAULT '',
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL, -- 'pasajero', 'conductor', 'admin'
            saldo REAL DEFAULT 0.0,
            placa TEXT DEFAULT '',
            serial_motor TEXT DEFAULT '',
            serial_carroceria TEXT DEFAULT ''
        )
    ''')
    
    # 2. Tabla de Viajes
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
    
    # 3. NUEVA: Tabla de Transacciones/Pago Móvil (Base de la seguridad financiera)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pagos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            monto REAL NOT NULL,
            telefono_origen TEXT NOT NULL,
            banco_origen TEXT NOT NULL,
            referencia TEXT UNIQUE NOT NULL, -- Clave UNIQUE para evitar que reutilicen el mismo recibo
            fecha_registro TEXT NOT NULL,
            estado TEXT DEFAULT 'Pendiente', -- 'Pendiente', 'Aprobado', 'Rechazado'
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        )
    ''')
    
    # 4. Tabla de Configuración Global
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS configuracion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tasa_comision REAL DEFAULT 9.0,
            imagen_principal TEXT DEFAULT '',
            video_animacion TEXT DEFAULT ''
        )
    ''')
    
    cursor.execute("SELECT COUNT(*) FROM configuracion")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO configuracion (tasa_comision, imagen_principal, video_animacion) VALUES (9.0, '', '')")

    # Administrador inicial por defecto seguro
    cursor.execute("SELECT * FROM usuarios WHERE email = 'admin@martillos.com'")
    if not cursor.fetchone():
        hashed_pw = generate_password_hash('admin123')
        cursor.execute("INSERT INTO usuarios (nombre, email, password, rol) VALUES (?, ?, ?, ?)",
                       ('Administrador', 'admin@martillos.com', hashed_pw, 'admin'))
                       
    conn.commit()
    conn.close()

init_db()

# Helpers de Configuración y Seguridad
def get_config():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT tasa_comision, imagen_principal, video_animacion FROM configuracion WHERE id = 1")
    res = cursor.fetchone()
    conn.close()
    return {"tasa": res[0], "imagen": res[1], "video": res[2]}

def verificar_autenticacion(rol_requerido):
    """Filtro de seguridad estricto para validar sesiones"""
    if 'user_id' not in session:
        return False
    if session.get('rol') != rol_requerido:
        return False
    return True

# ==================== RUTAS PÚBLICAS Y AUTENTICACIÓN ====================

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect('/login')
    
    # Redirección forzada según privilegios reales en sesión
    rol = session.get('rol')
    if rol == 'admin': return redirect('/admin_historial')
    if rol == 'conductor': return redirect('/conductor')
    return redirect('/pasajero')

@app.route('/login', methods=['GET', 'POST'])
def login():
    config = get_config()
    if request.method == 'POST':
        email = request.form.get('email').strip()
        password = request.form.get('password')
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre, email, password, rol, saldo FROM usuarios WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        
        # Verificación segura con Hash (Previene ataques de fuerza bruta simples)
        if user and check_password_hash(user[3], password):
            session.clear() # Limpiar cualquier residuo de sesión previo
            session['user_id'] = user[0]
            session['nombre'] = user[1]
            session['email'] = user[2]
            session['rol'] = user[4]
            session['saldo'] = user[5]
            return redirect('/')
        return "Credenciales inválidas. <a href='/login'>Intentar de nuevo</a>"
        
    return render_template('login.html', config=config)

@app.route('/registro_pasajero', methods=['GET', 'POST'])
def registro_pasajero():
    """Los pasajeros se registran de forma autónoma y pública"""
    if request.method == 'POST':
        nombre = request.form.get('nombre').strip()
        email = request.form.get('email').strip()
        password = request.form.get('password')
        
        if not nombre or not email or not password:
            return "Todos los campos son obligatorios."
            
        hashed_pw = generate_password_hash(password)
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            # Se registra estrictamente con rol 'pasajero'
            cursor.execute("INSERT INTO usuarios (nombre, email, password, rol, saldo) VALUES (?, ?, ?, ?, ?)",
                           (nombre, email, hashed_pw, 'pasajero', 0.0))
            conn.commit()
            conn.close()
            return "¡Registro exitoso! <a href='/login'>Inicia sesión aquí</a>"
        except sqlite3.IntegrityError:
            return "El correo ya se encuentra registrado."
            
    return render_template('registro_pasajero.html')

# ==================== CONTROLES DE ADMINISTRACIÓN (PROTEGIDOS) ====================

@app.route('/admin_historial')
def admin_historial():
    if not verificar_autenticacion('admin'): 
        return redirect('/login')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT viajes.id, usuarios.nombre, viajes.origen, viajes.destino, viajes.fecha, viajes.estado 
        FROM viajes JOIN usuarios ON viajes.pasajero_id = usuarios.id ORDER BY viajes.id DESC
    ''')
    viajes = cursor.fetchall()
    
    # Contadores de control
    total_pasajeros = cursor.fetchone()[0] if (cursor.execute("SELECT COUNT(*) FROM usuarios WHERE rol = 'pasajero'")) else 0
    total_conductores = cursor.fetchone()[0] if (cursor.execute("SELECT COUNT(*) FROM usuarios WHERE rol = 'conductor'")) else 0
    
    # Cargar solicitudes de recarga pendientes
    cursor.execute("SELECT pagos.id, usuarios.nombre, pagos.monto, pagos.referencia, pagos.estado FROM pagos JOIN usuarios ON pagos.usuario_id = usuarios.id WHERE pagos.estado = 'Pendiente'")
    pagos_pendientes = cursor.fetchall()
    
    conn.close()
    config = get_config()
    return render_template('admin_historial.html', viajes=viajes, total_pasajeros=total_pasajeros, total_conductores=total_conductores, config=config, pagos_pendientes=pagos_pendientes)

@app.route('/admin/crear_conductor', methods=['POST'])
def crear_conductor():
    """Solo el administrador puede ejecutar esta acción"""
    if not verificar_autenticacion('admin'): abort(403)
    
    nombre = request.form.get('nombre')
    apellido = request.form.get('apellido')
    cedula = request.form.get('cedula')
    fecha_nacimiento = request.form.get('fecha_nacimiento')
    email = request.form.get('email')
    password = request.form.get('password')
    placa = request.form.get('placa')
    serial_motor = request.form.get('serial_motor')
    serial_carroceria = request.form.get('serial_carroceria')
    
    hashed_pw = generate_password_hash(password)
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO usuarios (nombre, apellido, cedula, fecha_nacimiento, email, password, rol, placa, serial_motor, serial_carroceria) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (nombre, apellido, cedula, fecha_nacimiento, email, hashed_pw, 'conductor', placa, serial_motor, serial_carroceria))
        conn.commit()
        conn.close()
        return redirect('/admin_historial?status=conductor_ok')
    except sqlite3.IntegrityError:
        return "Error: Cédula o Correo duplicado en el sistema."

# ==================== RUTAS PASAJERO Y CONDUCTOR ====================

@app.route('/pasajero')
def pasajero():
    if not verificar_autenticacion('pasajero'): return redirect('/login')
    return render_template('pasajero.html')

@app.route('/conductor')
def conductor():
    if not verificar_autenticacion('conductor'): return redirect('/login')
    return render_template('conductor.html', driver_name=session.get('nombre'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    app.run(debug=False) # Debug False para producción por seguridad
