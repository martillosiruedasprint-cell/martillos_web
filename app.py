import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'martillos_ruedas_secreto_2026')

DB_NAME = "database.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# ==========================================
# INICIALIZACIÓN Y CONTROL DE BASE DE DATOS
# ==========================================
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabla única de Usuarios (Admin, Pasajeros/Clientes, Conductores/Motorizados)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            apellido TEXT NOT NULL,
            cedula TEXT UNIQUE NOT NULL,
            fecha_nacimiento TEXT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL,             -- 'admin', 'pasajero', 'conductor'
            placa TEXT,                    -- Solo motorizados
            serial_motor TEXT,             -- Solo motorizados
            serial_carroceria TEXT,        -- Solo motorizados
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabla de Viajes
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
    
    # Insertar el Administrador único inicial si no existe
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
# MIDDLEWARE DE CONTROL DE SESIONES
# ==========================================
@app.before_request
def verificar_sesion():
    rutas_publicas = ['login', 'registro', 'static']
    if request.endpoint in rutas_publicas or not request.endpoint:
        return

    if 'usuario_id' not in session:
        return redirect(url_for('login'))

# ==========================================
# RUTAS DE CONTROL DE FLUJO E INICIO
# ==========================================

@app.route('/')
def index():
    if 'usuario_id' in session:
        rol = session.get('rol')
        if rol == 'admin':
            return redirect(url_for('admin_panel'))
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
            
            if user['rol'] == 'admin':
                return redirect(url_for('admin_panel'))
            elif user['rol'] == 'conductor':
                return redirect(url_for('conductor_panel'))
            else:
                return redirect(url_for('pasajero_panel'))
        else:
            return render_template('login.html', error="Credenciales incorrectas.")
            
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==========================================
# 🛠️ CATEGORÍA 1: PANEL CENTRALIZADO DEL ADMINISTRADOR
# ==========================================

@app.route('/admin_panel')
def admin_panel():
    if session.get('rol') != 'admin':
        return redirect(url_for('index'))
        
    conn = get_db_connection()
    
    # Listados completos para el control del Admin
    pasajeros = conn.execute("SELECT * FROM usuarios WHERE rol = 'pasajero' ORDER BY id DESC").fetchall()
    conductores = conn.execute("SELECT * FROM usuarios WHERE rol = 'conductor' ORDER BY id DESC").fetchall()
    
    # Historial de viajes global
    viajes_db = conn.execute('''
        SELECT v.id, 
               (u1.nombre || ' ' || u1.apellido) AS pasajero, 
               v.origen, v.destino, v.monto, v.fecha_hora, v.estado,
               (u2.nombre || ' ' || u2.apellido) AS conductor
        FROM viajes v
        JOIN usuarios u1 ON v.pasajero_id = u1.id
        LEFT JOIN usuarios u2 ON v.conductor_id = u2.id
        ORDER BY v.id DESC
    ''').fetchall()
    
    conn.close()
    
    return render_template('admin_panel.html', 
                           viajes=viajes_db, 
                           pasajeros=pasajeros, 
                           conductores=conductores)


@app.route('/admin/crear_usuario', methods=['POST'])
def admin_crear_usuario():
    if session.get('rol') != 'admin':
        return redirect(url_for('index'))
        
    rol = request.form['rol'] # 'pasajero' o 'conductor'
    nombre = request.form['nombre'].strip()
    apellido = request.form['apellido'].strip()
    cedula = request.form['cedula'].strip()
    email = request.form['email'].strip()
    password = request.form['password'].strip()
    
    # Campos opcionales exclusivos de motorizados
    placa = request.form.get('placa', '').strip() if rol == 'conductor' else None
    serial_motor = request.form.get('serial_motor', '').strip() if rol == 'conductor' else None
    serial_carroceria = request.form.get('serial_carroceria', '').strip() if rol == 'conductor' else None
    
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO usuarios (nombre, apellido, cedula, email, password, rol, placa, serial_motor, serial_carroceria)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (nombre, apellido, cedula, email, password, rol, placa, serial_motor, serial_carroceria))
        conn.commit()
        status = 'success'
    except sqlite3.IntegrityError:
        status = 'error_duplicado'
    finally:
        conn.close()
        
    return redirect(url_for('admin_panel', status=status))


@app.route('/admin/eliminar_usuario/<int:id>')
def admin_eliminar_usuario(id):
    if session.get('rol') != 'admin':
        return redirect(url_for('index'))
        
    conn = get_db_connection()
    conn.execute("DELETE FROM usuarios WHERE id = ? AND rol != 'admin'", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel', status='deleted'))

# ==========================================
# 🏍️ CATEGORÍA 2: PANEL DE CONDUCTORES / MOTORIZADOS
# ==========================================

@app.route('/conductor')
def conductor_panel():
    if session.get('rol') != 'conductor':
        return redirect(url_for('index'))
        
    conn = get_db_connection()
    # Ver viajes pendientes en el sistema
    viajes_disponibles = conn.execute('''
        SELECT v.id, (u.nombre || ' ' || u.apellido) AS pasajero, v.origen, v.destino, v.monto, v.fecha_hora 
        FROM viajes v
        JOIN usuarios u ON v.pasajero_id = u.id
        WHERE v.estado = 'Pendiente'
        ORDER BY v.id DESC
    ''').fetchall()
    
    # Ver viajes que tiene asignados o completados el conductor actual
    mis_viajes = conn.execute('''
        SELECT v.id, (u.nombre || ' ' || u.apellido) AS pasajero, v.origen, v.destino, v.monto, v.estado
        FROM viajes v
        JOIN usuarios u ON v.pasajero_id = u.id
        WHERE v.conductor_id = ?
        ORDER BY v.id DESC
    ''', (session.get('usuario_id'),)).fetchall()
    
    conn.close()
    return render_template('conductor_panel.html', 
                           viajes=viajes_disponibles, 
                           mis_viajes=mis_viajes,
                           nombre=session.get('nombre'))


@app.route('/conductor/aceptar/<int:viaje_id>')
def conductor_aceptar_viaje(viaje_id):
    if session.get('rol') != 'conductor':
        return redirect(url_for('index'))
        
    conn = get_db_connection()
    conn.execute('''
        UPDATE viajes 
        SET estado = 'Aceptado', conductor_id = ? 
        WHERE id = ? AND estado = 'Pendiente'
    ''', (session.get('usuario_id'), viaje_id))
    conn.commit()
    conn.close()
    return redirect(url_for('conductor_panel'))


@app.route('/conductor/completar/<int:viaje_id>')
def conductor_completar_viaje(viaje_id):
    if session.get('rol') != 'conductor':
        return redirect(url_for('index'))
        
    conn = get_db_connection()
    conn.execute('''
        UPDATE viajes 
        SET estado = 'Completado' 
        WHERE id = ? AND conductor_id = ?
    ''', (viaje_id, session.get('usuario_id')))
    conn.commit()
    conn.close()
    return redirect(url_for('conductor_panel'))

# ==========================================
# 🚖 CATEGORÍA 3: PANEL DEL PASAJERO / CLIENTE
# ==========================================

@app.route('/pasajero')
def pasajero_panel():
    if session.get('rol') != 'pasajero':
        return redirect(url_for('index'))
        
    conn = get_db_connection()
    # Mostrar su propio historial de solicitudes para saber si lo aceptaron
    mis_solicitudes = conn.execute('''
        SELECT v.id, v.origen, v.destino, v.monto, v.estado, 
               (u.nombre || ' ' || u.apellido || ' [Placa: ' || u.placa || ']') AS motorizado
        FROM viajes v
        LEFT JOIN usuarios u ON v.conductor_id = u.id
        WHERE v.pasajero_id = ?
        ORDER BY v.id DESC
    ''', (session.get('usuario_id'),)).fetchall()
    conn.close()
    
    return render_template('pasajero.html', 
                           nombre=session.get('nombre'), 
                           solicitudes=mis_solicitudes)


@app.route('/pasajero/solicitar', methods=['POST'])
def pasajero_solicitar():
    if session.get('rol') != 'pasajero':
        return redirect(url_for('index'))
        
    origen = request.form['origen']
    destino = request.form['destino']
    monto = 700.0  # Tarifa fija estipulada
    pasajero_id = session.get('usuario_id')
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO viajes (pasajero_id, origen, destino, monto, estado)
        VALUES (?, ?, ?, ?, 'Pendiente')
    ''', (pasajero_id, origen, destino, monto))
    conn.commit()
    conn.close()
    
    return redirect(url_for('pasajero_panel', status='success'))


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
