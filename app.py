from flask import Flask, render_template, request, session, redirect, url_for, jsonify, abort
import sqlite3
from datetime import datetime
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'martillos_seguridad_extrema_2026_jwt_token')

DB_PATH = 'database.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Tabla de Usuarios
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
    
    # 3. Tabla de Transacciones/Pago Móvil
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pagos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            monto REAL NOT NULL,
            telefono_origen TEXT NOT NULL,
            banco_origen TEXT NOT NULL,
            referencia TEXT UNIQUE NOT NULL,
            fecha_registro TEXT NOT NULL,
            estado TEXT DEFAULT 'Pendiente',
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

    # Crear Administrador inicial si no existe
    cursor.execute("SELECT * FROM usuarios WHERE email = 'admin@martillos.com'")
    if not cursor.fetchone():
        hashed_pw = generate_password_hash('admin123')
        cursor.execute("INSERT INTO usuarios (nombre, email, password, rol) VALUES (?, ?, ?, ?)",
                       ('Administrador', 'admin@martillos.com', hashed_pw, 'admin'))
                       
    conn.commit()
    conn.close()

init_db()

def get_config():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT tasa_comision, imagen_principal, video_animacion FROM configuracion WHERE id = 1")
    res = cursor.fetchone()
    conn.close()
    if res:
        return {"tasa": res[0], "imagen": res[1], "video": res[2]}
    return {"tasa": 9.0, "imagen": "", "video": ""}

def verificar_autenticacion(rol_requerido):
    if 'user_id' not in session:
        return False
    if session.get('rol') != rol_requerido:
        return False
    return True

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect('/login')
    
    rol = session.get('rol')
    if rol == 'admin': 
        return redirect('/admin_historial')
    if rol == 'conductor': 
        return redirect('/conductor')
    return redirect('/pasajero')

@app.route('/login', methods=['GET', 'POST'])
def login():
    config = get_config()
    if request.method == 'POST':
        email = request.form.get('email').strip()
        password = request.form.get('password')
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre, email, password, rol FROM usuarios WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user[3], password):
            session.clear()
            session['user_id'] = user[0]
            session['nombre'] = user[1]
            session['email'] = user[2]
            session['rol'] = user[4]
            return redirect('/')
        return "Credenciales inválidas. <a href='/login'>Intentar de nuevo</a>"
        
    return render_template('login.html', config=config)

@app.route('/registro_pasajero', methods=['GET', 'POST'])
def registro_pasajero():
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
            cursor.execute("INSERT INTO usuarios (nombre, email, password, rol, saldo) VALUES (?, ?, ?, ?, ?)",
                           (nombre, email, hashed_pw, 'pasajero', 0.0))
            conn.commit()
            conn.close()
            return "¡Registro exitoso! <a href='/login'>Inicia sesión aquí</a>"
        except sqlite3.IntegrityError:
            return "El correo ya se encuentra registrado."
            
    return render_template('registro_pasajero.html')

@app.route('/pasajero')
def pasajero():
    if not verificar_autenticacion('pasajero'): 
        return redirect('/login')
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT saldo, nombre FROM usuarios WHERE id = ?", (session['user_id'],))
    usuario = cursor.fetchone()
    conn.close()
    
    saldo_real = usuario[0] if usuario else 0.0
    nombre_real = usuario[1] if usuario else "Pasajero"
    
    return render_template('pasajero.html', saldo=saldo_real, nombre=nombre_real)

@app.route('/solicitar_viaje', methods=['POST'])
def solicitar_viaje():
    if not verificar_autenticacion('pasajero'): 
        return redirect('/login')
        
    usuario_id = session['user_id']
    origen = request.form.get('origen')
    destino = request.form.get('destino')
    fecha = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT saldo FROM usuarios WHERE id = ?", (usuario_id,))
    saldo_actual = cursor.fetchone()[0]
    
    TARIFA_MINIMA_VIAJE = 1.00
    if saldo_actual < TARIFA_MINIMA_VIAJE:
        conn.close()
        return redirect('/pasajero?status=saldo_insuficiente')
        
    if origen and destino:
        cursor.execute('INSERT INTO viajes (pasajero_id, origen, destino, fecha) VALUES (?, ?, ?, ?)', 
                       (usuario_id, origen, destino, fecha))
        conn.commit()
        conn.close()
        return redirect('/pasajero?status=success')
        
    conn.close()
    return redirect('/pasajero?status=error')

@app.route('/pasajero/recargar', methods=['POST'])
def pasajero_recargar():
    if not verificar_autenticacion('pasajero'): 
        return jsonify({"success": False, "message": "No autorizado"})
        
    usuario_id = session['user_id']
    monto_str = request.form.get('monto')
    telefono_origen = request.form.get('telefono_origen').strip()
    banco_origen = request.form.get('banco_origen')
    referencia = request.form.get('referencia').strip()
    fecha_registro = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        monto = float(monto_str)
    except (ValueError, TypeError):
        return redirect('/pasajero?status=monto_invalido')
        
    if monto < 1.00:
        return redirect('/pasajero?status=recarga_muy_baja')
    if monto > 20.00:
        return redirect('/pasajero?status=recarga_muy_alta')
        
    if not referencia or len(referencia) < 4:
        return redirect('/pasajero?status=referencia_invalida')
        
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO pagos (usuario_id, monto, telefono_origen, banco_origen, referencia, fecha_registro, estado)
            VALUES (?, ?, ?, ?, ?, ?, 'Pendiente')
        ''', (usuario_id, monto, telefono_origen, banco_origen, referencia, fecha_registro))
        
        conn.commit()
        conn.close()
        return redirect('/pasajero?status=pago_reportado')
        
    except sqlite3.IntegrityError:
        return "<h3>Error: Referencia repetida.</h3><p>Este pago ya fue reportado previamente.</p><a href='/pasajero'>Volver</a>"

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
    
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE rol = 'pasajero'")
    total_pasajeros = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE rol = 'conductor'")
    total_conductores = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT pagos.id, usuarios.nombre, pagos.monto, pagos.referencia, pagos.estado 
        FROM pagos JOIN usuarios ON pagos.usuario_id = usuarios.id 
        WHERE pagos.estado = 'Pendiente'
    ''')
    pagos_pendientes = cursor.fetchall()
    
    conn.close()
    config = get_config()
    return render_template('admin_historial.html', viajes=viajes, total_pasajeros=total_pasajeros, total_conductores=total_conductores, config=config, pagos_pendientes=pagos_pendientes)

@app.route('/admin/crear_conductor', methods=['POST'])
def crear_conductor():
    if not verificar_autenticacion('admin'): 
        abort(403)
    
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
            VALUES (?, ?, ?, ?, ?, ?, 'conductor', ?, ?, ?)
        ''', (nombre, apellido, cedula, fecha_nacimiento, email, hashed_pw, placa, serial_motor, serial_carroceria))
        conn.commit()
        conn.close()
        return redirect('/admin_historial?status=conductor_ok')
    except sqlite3.IntegrityError:
        return "Error: Cédula o Correo duplicado en el sistema."

@app.route('/admin/procesar_pago/<int:pago_id>/<string:accion>', methods=['POST'])
def admin_procesar_pago(pago_id, accion):
    if not verificar_autenticacion('admin'): 
        abort(403)
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT usuario_id, monto, estado FROM pagos WHERE id = ?", (pago_id,))
    pago = cursor.fetchone()
    
    if not pago:
        conn.close()
        return "Pago no encontrado"
        
    usuario_id, monto, estado_actual = pago
    
    if estado_actual != 'Pendiente':
        conn.close()
        return redirect('/admin_historial?status=ya_procesado')
        
    if accion == 'aprobar':
        cursor.execute("UPDATE pagos SET estado = 'Aprobado' WHERE id = ?", (pago_id,))
        cursor.execute("UPDATE usuarios SET saldo = saldo + ? WHERE id = ?", (monto, usuario_id))
    elif accion == 'rechazar':
        cursor.execute("UPDATE pagos SET estado = 'Rechazado' WHERE id = ?", (pago_id,))
        
    conn.commit()
    conn.close()
    return redirect('/admin_historial?status=pago_procesado_ok')

@app.route('/conductor')
def conductor():
    if not verificar_autenticacion('conductor'): 
        return redirect('/login')
    return render_template('conductor.html', driver_name=session.get('nombre'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
