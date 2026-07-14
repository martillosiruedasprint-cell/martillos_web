# ==================== CONTROLES DE VIAJES Y SALDO ====================

@app.route('/solicitar_viaje', methods=['POST'])
def solicitar_viaje():
    if not verificar_autenticacion('pasajero'): 
        return redirect('/login')
        
    usuario_id = session['user_id']
    origen = request.form.get('origen')
    destino = request.form.get('destino')
    fecha = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 1. Conectar a la Base de Datos para verificar el saldo real actual del usuario
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT saldo FROM usuarios WHERE id = ?", (usuario_id,))
    saldo_actual = cursor.fetchone()[0]
    
    # 2. Bloqueo de seguridad: Tarifa mínima base para pedir una moto (Ej. $1.00)
    TARIFA_MINIMA_VIAJE = 1.00
    if saldo_actual < TARIFA_MINIMA_VIAJE:
        conn.close()
        # Redirigir indicando que el saldo es insuficiente
        return redirect('/pasajero?status=saldo_insuficiente')
        
    if origen and destino:
        cursor.execute('INSERT INTO viajes (pasajero_id, origen, destino, fecha) VALUES (?, ?, ?, ?)', 
                       (usuario_id, origen, destino, fecha))
        conn.commit()
        conn.close()
        return redirect('/pasajero?status=success')
        
    conn.close()
    return redirect('/pasajero?status=error')


# ==================== PROCESAMIENTO DE PAGO MÓVIL CON LÍMITES ====================

@app.route('/pasajero/recargar', methods=['POST'])
def pasajero_recargar():
    """El pasajero reporta un pago móvil con límites estrictos de $1 a $20"""
    if not verificar_autenticacion('pasajero'): 
        return jsonify({"success": False, "message": "No autorizado"})
        
    usuario_id = session['user_id']
    monto_str = request.form.get('monto')
    telefono_origen = request.form.get('telefono_origen').strip()
    banco_origen = request.form.get('banco_origen')
    referencia = request.form.get('referencia').strip()
    fecha_registro = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Validación de conversión numérica
    try:
        monto = float(monto_str)
    except (ValueError, TypeError):
        return redirect('/pasajero?status=monto_invalido')
        
    # VALIDACIÓN ESTRICTA DE LÍMITES DE SEGURIDAD
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
        return "<h3>Error de Seguridad: Este número de referencia ya ha sido registrado previamente.</h3><p>Para evitar fraudes o duplicaciones, no se permiten referencias repetidas.</p><a href='/pasajero'>Volver</a>"
