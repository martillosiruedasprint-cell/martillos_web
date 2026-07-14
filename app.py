import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'martillos_ruedas_secreto_2026'

def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/solicitar_carrera', methods=['POST'])
def solicitar():
    # Lógica de solicitud de carrera limitada a San Juan de los Morros
    # Aquí el motorizado recibe la notificación via socket o refresco
    return "Carrera solicitada en San Juan de los Morros"

# [Añadir aquí las rutas de Admin, Conductor y Pasajero que ya definimos]
if __name__ == '__main__':
    app.run(debug=True)
