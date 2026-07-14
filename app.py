from flask import Flask, render_template, request, session, redirect, jsonify
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'martillos_seguridad_alta_2026')

DB_PATH = 'database.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
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

# ==================== NUEVAS RUTAS PARA EL CONDUCTOR ====================

@app.route('/conductor')
def conductor():
    # Carga la interfaz visual del conductor
    return render_template('conductor.html')

@app.route('/api/viaje_pendiente')
def viaje_pendiente():
    # El navegador del conductor consultará esta ruta cada 4 segundos buscando viajes 'Pendientes'
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, pasajero, origen, destino FROM viajes WHERE estado = 'Pendiente' ORDER BY id DESC LIMIT 1")
    viaje = cursor.fetchone()
    conn.close()
    
    if viaje:
        return jsonify({
            "encontrado": True,
            "id": viaje[0],
            "pasajero": viaje[1],
            "origen": viaje[2],
            "destino": viaje[3]
        })
    return jsonify({"encontrado": False})

@app.route('/api/aceptar_viaje', methods=['POST'])
def aceptar_viaje():
    viaje_id = request.json.get('id')
    if viaje_id:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE viajes SET estado = 'Aceptado' WHERE id = ?", (viaje_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    return jsonify({"success": False})

if __name__ == '__main__':
    app.run()
