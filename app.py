import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import date
import urllib.parse

# ==========================================
# CONFIGURACIÓN DE PÁGINA Y BASE DE DATOS
# ==========================================
st.set_page_config(page_title="Gestión de Vehículos", layout="wide")

# Conexión directa
conn = st.connection(
    "supabase", 
    type="sql", 
    url="postgresql://postgres.prqgmsnglfvqyizfvaqm:Energia2026Master@aws-1-sa-east-1.pooler.supabase.com:5432/postgres"
)

# ==========================================
# FUNCIONES AUXILIARES
# ==========================================
def obtener_vehiculos():
    return conn.query("SELECT placa, conductor, celular FROM vehiculos", ttl=0)

def obtener_asignaciones(fecha):
    return conn.query(f"SELECT placa FROM asignaciones WHERE fecha='{fecha}'", ttl=0)

# ==========================================
# INTERFAZ DE USUARIO (LOGIN OBLIGATORIO)
# ==========================================
st.sidebar.title("🔐 Acceso al Sistema")

# Obtenemos los nombres con ttl=0
usuarios_df = conn.query("SELECT nombre, rol FROM usuarios", ttl=0)
lista_usuarios = ["-- Selecciona tu nombre --"] + usuarios_df['nombre'].tolist()

usuario_actual = st.sidebar.selectbox(
    "¿Quién está ingresando?", 
    options=lista_usuarios,
    index=0 
)

if usuario_actual == "-- Selecciona tu nombre --":
    st.title("Bienvenido al Sistema de Vehículos")
    st.warning("👈 Por favor, selecciona tu nombre en el panel de la izquierda para continuar.")
    st.stop() 
else:
    rol_actual = usuarios_df[usuarios_df['nombre'] == usuario_actual]['rol'].values[0]
    
    # --- DETALLE PARA TU COMPAÑERA ---
    # Reemplaza 'Nombre de tu compañera' exactamente como aparece en la DB
    if usuario_actual == "Angelica Vela": 
        st.markdown(f"""
            <div style="
                background-color: #FFC0CB; 
                padding: 20px; 
                border-radius: 15px; 
                border: 2px solid #FF69B4;
                text-align: center;
                margin-bottom: 20px;">
                <h1 style="color: #D23669; margin: 0;">🌸 ¡Bienvenida, {usuario_actual}! 🌸</h1>
                <p style="color: #D23669; font-weight: bold;">Sesión activa en modo especial</p>
            </div>
        """, unsafe_allow_html=True)
    
    else:
        st.sidebar.success(f"Sesión iniciada: **{usuario_actual}**")
    # ---------------------------------
        st.sidebar.info(f"Rol activo: **{rol_actual}**")

# ==========================================
# VISTA GLOBAL: VEHÍCULOS EN RUTA SEGÚN FECHA
# ==========================================
st.markdown("### 🌐 Vehículos en Ruta")

col_fecha_filtro, _ = st.columns([0.3, 0.7])
with col_fecha_filtro:
    fecha_consulta = st.date_input("Filtrar por fecha:", value=date.today(), key="filtro_global")

fecha_str = str(fecha_consulta)

query_global = f"""
    SELECT r.placa as Placa, v.conductor as Conductor, r.usuario as Trabajador, r.destino as Destino, r.franja as Turno
    FROM reservas r
    JOIN vehiculos v ON r.placa = v.placa
    WHERE r.estado = 'Activa' AND r.fecha = '{fecha_str}'
"""
df_global = conn.query(query_global, ttl=0)

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
    fecha_sel = st.date_input("Fecha de asignación:", min_value=date.today())
    
    vehiculos_totales = obtener_vehiculos()['placa'].tolist()
    asignados_actuales = obtener_asignaciones(fecha_sel)['placa'].tolist()
    asignados_validos = [placa for placa in asignados_actuales if placa in vehiculos_totales]
    
    with st.form("form_asignacion"):
        seleccionados = st.multiselect(
            "Vehículos habilitados (Máximo 7):", 
            options=vehiculos_totales, 
            default=asignados_validos, 
            max_selections=7
        )
        if st.form_submit_button("Guardar Asignación Diaria"):
            try:
                with conn.session as s:
                    s.execute(text("DELETE FROM asignaciones WHERE fecha = :f"), {"f": str(fecha_sel)})
                    for placa in seleccionados:
                        s.execute(text("INSERT INTO asignaciones (fecha, placa) VALUES (:f, :p)"), 
                                   {"f": str(fecha_sel), "p": placa})
                    s.commit()
                st.success(f"Se habilitaron {len(seleccionados)} vehículos.")
                st.rerun()
            except Exception as e:
                st.error("Error al guardar asignación. Intente de nuevo.")

    st.subheader("📊 Control Maestro de Reservas")
    
    # 1. Consulta de datos (incluimos r.fecha)
    df_res_coord = conn.query(f"""
        SELECT r.id, r.fecha, r.placa, v.conductor, r.usuario, r.franja, r.destino, r.estado 
        FROM reservas r
        JOIN vehiculos v ON r.placa = v.placa
        WHERE r.fecha='{fecha_sel}'
    """, ttl=0)
    
    if df_res_coord.empty:
        st.info(f"No hay movimientos registrados para el {fecha_sel}")
    else:
        # 2. Vista Rápida con Fecha
        st.write("### Vista Rápida")
        # Formateamos la fecha para que se vea más limpia en la tabla
        df_mostrar = df_res_coord.copy()
        df_mostrar['fecha'] = df_mostrar['fecha'].astype(str)
        
        st.dataframe(
            df_mostrar[['fecha', 'placa', 'conductor', 'usuario', 'franja', 'estado']], 
            use_container_width=True, 
            hide_index=True
        )

        # 3. Acciones de Gestión
        st.write("### Acciones de Liberación")
        reservas_activas = df_res_coord[df_res_coord['estado'] == 'Activa']
        
        if reservas_activas.empty:
            st.success("No hay reservas activas por liberar.")
        else:
            for _, row in reservas_activas.iterrows():
                # Añadimos la fecha en el título del expander para mayor claridad
                with st.expander(f"📅 {row['fecha']} | 🚗 {row['placa']} | 👤 {row['usuario']}"):
                    col_info_ad, col_btn_ad = st.columns([0.7, 0.3])
                    
                    with col_info_ad:
                        st.write(f"**Turno:** {row['franja']}")
                        st.write(f"**Conductor:** {row['conductor']}")
                        st.write(f"**Destino:** {row['destino']}")
                    
                    with col_btn_ad:
                        if st.button(f"🚫 Forzar Liberación", key=f"f_lib_{row['id']}", use_container_width=True):
                            try:
                                with conn.session as s:
                                    s.execute(text("UPDATE reservas SET estado = 'Liberada' WHERE id = :id"), {"id": row['id']})
                                    s.commit()
                                
                                st.toast(f"Vehículo {row['placa']} liberado", icon="✅")
                                
                                # WhatsApp de aviso
                                d_v = conn.query(f"SELECT celular FROM vehiculos WHERE placa='{row['placa']}'", ttl=0)
                                if not d_v.empty:
                                    cel_c = "".join(filter(str.isdigit, str(d_v.iloc[0]['celular'])))
                                    if len(cel_c) == 10: cel_c = "57" + cel_c
                                    msj = f"Hola {row['conductor']}, el Coordinador {usuario_actual} ha liberado tu vehículo {row['placa']} del día {row['fecha']}."
                                    url = f"https://wa.me/{cel_c}?text={urllib.parse.quote(msj)}"
                                    
                                    st.markdown(f"""
                                        <a href="{url}" target="_blank" style="text-decoration: none;">
                                            <div style="background-color: #FF4B4B; color: white; padding: 10px; text-align: center; border-radius: 5px; font-weight: bold;">
                                                📲 Avisar al Conductor
                                            </div>
                                        </a>
                                    """, unsafe_allow_html=True)
                            except Exception as e:
                                st.error(f"Error: {e}")
            else:
                st.markdown(f"<span style='color:gray'>🚗 <i>{row['placa']}</i> | 👤 <i>{row['usuario']}</i> | ✅ <b>Liberada</b></span>", unsafe_allow_html=True)
    st.markdown("---")
    st.subheader("👑 Reserva Manual (Solo Coordinador)")
    
    col_r1, col_r2, col_r3 = st.columns(3)
    with col_r1: fecha_admin = st.date_input("Fecha:", min_value=date.today(), key="fecha_admin")
    with col_r2: franja_admin = st.selectbox("Franja:", ["Mañana", "Tarde", "Todo el día"], key="franja_admin")
    with col_r3: 
        df_nombres = conn.query("SELECT nombre FROM usuarios", ttl=0)
        usuario_destino = st.selectbox("¿Para quién es la reserva?", df_nombres['nombre'])

    query_disp_admin = f"""
        SELECT v.placa, v.conductor, v.celular FROM asignaciones a
        JOIN vehiculos v ON a.placa = v.placa
        WHERE a.fecha = '{fecha_admin}' AND a.placa NOT IN (
            SELECT placa FROM reservas WHERE fecha = '{fecha_admin}' AND estado = 'Activa'
            AND (franja = '{franja_admin}' OR franja = 'Todo el día' OR '{franja_admin}' = 'Todo el día')
        )
    """
    df_disp_admin = conn.query(query_disp_admin, ttl=0)

    if df_disp_admin.empty:
        st.warning("No hay vehículos disponibles para esta fecha y franja.")
    else:
        with st.form("form_reserva_admin"):
            # Al coordinador sí le mostramos la lista completa para que elija a dedo
            st.dataframe(df_disp_admin, hide_index=True, use_container_width=True)
            
            col_f1, col_f2 = st.columns(2)
            with col_f1: placa_admin = st.selectbox("Selecciona la placa:", df_disp_admin['placa'])
            with col_f2: destino_admin = st.text_input("Destino:")
                
            if st.form_submit_button("Confirmar Reserva (Admin)"):
                if not destino_admin:
                    st.error("⚠️ Ingresa el destino.")
                else:
                    try:
                        with conn.session as s:
                            s.execute(text("""
                                INSERT INTO reservas (fecha, placa, usuario, franja, estado, destino) 
                                VALUES (:f, :p, :u, :fr, :e, :d)
                            """), {"f": str(fecha_admin), "p": placa_admin, "u": usuario_destino, "fr": franja_admin, "e": 'Activa', "d": destino_admin})
                            s.commit()
                        
                        st.success(f"✅ Reservado exitosamente a nombre de {usuario_destino}.")
                        
                        # Datos WhatsApp Admin
                        datos_cond_adm = df_disp_admin[df_disp_admin['placa'] == placa_admin].iloc[0]
                        n_cond_adm = datos_cond_adm['conductor']
                        c_cond_adm = "".join(filter(str.isdigit, str(datos_cond_adm['celular'])))
                        if len(c_cond_adm) == 10: c_cond_adm = "57" + c_cond_adm
                        
                        msj_wa_adm = f"Hola {n_cond_adm}, soy {usuario_actual} (Coordinador). Te he asignado un servicio con {usuario_destino} para el {fecha_admin}, Franja: {franja_admin}. Destino: {destino_admin}."
                        wa_url_adm = f"https://wa.me/{c_cond_adm}?text={urllib.parse.quote(msj_wa_adm)}"
                        
                        st.markdown(f"""
                            <a href="{wa_url_adm}" target="_blank" style="text-decoration: none;">
                                <div style="background-color: #25D366; color: white; padding: 15px; text-align: center; border-radius: 10px; font-weight: bold; font-size: 20px; margin-top: 10px;">
                                    📱 NOTIFICAR ASIGNACIÓN A {n_cond_adm.upper()}
                                </div>
                            </a>
                            <br>
                        """, unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"Error al reservar: {e}")
    with st.expander("🛠️ Panel de Control: Usuarios y Vehículos"):
        tab_veh, tab_usu = st.tabs(["Listado de Vehículos", "Listado de Usuarios"])

        with tab_veh:
            st.subheader("Modificar o Agregar Vehículos")
            with st.form("form_gestion_veh"):
                col_p, col_c, col_t = st.columns(3)
                p_nueva = col_p.text_input("Placa")
                c_nuevo = col_c.text_input("Nombre Conductor")
                t_nuevo = col_t.text_input("Celular/Contacto")
                
                if st.form_submit_button("Guardar / Actualizar"):
                    if p_nueva and c_nuevo:
                        p_limpia = p_nueva.upper().strip()
                        existe_v = conn.query(f"SELECT placa FROM vehiculos WHERE placa = '{p_limpia}'", ttl=0)
                        try:
                            with conn.session as s:
                                if not existe_v.empty:
                                    s.execute(text("UPDATE vehiculos SET conductor=:c, celular=:t WHERE placa=:p"), 
                                              {"p": p_limpia, "c": c_nuevo, "t": t_nuevo})
                                else:
                                    s.execute(text("INSERT INTO vehiculos (placa, conductor, celular) VALUES (:p, :c, :t)"), 
                                              {"p": p_limpia, "c": c_nuevo, "t": t_nuevo})
                                s.commit()
                            st.success(f"Vehículo {p_limpia} procesado.")
                            st.rerun()
                        except Exception:
                            st.error("Error al procesar el vehículo.")
                    else:
                        st.error("Placa y conductor obligatorios.")

            st.write("**Eliminar Vehículos:**")
            df_v = conn.query("SELECT * FROM vehiculos", ttl=0)
            for _, row in df_v.iterrows():
                col_i, col_b = st.columns([0.8, 0.2])
                col_i.write(f"🚗 **{row['placa']}** - {row['conductor']}")
                if col_b.button("🗑️ Borrar", key=f"del_v_{row['placa']}"):
                    try:
                        with conn.session as s:
                            s.execute(text("DELETE FROM vehiculos WHERE placa=:p"), {"p": row['placa']})
                            s.commit()
                        st.rerun()
                    except Exception:
                        st.error("No se puede borrar el vehículo (tiene reservas asociadas).")

        with tab_usu:
            st.subheader("Gestión de Personal")
            with st.form("form_nuevo_usuario"):
                n_usuario = st.text_input("Nombre completo")
                r_usuario = st.selectbox("Rol", ["Trabajador", "Coordinador"])
                if st.form_submit_button("Registrar / Modificar"):
                    if n_usuario:
                        n_limpio = n_usuario.strip()
                        existe_u = conn.query(f"SELECT nombre FROM usuarios WHERE nombre = '{n_limpio}'", ttl=0)
                        try:
                            with conn.session as s:
                                if not existe_u.empty:
                                    s.execute(text("UPDATE usuarios SET rol = :r WHERE nombre = :n"), 
                                              {"n": n_limpio, "r": r_usuario})
                                else:
                                    s.execute(text("INSERT INTO usuarios (nombre, rol) VALUES (:n, :r)"), 
                                              {"n": n_limpio, "r": r_usuario})
                                s.commit()
                            st.success(f"Usuario {n_limpio} procesado.")
                            st.rerun()
                        except Exception:
                            st.error("Error al procesar usuario.")

            st.write("**Eliminar Usuarios:**")
            df_u = conn.query("SELECT id, nombre, rol FROM usuarios", ttl=0)
            for _, row in df_u.iterrows():
                if row['nombre'] != usuario_actual:
                    col_u, col_b = st.columns([0.8, 0.2])
                    col_u.write(f"👤 {row['nombre']} ({row['rol']})")
                    if col_b.button("🗑️ Quitar", key=f"del_u_{row['id']}"):
                        try:
                            with conn.session as s:
                                s.execute(text("DELETE FROM usuarios WHERE id=:id"), {"id": row['id']})
                                s.commit()
                            st.rerun()
                        except Exception:
                            st.error("No se pudo eliminar al usuario.")

# ==========================================
# VISTA: USUARIO (TRABAJADOR)
# ==========================================
elif rol_actual == 'Trabajador':
    st.title("🚗 Reserva Ágil de Vehículos")
    tab_reserva, tab_mis_reservas = st.tabs(["Nueva Reserva", "Mis Reservas Activas"])
    
    with tab_reserva:
        col1, col2 = st.columns(2)
        with col1: fecha_res = st.date_input("¿Qué día?", min_value=date.today())
        with col2: franja_res = st.selectbox("Franja Horaria:", ["Mañana", "Tarde", "Todo el día"])
            
        st.markdown("### Disponibilidad de Vehículos")
        query_disponibles = f"""
            SELECT v.placa, v.conductor, v.celular FROM asignaciones a
            JOIN vehiculos v ON a.placa = v.placa
            WHERE a.fecha = '{fecha_res}' AND a.placa NOT IN (
                SELECT placa FROM reservas WHERE fecha = '{fecha_res}' AND estado = 'Activa'
                AND (franja = '{franja_res}' OR franja = 'Todo el día' OR '{franja_res}' = 'Todo el día')
            )
        """
        df_disp = conn.query(query_disponibles, ttl=0)
        
        if df_disp.empty:
            st.warning("No hay vehículos disponibles para esta fecha y franja.")
        else:
            # Mostramos solo la cantidad, ocultando quiénes son
            st.success(f"✅ Hay {len(df_disp)} vehículo(s) disponible(s) para tu solicitud.")
            st.info("💡 Para garantizar la equidad, el sistema te asignará un vehículo automáticamente.")

            with st.form("form_reserva"):
                destino_res = st.text_input("Destino:")
                if st.form_submit_button("Asignar y Confirmar Reserva"):
                    if not destino_res:
                        st.error("⚠️ Ingresa el destino.")
                    else:
                        try:
                            # 1. El sistema elige un vehículo al azar usando .sample()
                            vehiculo_asignado = df_disp.sample(n=1).iloc[0]
                            placa_elegida = vehiculo_asignado['placa']

                            # 2. Guardamos la reserva en la base de datos
                            with conn.session as s:
                                s.execute(text("""
                                    INSERT INTO reservas (fecha, placa, usuario, franja, estado, destino) 
                                    VALUES (:f, :p, :u, :fr, :e, :d)
                                """), {"f": str(fecha_res), "p": placa_elegida, "u": usuario_actual, "fr": franja_res, "e": 'Activa', "d": destino_res})
                                s.commit()
                            
                            # 3. AHORA SÍ revelamos quién es el conductor asignado
                            n_cond = vehiculo_asignado['conductor']
                            st.success(f"🎉 ¡Reserva exitosa! Se te ha asignado el vehículo **{placa_elegida}** con el conductor **{n_cond}**.")
                            
                            # 4. Datos WhatsApp (Misma lógica que ya tenías)
                            c_cond = "".join(filter(str.isdigit, str(vehiculo_asignado['celular'])))
                            if len(c_cond) == 10: c_cond = "57" + c_cond
                            
                            msj_wa = f"Hola {n_cond}, soy {usuario_actual}. Reservé el vehículo {placa_elegida} para el {fecha_res}, Franja Horaria: {franja_res}. Destino: {destino_res}."
                            wa_url = f"https://wa.me/{c_cond}?text={urllib.parse.quote(msj_wa)}"
                            
                            st.markdown(f"""
                                <a href="{wa_url}" target="_blank" style="text-decoration: none;">
                                    <div style="background-color: #25D366; color: white; padding: 15px; text-align: center; border-radius: 10px; font-weight: bold; font-size: 20px; margin-top: 10px;">
                                        📱 NOTIFICAR A {n_cond.upper()} POR WHATSAPP
                                    </div>
                                </a>
                                <br>
                            """, unsafe_allow_html=True)
                            
                            st.info("Haga clic arriba para enviar el mensaje. Luego puede refrescar la página manualmente.")
                            
                        except Exception as e:
                            st.error(f"Error al reservar: {e}")

    with tab_mis_reservas:
        query_mis = f"SELECT id, fecha, placa, franja FROM reservas WHERE usuario='{usuario_actual}' AND estado='Activa'"
        df_mis = conn.query(query_mis, ttl=0)
        
        if df_mis.empty:
            st.info("No tienes reservas activas.")
        else:
            for _, row in df_mis.iterrows():
                col_info, col_btn = st.columns([0.7, 0.3])
                col_info.write(f"🚗 **{row['placa']}** | {row['fecha']} | {row['franja']}")
                
                if col_btn.button(f"🗑️ Liberar {row['placa']}", key=f"lib_{row['id']}"):
                    try:
                        # 1. Obtener datos antes de liberar para el mensaje
                        d_cond = conn.query(f"SELECT conductor, celular FROM vehiculos WHERE placa='{row['placa']}'", ttl=0)
                        
                        # 2. Liberar en DB
                        with conn.session as s:
                            s.execute(text("UPDATE reservas SET estado = 'Liberada' WHERE id = :id"), {"id": row['id']})
                            s.commit()
                        
                        st.warning(f"Vehículo {row['placa']} liberado.")

                        # 3. Mostrar botón de WhatsApp para avisar la liberación
                        if not d_cond.empty:
                            n_c = d_cond.iloc[0]['conductor']
                            c_c = "".join(filter(str.isdigit, str(d_cond.iloc[0]['celular'])))
                            if len(c_c) == 10: c_c = "57" + c_c
                            
                       
                            msj_lib = f"Hola {n_c}, te informo que el trabajador {usuario_actual} ha liberado el vehículo {row['placa']}. Está disponible nuevamente."
                            url_lib = f"https://wa.me/{c_c}?text={urllib.parse.quote(msj_lib)}"
                            
                            st.markdown(f"""
                                <a href="{url_lib}" target="_blank" style="text-decoration: none;">
                                    <div style="background-color: #FF4B4B; color: white; padding: 12px; text-align: center; border-radius: 8px; font-weight: bold; font-size: 18px;">
                                        📲 Avisar liberación a {n_c}
                                    </div>
                                </a>
                            """, unsafe_allow_html=True)
                            st.info("La lista se actualizará la próxima vez que ingreses o cambies de pestaña.")
                    except Exception:
                        st.error("No se pudo liberar.")
