from flask import Flask, render_template, request, session, redirect, jsonify
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
# Usamos una clave de seguridad por defecto para la sesión
app.secret_key = os.environ.get('SECRET_KEY', 'martillos_seguridad_alta_2026')

DB_PATH = 'database.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Mantenemos la estructura de la base de datos exacta
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS viajes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pasajero TEXT NOT NULL,
            origen TEXT NOT NULL,
            destino TEXT NOT NULL,
            fecha TEXT NOT NULL,
            estado TEXT DEFAULT 'Pendiente'
        )
    ''')
    conn.commit()
    conn.close()

# Inicializar la base de datos al arrancar el servidor
init_db()

@app.route('/')
@app.route('/pasajero')
def pasajero():
    return render_template('pasajero.html')

@app.route('/admin_historial')
def admin_historial():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM viajes ORDER BY id DESC')
    viajes = cursor.fetchall()
    conn.close()
    return render_template('admin_historial.html', viajes=viajes)

@app.route('/solicitar_viaje', methods=['POST'])
def solicitar_viaje():
    pasajero = request.form.get('pasajero')
    origen = request.form.get('origen')
    destino = request.form.get('destino')
    fecha = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if pasajero and origen and destino:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO viajes (pasajero, origen, destino, fecha) VALUES (?, ?, ?, ?)',
                       (pasajero, origen, destino, fecha))
        conn.commit()
        conn.close()
        return redirect('/pasajero?status=success')
    
    return redirect('/pasajero?status=error')

# ==================== RUTAS SINCRONIZADAS PARA EL CONDUCTOR ====================

@app.route('/conductor')
def conductor():
    # Pasa el nombre a la plantilla; si no hay sesión iniciada, usa 'Disponible'
    driver_name = session.get('driver_name', 'Disponible')
    return render_template('conductor.html', driver_name=driver_name)

@app.route('/api/check_ride')
def check_ride():
    # Esta ruta la consulta el JavaScript del conductor automáticamente cada 3 segundos
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Busca el viaje 'Pendiente' más reciente
    cursor.execute("SELECT id, pasajero, origen, destino FROM viajes WHERE estado = 'Pendiente' ORDER BY id DESC LIMIT 1")
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
    # Esta ruta procesa la aceptación del viaje cuando el conductor hace clic en el botón
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data received"}), 400
        
    ride_id = data.get('ride_id')
    if ride_id:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # Cambiamos el estado de 'Pendiente' a 'Aceptado'
        cursor.execute("UPDATE viajes SET estado = 'Aceptado' WHERE id = ?", (ride_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Missing ride_id"}), 400

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/pasajero')

if __name__ == '__main__':
    app.run()
