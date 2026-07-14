import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
# Usamos una clave secreta segura para el manejo de sesiones en producción
app.secret_key = os.environ.get('SECRET_KEY', 'martillos_ruedas_secreto_2026')

DB_NAME = "database.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# ==========================================
# INICIALIZACIÓN DE LA BASE DE DATOS
# ==========================================
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabla de Usuarios (Administradores, Pasajeros, Conductores)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            apellido TEXT NOT NULL,
            cedula TEXT UNIQUE NOT NULL,
            fecha_nacimiento TEXT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL, -- 'admin', 'pasajero', 'conductor'
            placa TEXT,        -- Solo para conductores
            serial_motor TEXT, -- Solo para conductores
            serial_carroceria TEXT -- Solo para conductores
        )
    ''')
    
    # Tabla de Solicitudes de Viajes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS viajes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pasajero_id INTEGER,
            origen TEXT NOT NULL,
            destino TEXT NOT NULL,
            monto REAL DEFAULT 700.0,
            fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            estado TEXT DEFAULT 'Pendiente', -- 'Pendiente', 'Aceptado', 'Completado'
            conductor_id INTEGER,
            FOREIGN KEY(pasajero_id) REFERENCES usuarios(id),
            FOREIGN KEY(conductor_id) REFERENCES usuarios(id)
        )
    ''')
    
    # Insertar administrador por defecto si no existe ninguno
    cursor.execute("SELECT * FROM usuarios WHERE rol = 'admin'")
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO usuarios (nombre, apellido, cedula, email, password, rol)
            VALUES ('Admin', 'Martillos', 'V-00000000', 'admin@martillos.com', 'admin123', 'admin')
        ''')
        
    conn.commit()
    conn.close()

init_db()

# ==========================================
# MIDDLEWARE / CONTROL DE ACCESO (PROTECCIÓN)
# ==========================================
@app.before_request
def verificar_sesion():
    # Rutas públicas que no requieren autenticación
    rutas_publicas = ['login', 'registro', 'static']
    
    # Si la petición va a una ruta pública, la dejamos pasar
    if request.endpoint in rutas_publicas or not request.endpoint:
        return

    # Si no hay sesión activa, redirigir obligatoriamente al Login
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

# ==========================================
# RUTAS DE AUTENTICACIÓN
# ==========================================

@app.route('/')
def index():
    # Redirección inteligente según el rol que tenga guardado en sesión
    if 'usuario_id' in session:
        rol = session.get('rol')
        if rol == 'admin':
            return redirect(url_for('admin_historial'))
        elif rol == 'conductor':
            return redirect(url_for('conductor_panel'))
        elif rol == 'pasajero':
            return redirect(url_for('pasajero_panel'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password'].strip()
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM usuarios WHERE email = ? AND password = ?', (email, password)).fetchone()
        conn.close()
        
        if user:
            session['usuario_id'] = user['id']
            session['nombre'] = user['nombre']
            session['rol'] = user['rol']
            
            # Redireccionar según rol tras un inicio de sesión exitoso
            if user['rol'] == 'admin':
                return redirect(url_for('admin_historial'))
            elif user['rol'] == 'conductor':
                return redirect(url_for('conductor_panel'))
            else:
                return redirect(url_for('pasajero_panel'))
        else:
            flash("Credenciales incorrectas. Inténtalo de nuevo.")
            return render_template('login.html', error="Correo o contraseña incorrectos.")
            
    return render_template('login.html')


@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        apellido = request.form['apellido'].strip()
        cedula = request.form['cedula'].strip()
        email = request.form['email'].strip()
        password = request.form['password'].strip()
        
        conn = get_db_connection()
        try:
            conn.execute('''
                INSERT INTO usuarios (nombre, apellido, cedula, email, password, rol)
                VALUES (?, ?, ?, ?, ?, 'pasajero')
            ''', (nombre, apellido, cedula, email, password))
            conn.commit()
            conn.close()
            return redirect(url_for('login', registro='ok'))
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('registro.html', error="La cédula o el correo ya se encuentran registrados.")
            
    return render_template('registro.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==========================================
# RUTA DE ADMINISTRACIÓN (ADMIN)
# ==========================================

@app.route('/admin_historial')
def admin_historial():
    # Verificar si es admin realmente
    if session.get('rol') != 'admin':
        return redirect(url_for('index'))
        
    conn = get_db_connection()
    
    # Obtener el conteo rápido de usuarios
    total_pasajeros = conn.execute("SELECT COUNT(*) FROM usuarios WHERE rol = 'pasajero'").fetchone()[0]
    total_conductores = conn.execute("SELECT COUNT(*) FROM usuarios WHERE rol = 'conductor'").fetchone()[0]
    
    # Obtener el historial completo de viajes ordenado de más recientes a antiguos
    viajes_db = conn.execute('''
        SELECT v.id, u.nombre || ' ' || u.apellido AS pasajero, v.origen, v.destino, v.monto, v.fecha_hora, v.estado
        FROM viajes v
        JOIN usuarios u ON v.pasajero_id = u.id
        ORDER BY v.id DESC
    ''').fetchall()
    
    conn.close()
    
    return render_template('admin_historial.html', 
                           viajes=viajes_db, 
                           total_pasajeros=total_pasajeros, 
                           total_conductores=total_conductores)


@app.route('/admin/crear_conductor', methods=['POST'])
def crear_conductor():
    if session.get('rol') != 'admin':
        return redirect(url_for('index'))
        
    nombre = request.form['nombre'].strip()
    apellido = request.form['apellido'].strip()
    cedula = request.form['cedula'].strip()
    fecha_nacimiento = request.form['fecha_nacimiento']
    email = request.form['email'].strip()
    password = request.form['password'].strip()
    placa = request.form['placa'].strip()
    serial_motor = request.form.get('serial_motor', '').strip()
    serial_carroceria = request.form.get('serial_carroceria', '').strip()
    
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO usuarios (nombre, apellido, cedula, fecha_nacimiento, email, password, rol, placa, serial_motor, serial_carroceria)
            VALUES (?, ?, ?, ?, ?, ?, 'conductor', ?, ?, ?)
        ''', (nombre, apellido, cedula, fecha_nacimiento, email, password, placa, serial_motor, serial_carroceria))
        conn.commit()
    except sqlite3.IntegrityError as e:
        print("Error registrando conductor:", e)
    finally:
        conn.close()
        
    return redirect(url_for('admin_historial', status='conductor_ok'))

# ==========================================
# RUTAS DEL PASAJERO
# ==========================================

@app.route('/pasajero')
def pasajero_panel():
    if session.get('rol') != 'pasajero':
        return redirect(url_for('index'))
    return render_template('pasajero.html', nombre=session.get('nombre'))


@app.route('/solicitar_viaje', methods=['POST'])
def solicitar_viaje():
    if session.get('rol') != 'pasajero':
        return redirect(url_for('index'))
        
    origen = request.form['origen']
    destino = request.form['destino']
    monto = float(request.form.get('monto', 700.0))
    pasajero_id = session.get('usuario_id')
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO viajes (pasajero_id, origen, destino, monto, estado)
        VALUES (?, ?, ?, ?, 'Pendiente')
    ''', (pasajero_id, origen, destino, monto))
    conn.commit()
    conn.close()
    
    return redirect(url_for('pasajero_panel', status='success'))

# ==========================================
# RUTAS DEL CONDUCTOR (Para futuras vistas)
# ==========================================

@app.route('/conductor')
def conductor_panel():
    if session.get('rol') != 'conductor':
        return redirect(url_for('index'))
    return f"Bienvenido Conductor {session.get('nombre')}. Panel de pedidos en desarrollo."


if __name__ == '__main__':
    # Render asigna dinámicamente un puerto en producción
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
