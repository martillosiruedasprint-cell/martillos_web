# ==================== RUTAS DE PAGO MÓVIL (SEGURIDAD FINANCIERA) ====================

@app.route('/pasajero/recargar', methods=['POST'])
def pasajero_recargar():
    """El pasajero reporta un pago móvil realizado"""
    if not verificar_autenticacion('pasajero'): 
        return jsonify({"success": False, "message": "No autorizado"})
        
    usuario_id = session['user_id']
    monto = request.form.get('monto')
    telefono_origen = request.form.get('telefono_origen').strip()
    banco_origen = request.form.get('banco_origen')
    referencia = request.form.get('referencia').strip()
    fecha_registro = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Validaciones básicas
    if not monto or float(monto) <= 0:
        return redirect('/pasajero?status=monto_invalido')
    if not referencia or len(referencia) < 4:
        return redirect('/pasajero?status=referencia_invalida')
        
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Guardar solicitud de recarga (La DB frena duplicados gracias a UNIQUE en 'referencia')
        cursor.execute('''
            INSERT INTO pagos (usuario_id, monto, telefono_origen, banco_origen, referencia, fecha_registro, estado)
            VALUES (?, ?, ?, ?, ?, ?, 'Pendiente')
        ''', (usuario_id, float(monto), telefono_origen, banco_origen, referencia, fecha_registro))
        
        conn.commit()
        conn.close()
        return redirect('/pasajero?status=pago_reportado')
        
    except sqlite3.IntegrityError:
        # Esto salta si el número de referencia ya existe en la base de datos
        return "<h3>Error de Seguridad: Este número de referencia ya ha sido registrado previamente.</h3><p>Para evitar fraudes o duplicaciones, no se permiten referencias repetidas.</p><a href='/pasajero'>Volver</a>"

@app.route('/admin/procesar_pago/<int:pago_id>/<string:accion>', methods=['POST'])
def admin_procesar_pago(pago_id, accion):
    """El administrador aprueba o rechaza el pago tras verificar su banco"""
    if not verificar_autenticacion('admin'): 
        abort(403)
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Obtener detalles del pago
    cursor.execute("SELECT usuario_id, monto, estado FROM pagos WHERE id = ?", (pago_id,))
    pago = cursor.fetchone()
    
    if not pago:
        conn.close()
        return "Pago no encontrado"
        
    usuario_id, monto, estado_actual = pago
    
    # Evitar doble procesamiento
    if estado_actual != 'Pendiente':
        conn.close()
        return redirect('/admin_historial?status=ya_procesado')
        
    if accion == 'aprobar':
        # 1. Actualizar estado del pago
        cursor.execute("UPDATE pagos SET estado = 'Aprobado' WHERE id = ?", (pago_id,))
        # 2. Sumar de forma inmediata el saldo al pasajero
        cursor.execute("UPDATE usuarios SET saldo = saldo + ? WHERE id = ?", (monto, usuario_id))
        
    elif accion == 'rechazar':
        cursor.execute("UPDATE pagos SET estado = 'Rechazado' WHERE id = ?", (pago_id,))
        
    conn.commit()
    conn.close()
    return redirect('/admin_historial?status=pago_procesado_ok')
