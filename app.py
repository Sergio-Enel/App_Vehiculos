import streamlit as st
import streamlit as st
import pandas as pd
from datetime import date

# ==========================================
# CONFIGURACIÓN DE PÁGINA Y BASE DE DATOS
# ==========================================
conn = st.connection("supabase", type="sql")
st.set_page_config(page_title="Gestión de Vehículos", layout="wide")



# ==========================================
# FUNCIONES AUXILIARES
# ==========================================
def obtener_vehiculos():
    return conn.query("SELECT placa, conductor FROM vehiculos", conn)

def obtener_asignaciones(fecha):
    return conn.query(f"SELECT placa FROM asignaciones WHERE fecha='{fecha}'", conn)

# ==========================================
# INTERFAZ DE USUARIO (LOGIN OBLIGATORIO)
# ==========================================
st.sidebar.title("🔐 Acceso al Sistema")

# Obtenemos los nombres y creamos una lista con una opción neutra al principio
usuarios_df = conn.query("SELECT nombre, rol FROM usuarios", conn)
lista_usuarios = ["-- Selecciona tu nombre --"] + usuarios_df['nombre'].tolist()

usuario_actual = st.sidebar.selectbox(
    "¿Quién está ingresando?", 
    options=lista_usuarios,
    index=0  # Fuerza a que empiece en la opción neutra
)

# Verificamos si ya seleccionó a alguien
if usuario_actual == "-- Selecciona tu nombre --":
    st.title("Bienvenido al Sistema de Vehículos")
    st.warning("👈 Por favor, selecciona tu nombre en el panel de la izquierda para continuar.")
    st.info("Esto asegura que las reservas y notificaciones queden a tu nombre.")
    st.stop()  # ESTA LÍNEA ES CLAVE: Detiene la ejecución del resto del código
else:
    # Si ya eligió, extraemos el rol para que la app funcione normalmente
    rol_actual = usuarios_df[usuarios_df['nombre'] == usuario_actual]['rol'].values[0]
    st.sidebar.success(f"Sesión iniciada: **{usuario_actual}**")
    st.sidebar.info(f"Rol activo: **{rol_actual}**")

# ==========================================
# VISTA GLOBAL: VEHÍCULOS EN RUTA SEGÚN FECHA
# ==========================================
st.markdown("### 🌐 Vehículos en Ruta")

# 1. Añadimos un selector de fecha para filtrar la tabla global
col_fecha_filtro, _ = st.columns([0.3, 0.7])
with col_fecha_filtro:
    fecha_consulta = st.date_input("Filtrar por fecha:", value=date.today(), key="filtro_global")

# Convertimos la fecha seleccionada a string para la consulta SQL
fecha_str = str(fecha_consulta)

# 2. Usamos 'fecha_str' en la query en lugar de 'hoy'
query_global = f"""
    SELECT r.placa as Placa, v.conductor as Conductor, r.usuario as Trabajador, r.destino as Destino, r.franja as Turno
    FROM reservas r
    JOIN vehiculos v ON r.placa = v.placa
    WHERE r.estado = 'Activa' AND r.fecha = '{fecha_str}'
"""
df_global = pd.read_sql(query_global, conn)

if not df_global.empty:
    st.dataframe(df_global, hide_index=True, use_container_width=True)
else:
    st.info(f"No hay vehículos en ruta para el día {fecha_str}.")

st.markdown("---")

# ==========================================
# VISTA: COORDINADOR
# ==========================================
if rol_actual == 'Coordinador':
    st.title("⚙️ Gestión y Asignación de Vehículos")
    st.write("Selecciona los 7 vehículos que estarán disponibles para la fecha.")
    
    fecha_sel = st.date_input("Fecha de asignación:", min_value=date.today())
    vehiculos_totales = obtener_vehiculos()['placa'].tolist()
    asignados_actuales = obtener_asignaciones(fecha_sel)['placa'].tolist()
    
    # Esta línea filtra los que ya no existen
    asignados_validos = [placa for placa in asignados_actuales if placa in vehiculos_totales]
    
    # Asignar vehículos diarios
    with st.form("form_asignacion"):
        seleccionados = st.multiselect(
            "Vehículos habilitados (Máximo 7):", 
            options=vehiculos_totales, 
            default=asignados_validos,  # <-- Usa la lista filtrada aquí
            max_selections=7
        )
        guardar = st.form_submit_button("Guardar Asignación Diaria")
        
        if guardar:
            with conn.session as s:
    # Eliminamos lo anterior para esa fecha
    s.execute("DELETE FROM asignaciones WHERE fecha = :f", {"f": str(fecha_sel)})
    # Insertamos los nuevos vehículos habilitados
    for placa in seleccionados:
        s.execute("INSERT INTO asignaciones (fecha, placa) VALUES (:f, :p)", 
                  {"f": str(fecha_sel), "p": placa})
    s.commit()
            st.success(f"Se habilitaron {len(seleccionados)} vehículos para el {fecha_sel}.")
            st.rerun()

    # Monitoreo de estado
    st.subheader("📊 Estado de Reservas")
    df_reservas_dia = conn.query(f"SELECT placa, usuario, franja, estado FROM reservas WHERE fecha='{fecha_sel}'", conn)
    if not df_reservas_dia.empty:
        st.dataframe(df_reservas_dia, use_container_width=True)
    else:
        st.info("No hay reservas registradas para esta fecha.")

    # =========================================================
    # PANEL DE CONFIGURACIÓN MAESTRA (USUARIOS Y VEHÍCULOS)
    # =========================================================
    st.markdown("---")
    with st.expander("🛠️ Panel de Control: Usuarios y Vehículos"):
        tab_veh, tab_usu = st.tabs(["Listado de Vehículos", "Listado de Usuarios"])

        # --- PESTAÑA VEHÍCULOS ---
        with tab_veh:
            st.subheader("Modificar o Agregar Vehículos")
            with st.form("form_gestion_veh"):
                col_p, col_c, col_t = st.columns(3)
                p_nueva = col_p.text_input("Placa", help="Si la placa existe, se actualiza. Si no, se crea.")
                c_nuevo = col_c.text_input("Nombre Conductor")
                t_nuevo = col_t.text_input("Celular/Contacto")
                
                if st.form_submit_button("Guardar / Actualizar"):
                    if p_nueva and c_nuevo:
                        cursor = conn.cursor()
                        cursor.execute("INSERT OR REPLACE INTO vehiculos (placa, conductor, celular) VALUES (?, ?, ?)", 
                                      (p_nueva.upper(), c_nuevo, t_nuevo))
                        conn.commit()
                        st.success(f"Vehículo {p_nueva.upper()} procesado.")
                        st.rerun()
                    else:
                        st.error("La placa y el conductor son obligatorios.")

            st.write("---")
            st.write("**Eliminar Vehículos:**")
            df_v = conn.query("SELECT * FROM vehiculos", conn)
            for _, row in df_v.iterrows():
                col_info, col_btn = st.columns([0.8, 0.2])
                col_info.write(f"🚗 **{row['placa']}** - {row['conductor']}")
                if col_btn.button("🗑️ Borrar", key=f"del_v_{row['placa']}"):
                    cursor = conn.cursor()
                    # Borrar de la tabla de vehículos
                    cursor.execute("DELETE FROM vehiculos WHERE placa=?", (row['placa'],))
                    # Borrar de las asignaciones para evitar errores de Streamlit
                    cursor.execute("DELETE FROM asignaciones WHERE placa=?", (row['placa'],))
                    conn.commit()
                    st.warning(f"Vehículo {row['placa']} eliminado del sistema.")
                    st.rerun()

        # --- PESTAÑA USUARIOS ---
        with tab_usu:
            st.subheader("Gestión de Personal")
            with st.form("form_nuevo_usuario"):
                n_usuario = st.text_input("Nombre completo")
                r_usuario = st.selectbox("Rol", ["Trabajador", "Coordinador"])
                if st.form_submit_button("Registrar"):
                    if n_usuario:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO usuarios (nombre, rol) VALUES (?, ?)", (n_usuario, r_usuario))
                        conn.commit()
                        st.success(f"Usuario {n_usuario} creado.")
                        st.rerun()
                    else:
                        st.error("El nombre es obligatorio.")

            st.write("---")
            st.write("**Eliminar Usuarios:**")
            df_u = conn.query("SELECT id, nombre, rol FROM usuarios", conn)
            for _, row in df_u.iterrows():
                if row['nombre'] != usuario_actual: # Evita borrarte a ti mismo
                    col_u, col_b = st.columns([0.8, 0.2])
                    col_u.write(f"👤 {row['nombre']} ({row['rol']})")
                    if col_b.button("🗑️ Quitar", key=f"del_u_{row['id']}"):
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM usuarios WHERE id=?", (row['id'],))
                        conn.commit()
                        st.warning(f"Usuario {row['nombre']} eliminado.")
                        st.rerun()

# ==========================================
# VISTA: USUARIO (TRABAJADOR)
# ==========================================
elif rol_actual == 'Trabajador':
    st.title("🚗 Reserva Ágil de Vehículos")
    
    tab_reserva, tab_mis_reservas = st.tabs(["Nueva Reserva", "Mis Reservas Activas"])
    
    # PESTAÑA 1: NUEVA RESERVA
    with tab_reserva:
        col1, col2 = st.columns(2)
        with col1:
            fecha_res = st.date_input("¿Qué día necesitas el vehículo?", min_value=date.today())
        with col2:
            franja_res = st.selectbox("Franja Horaria:", ["Mañana", "Tarde", "Todo el día"])
            
        st.markdown("### Vehículos Disponibles")
        # LÓGICA DE DISPONIBILIDAD
        # 1. Traer asignados para el día
        # 2. Excluir los que tienen reserva activa en la misma franja o "Todo el día"
        query_disponibles = f"""
            SELECT v.placa, v.conductor, v.celular 
            FROM asignaciones a
            JOIN vehiculos v ON a.placa = v.placa
            WHERE a.fecha = '{fecha_res}'
            AND a.placa NOT IN (
                SELECT placa FROM reservas 
                WHERE fecha = '{fecha_res}' AND estado = 'Activa'
                AND (franja = '{franja_res}' OR franja = 'Todo el día' OR '{franja_res}' = 'Todo el día')
            )
        """
        df_disp = conn.query(query_disponibles, conn)
        
        if df_disp.empty:
            st.warning("No hay vehículos disponibles para la fecha y franja seleccionadas.")
        else:
            st.dataframe(df_disp, hide_index=True, use_container_width=True)
            
            with st.form("form_reserva"):
                placa_elegida = st.selectbox("Selecciona la placa a reservar:", df_disp['placa'])
                
                # NUEVO CAMPO: Pedimos el destino
                destino_res = st.text_input("Destino al que te diriges (Ej: Sede Norte, Planta, Cliente X):")
                
                btn_reservar = st.form_submit_button("Confirmar Reserva")
                
                if btn_reservar:
                    # Validación para que no dejen el destino en blanco
                    if not destino_res:
                        st.error("⚠️ Por favor, ingresa el destino antes de reservar.")
                    else:
                        
                        with conn.session as s:
    s.execute("""
        INSERT INTO reservas (fecha, placa, usuario, franja, estado, destino) 
        VALUES (:f, :p, :u, :fr, :e, :d)
    """, {
        "f": str(fecha_res), 
        "p": placa_elegida, 
        "u": usuario_actual, 
        "fr": franja_res, 
        "e": 'Activa', 
        "d": destino_res
    })
    s.commit()
                        
                        # 2. Obtener los datos del conductor
                        datos_cond = conn.query(f"SELECT conductor, celular FROM vehiculos WHERE placa = '{placa_elegida}'", conn)
                        
                        if not datos_cond.empty:
                            nombre_cond = datos_cond.iloc[0]['conductor']
                            cel_cond = str(datos_cond.iloc[0]['celular'])
                            
                            st.success(f"✅ ¡Reserva Exitosa! Has reservado el vehículo **{placa_elegida}** hacia **{destino_res}**.")
                            
                            # 3. Crear el link de WhatsApp
                            cel_limpio = "".join(filter(str.isdigit, cel_cond))
                            if len(cel_limpio) == 10: cel_limpio = "57" + cel_limpio
                            
                            # ACTUALIZAMOS EL MENSAJE PARA INCLUIR EL DESTINO
                            mensaje = (f"Hola {nombre_cond}, soy {usuario_actual}. "
                                       f"Acabo de reservar el vehículo {placa_elegida} "
                                       f"para el día {fecha_res} en la franja: {franja_res}. "
                                       f"Destino: {destino_res}.")
                            
                            import urllib.parse
                            mensaje_encoded = urllib.parse.quote(mensaje)
                            wa_url = f"https://wa.me/{cel_limpio}?text={mensaje_encoded}"
                            
                            st.markdown(f"""
                                <div style="text-align: center; padding: 20px; border: 2px solid #25D366; border-radius: 10px; background-color: #f0fff4;">
                                    <p style="color: #128C7E; font-weight: bold;">⚠️ Paso final: Notifica al conductor</p>
                                    <a href="{wa_url}" target="_blank" style="text-decoration: none;">
                                        <button style="background-color: #25D366; color: white; border: none; padding: 12px 24px; border-radius: 25px; font-size: 16px; cursor: pointer; font-weight: bold; display: flex; align-items: center; justify-content: center; margin: 0 auto;">
                                            📱 Enviar WhatsApp a {nombre_cond}
                                        </button>
                                    </a>
                                </div>
                            """, unsafe_allow_html=True)
                        
                        # Nota: Quitamos el st.rerun() aquí para que el usuario pueda ver y tocar el botón.
                        # El sistema se refrescará la próxima vez que interactúe.
                        else:
                           st.warning("Reserva guardada, pero no se encontró celular del conductor para notificar.")

    # PESTAÑA 2: MIS RESERVAS / LIBERAR
    with tab_mis_reservas:
        st.write("Gestiona tus desplazamientos actuales.")
        query_mis_reservas = f"SELECT id, fecha, placa, franja FROM reservas WHERE usuario='{usuario_actual}' AND estado='Activa'"
        df_mis = pd.read_sql(query_mis_reservas, conn)
        
        if df_mis.empty:
            st.info("No tienes vehículos asignados actualmente.")
        else:
            for index, row in df_mis.iterrows():
                with st.container():
                    st.markdown(f"**Vehículo:** {row['placa']} | **Día:** {row['fecha']} | **Turno:** {row['franja']}")
                    # Botón para liberar el vehículo
                    if st.button(f"🗑️ Liberar Vehículo {row['placa']}", key=f"lib_{row['id']}"):
                        with conn.session as s:
    s.execute("UPDATE reservas SET estado = 'Liberada' WHERE id = :id", {"id": row['id']})
    s.commit()
                        
                        # 2. Buscamos los datos del conductor para avisarle
                        datos_cond = pd.read_sql(f"SELECT conductor, celular FROM vehiculos WHERE placa = '{row['placa']}'", conn)
                        
                        if not datos_cond.empty:
                            nombre_cond = datos_cond.iloc[0]['conductor']
                            cel_cond = str(datos_cond.iloc[0]['celular'])
                            
                            st.success(f"✅ Vehículo {row['placa']} liberado correctamente.")

                            # 3. Crear el link de WhatsApp para la LIBERACIÓN
                            cel_limpio = "".join(filter(str.isdigit, cel_cond))
                            if len(cel_limpio) == 10: cel_limpio = "57" + cel_limpio
                            
                            # Redactamos el mensaje de aviso
                            mensaje_lib = (f"Hola {nombre_cond}, te informo que el trabajador {usuario_actual} "
                                           f"ha LIBERADO la reserva del vehículo {row['placa']} "
                                           f"que tenía para el turno de la {row['franja']}. "
                                           f"El vehículo ya está disponible.")
                            
                            import urllib.parse
                            mensaje_encoded = urllib.parse.quote(mensaje_lib)
                            wa_url_lib = f"https://wa.me/{cel_limpio}?text={mensaje_encoded}"
                            
                            # Mostramos el botón de notificación de liberación
                            st.markdown(f"""
                                <div style="text-align: center; padding: 15px; border: 2px solid #FF4B4B; border-radius: 10px; background-color: #fff5f5; margin-top: 10px;">
                                    <p style="color: #FF4B4B; font-weight: bold;">📢 Paso final: Avisa al conductor</p>
                                    <a href="{wa_url_lib}" target="_blank" style="text-decoration: none;">
                                        <button style="background-color: #FF4B4B; color: white; border: none; padding: 10px 20px; border-radius: 20px; font-size: 14px; cursor: pointer; font-weight: bold;">
                                            📲 Avisar a {nombre_cond} (Liberación)
                                        </button>
                                    </a>
                                </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.success("Vehículo liberado. No se encontró contacto del conductor.")
                        
                        # Nota: No usamos rerun() aquí para que el trabajador pueda tocar el botón rojo de aviso.
