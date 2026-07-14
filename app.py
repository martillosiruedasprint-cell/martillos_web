from flask import Flask, render_template, request, session, redirect, jsonify
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'martillos_seguridad_alta_2026')

# ... (resto de tu lógica que ya tenemos) ...
if __name__ == '__main__':
    app.run()
