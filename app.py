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

# Inicializar base de datos al arrancar
init_db()

@app.route('/')
@app.route('/pasajero')
def pasajero():
    # Esta ruta cargará la vista para solicitar viajes
    return render_template('pasajero.html')

@app.route('/admin_historial')
def admin_historial():
    # Esta ruta cargará el historial de administración
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

if __name__ == '__main__':
    app.run()
