import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import date
import urllib.parse
import plotly.express as px

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

# --- NUEVO: Aseguramos que exista la columna 'password' sin dañar la base actual ---
try:
    with conn.session as s:
        s.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS password TEXT"))
        s.commit()
except Exception:
    pass

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

# Obtenemos los nombres con ttl=0 (AHORA TRAEMOS EL PASSWORD TAMBIÉN)
usuarios_df = conn.query("SELECT id, nombre, rol, password FROM usuarios", ttl=0)
lista_usuarios = ["-- Selecciona tu nombre --"] + usuarios_df['nombre'].tolist()

usuario_actual = st.sidebar.selectbox(
    "¿Quién está ingresando?", 
    options=lista_usuarios,
    index=0 
)

if usuario_actual == "-- Selecciona tu nombre --":
    st.title("Bienvenido al Sistema de Vehículos")
    st.warning("👈 Por favor, selecciona tu nombre en el panel de la izquierda para continuar.")
    # --- BLOQUE DE CRÉDITOS EN LA BIENVENIDA ---
    st.markdown("<br><br>", unsafe_allow_html=True) 
    st.markdown(
        """
        <div style="
            background-color: #f0f2f6;
            padding: 20px;
            border-radius: 15px;
            border-left: 5px solid #FF4B4B;
            max-width: fit-content;
        ">
            <p style="margin: 0; font-size: 0.9em; color: #555;">Soporte y Desarrollo:</p>
            <h3 style="margin: 5px 0; color: #1f1f1f;">Sergio Cutiva</h3>
            <hr style="margin: 10px 0; border: 0.5px solid #ddd;">
            <p style="margin: 0; font-size: 0.85em; color: #333;">
                <b>Contacto Enel:</b> <a href="mailto:sergio.cutiva@enel.com">sergio.cutiva@enel.com</a><br>
                <b>Personal:</b> <a href="mailto:sergiocutivam@gmail.com">sergiocutivam@gmail.com</a>
            </p>
        </div>
        """, 
        unsafe_allow_html=True
    )
    st.stop() 
else:
    rol_actual = usuarios_df[usuarios_df['nombre'] == usuario_actual]['rol'].values[0]
    
    # --- CERRAR SESIÓN DE ADMIN SI SE CAMBIA DE USUARIO ---
    if "coord_user" not in st.session_state:
        st.session_state.coord_user = usuario_actual
    if st.session_state.coord_user != usuario_actual:
        st.session_state.coord_auth = False
        st.session_state.coord_user = usuario_actual
    
    # --- DETALLE PARA TU COMPAÑERA ---
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
        st.sidebar.info(f"Rol activo: **{rol_actual}**")

# ==========================================
# CRÉDITOS DEL DESARROLLADOR
# ==========================================
st.sidebar.markdown("---") 
st.sidebar.markdown(
    f"""
    <div style="
        background-color: rgba(255, 255, 255, 0.05);
        padding: 15px;
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        text-align: center;
    ">
        <p style="margin: 0; font-size: 0.8em; color: gray;">Desarrollado por:</p>
        <strong style="font-size: 1.1em; color: #FF4B4B;">Sergio Cutiva</strong>
        <p style="margin: 5px 0 0 0; font-size: 0.75em;">
            📧 <a href="mailto:sergio.cutiva@enel.com" style="text-decoration: none; color: inherit;">sergio.cutiva@enel.com</a><br>
            📧 <a href="mailto:sergiocutivam@gmail.com" style="text-decoration: none; color: inherit;">sergiocutivam@gmail.com</a>
        </p>
    </div>
    """, 
    unsafe_allow_html=True
)

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
    # --- SISTEMA DE CONTRASEÑAS ---
    if "coord_auth" not in st.session_state:
        st.session_state.coord_auth = False

    user_pass_db = usuarios_df[usuarios_df['nombre'] == usuario_actual]['password'].values[0]
    
    if not st.session_state.coord_auth:
        st.markdown("### 🔒 Autenticación de Coordinador Requerida")
        
        # CASO 1: Es la primera vez y no tiene contraseña
        if pd.isna(user_pass_db) or user_pass_db is None or str(user_pass_db).strip() == "":
            st.info("👋 Parece que es tu primera vez ingresando. Por favor, crea una contraseña para proteger tu perfil.")
            nueva_clave = st.text_input("Ingresa tu nueva contraseña:", type="password", key="new_pass")
            if st.button("Guardar y Desbloquear", use_container_width=True):
                if nueva_clave.strip():
                    try:
                        with conn.session as s:
                            s.execute(text("UPDATE usuarios SET password = :p WHERE nombre = :n"), {"p": nueva_clave, "n": usuario_actual})
                            s.commit()
                        st.session_state.coord_auth = True
                        st.success("Contraseña guardada. Ingresando...")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")
                else:
                    st.error("La contraseña no puede estar vacía.")
        
        # CASO 2: Ya tiene contraseña, se le pide para ingresar
        else:
            clave_ingresada = st.text_input("Ingresa tu contraseña de acceso:", type="password", key="login_pass")
            if st.button("Desbloquear Panel", use_container_width=True):
                if clave_ingresada == str(user_pass_db):
                    st.session_state.coord_auth = True
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta ❌")
        
        st.stop() # Congela todo lo de abajo si no está autenticado

    # SI PASÓ LA AUTENTICACIÓN: Opción para cambiar la contraseña
    with st.expander("🔑 Cambiar mi contraseña de seguridad"):
        cambio_clave = st.text_input("Escribe tu nueva contraseña:", type="password", key="change_pass")
        if st.button("Actualizar contraseña"):
            if cambio_clave.strip():
                try:
                    with conn.session as s:
                        s.execute(text("UPDATE usuarios SET password = :p WHERE nombre = :n"), {"p": cambio_clave, "n": usuario_actual})
                        s.commit()
                    st.success("¡Contraseña actualizada exitosamente!")
                except Exception as e:
                    st.error(f"Error al actualizar la contraseña: {e}")
            else:
                st.warning("Escribe una contraseña válida.")
                
    # --- FIN SISTEMA DE CONTRASEÑAS ---

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
                st.error(f"Error al guardar asignación: {e}")

    st.subheader("📊 Control Maestro de Reservas")
    
    df_res_coord = conn.query(f"""
        SELECT r.id, r.fecha, r.placa, v.conductor, r.usuario, r.franja, r.destino, r.estado 
        FROM reservas r
        JOIN vehiculos v ON r.placa = v.placa
        WHERE r.fecha='{fecha_sel}'
    """, ttl=0)
    
    if df_res_coord.empty:
        st.info(f"No hay movimientos registrados para el {fecha_sel}")
    else:
        st.write("### Vista Rápida")
        df_mostrar = df_res_coord.copy()
        df_mostrar['fecha'] = df_mostrar['fecha'].astype(str)
        
        st.dataframe(
            df_mostrar[['fecha', 'placa', 'conductor', 'usuario', 'franja', 'estado']], 
            use_container_width=True, 
            hide_index=True
        )

        st.write("### Acciones de Liberación")
        reservas_activas = df_res_coord[df_res_coord['estado'] == 'Activa']
        
        if reservas_activas.empty:
            st.success("No hay reservas activas por liberar.")
        else:
            for _, row in reservas_activas.iterrows():
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
                                s.commit() # <--- LA CORRECCIÓN CLAVE ESTÁ AQUÍ
                            st.success(f"Vehículo {p_limpia} procesado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al procesar el vehículo: {e}")
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
                    except Exception as e:
                        st.error(f"No se puede borrar el vehículo (tiene reservas asociadas): {e}")

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
                        except Exception as e:
                            st.error(f"Error al procesar usuario: {e}")

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
                        except Exception as e:
                            st.error(f"No se pudo eliminar al usuario: {e}")
                            
    # ==========================================
    # MÓDULO: ANÁLISIS Y ESTADÍSTICAS (SOLO COORDINADOR)
    # ==========================================
    st.markdown("---")
    st.title("📈 Análisis y Demanda de Vehículos")
    
    df_historico = conn.query("SELECT * FROM reservas", ttl=0)
    
    if not df_historico.empty:
        df_historico['fecha'] = pd.to_datetime(df_historico['fecha'])
        hoy = pd.to_datetime(date.today())
        
        filtro_tiempo = st.radio(
            "Selecciona el periodo de análisis:",
            ["Histórico Completo", "Hoy", "Últimos 7 días", "Este Mes", "Este Año"],
            horizontal=True
        )
        
        if filtro_tiempo == "Hoy":
            df_filtrado = df_historico[df_historico['fecha'] == hoy].copy()
        elif filtro_tiempo == "Últimos 7 días":
            df_filtrado = df_historico[df_historico['fecha'] >= (hoy - pd.Timedelta(days=7))].copy()
        elif filtro_tiempo == "Este Mes":
            df_filtrado = df_historico[(df_historico['fecha'].dt.month == hoy.month) & (df_historico['fecha'].dt.year == hoy.year)].copy()
        elif filtro_tiempo == "Este Año":
            df_filtrado = df_historico[df_historico['fecha'].dt.year == hoy.year].copy()
        else:
            df_filtrado = df_historico.copy()
            
        if df_filtrado.empty:
            st.info(f"No hay datos registrados para el filtro: {filtro_tiempo}")
        else:
            df_filtrado['turnos_usados'] = df_filtrado['franja'].apply(lambda x: 2 if x == 'Todo el día' else 1)
            total_turnos_usados = df_filtrado['turnos_usados'].sum()

            capacidad_diaria = 8
            dias_unicos = df_filtrado['fecha'].nunique()
            if dias_unicos == 0: dias_unicos = 1 
            
            total_turnos_disponibles = dias_unicos * capacidad_diaria

            col_k1, col_k2, col_k3, col_k4 = st.columns(4)
            col_k1.metric("📌 Total Reservas", len(df_filtrado), help="Número de clics de reserva")
            col_k2.metric("🔄 Turnos Consumidos", total_turnos_usados, help="Todo el día vale por 2")
            col_k3.metric("📊 Límite Operativo", total_turnos_disponibles, help=f"Basado en 8 turnos/día * {dias_unicos} días de actividad")
            
            ocupacion = (total_turnos_usados / total_turnos_disponibles * 100) if total_turnos_disponibles > 0 else 0
            color_ocupacion = "normal" if ocupacion <= 100 else "inverse"
            col_k4.metric("🔥 % Ocupación", f"{ocupacion:.1f}%",
                          delta="¡Sobredemanda!" if ocupacion > 100 else "Dentro del límite",
                          delta_color=color_ocupacion)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.subheader("🏆 Vehículos Más Demandados")
                demanda_veh = df_filtrado['placa'].value_counts().reset_index()
                demanda_veh.columns = ['Placa', 'Cantidad']
                fig_veh = px.bar(demanda_veh, x='Placa', y='Cantidad', color='Placa', text='Cantidad',
                                 color_discrete_sequence=px.colors.qualitative.Pastel)
                st.plotly_chart(fig_veh, use_container_width=True)
                
            with col_g2:
                st.subheader("🕒 Demanda por Turno (Franja)")
                demanda_franja = df_filtrado['franja'].value_counts().reset_index()
                demanda_franja.columns = ['Franja', 'Cantidad']
                fig_franja = px.pie(demanda_franja, names='Franja', values='Cantidad', hole=0.4,
                                    color_discrete_sequence=px.colors.qualitative.Set2)
                st.plotly_chart(fig_franja, use_container_width=True)

            st.subheader("📉 Evolución de Reservas en el Tiempo")
            tendencia = df_filtrado.groupby('fecha').size().reset_index(name='Reservas')
            fig_tendencia = px.line(tendencia, x='fecha', y='Reservas', markers=True, 
                                    line_shape='spline', color_discrete_sequence=['#FF4B4B'])
            fig_tendencia.add_hline(y=8, line_dash="dash", line_color="gray", 
                                    annotation_text="Límite Guía (8)", annotation_position="top left")
            st.plotly_chart(fig_tendencia, use_container_width=True)
            
            st.subheader("⚖️ Sobredemanda: Turnos Gastados vs Capacidad Máxima (8/día)")
            demanda_turnos = df_filtrado.groupby('fecha')['turnos_usados'].sum().reset_index(name='Turnos Gastados')
            
            demanda_turnos['Estado'] = demanda_turnos['Turnos Gastados'].apply(lambda x: 'Sobredemanda' if x > 8 else 'Normal')
            
            fig_sobredemanda = px.bar(demanda_turnos, x='fecha', y='Turnos Gastados', text='Turnos Gastados',
                                      color='Estado',
                                      color_discrete_map={'Normal': '#1f77b4', 'Sobredemanda': '#FF4B4B'})
            
            fig_sobredemanda.add_hline(y=8, line_dash="solid", line_color="red", 
                                       annotation_text="Límite Máximo (8 turnos)", 
                                       annotation_position="top left")
            st.plotly_chart(fig_sobredemanda, use_container_width=True)

            with st.expander("Ver Top Trabajadores (Ranking de Reservas)"):
                demanda_usu = df_filtrado.groupby('usuario').agg(
                    Reservas_Totales=('id', 'count'),
                    Turnos_Consumidos=('turnos_usados', 'sum')
                ).reset_index().sort_values(by='Turnos_Consumidos', ascending=False)
                st.dataframe(demanda_usu, hide_index=True, use_container_width=True)
    else:
        st.info("Aún no hay histórico de reservas para analizar.")

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
            st.success(f"✅ Hay {len(df_disp)} vehículo(s) disponible(s) para tu solicitud.")
            st.info("💡 Para garantizar la equidad, el sistema te asignará un vehículo automáticamente.")

            with st.form("form_reserva"):
                destino_res = st.text_input("Destino:")
                if st.form_submit_button("Asignar y Confirmar Reserva"):
                    if not destino_res:
                        st.error("⚠️ Ingresa el destino.")
                    else:
                        try:
                            vehiculo_asignado = df_disp.sample(n=1).iloc[0]
                            placa_elegida = vehiculo_asignado['placa']

                            with conn.session as s:
                                s.execute(text("""
                                    INSERT INTO reservas (fecha, placa, usuario, franja, estado, destino) 
                                    VALUES (:f, :p, :u, :fr, :e, :d)
                                """), {"f": str(fecha_res), "p": placa_elegida, "u": usuario_actual, "fr": franja_res, "e": 'Activa', "d": destino_res})
                                s.commit()
                            
                            n_cond = vehiculo_asignado['conductor']
                            st.success(f"🎉 ¡Reserva exitosa! Se te ha asignado el vehículo **{placa_elegida}** con el conductor **{n_cond}**.")
                            
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
        if "lib_pendiente" in st.session_state:
            lp = st.session_state.lib_pendiente
            st.error(f"⚠️ Has liberado el vehículo {lp['placa']}. ¡Avisa al conductor!")
            st.markdown(f"""
                <a href="{lp['url']}" target="_blank" style="text-decoration: none;">
                    <div style="background-color: #FF4B4B; color: white; padding: 15px; text-align: center; border-radius: 10px; font-weight: bold; font-size: 18px;">
                        📲 CLIC AQUÍ PARA AVISAR A {lp['conductor'].upper()}
                    </div>
                </a>
            """, unsafe_allow_html=True)
            if st.button("✅ Ya avisé / Cerrar aviso"):
                del st.session_state.lib_pendiente
                st.rerun()
            st.markdown("---")
            
        query_mis = f"""
            SELECT r.id, r.fecha, r.placa, r.franja, r.destino, v.conductor, v.celular 
            FROM reservas r
            JOIN vehiculos v ON r.placa = v.placa
            WHERE r.usuario='{usuario_actual}' AND r.estado='Activa'
        """
        df_mis = conn.query(query_mis, ttl=0)
        
        if df_mis.empty:
            st.info("No tienes reservas activas.")
        else:
            st.write("### Mis Vehículos Reservados")
            for _, row in df_mis.iterrows():
                with st.expander(f"🚗 {row['placa']} - {row['fecha']} ({row['franja']})"):
                    col_det, col_acc = st.columns([0.6, 0.4])
                    
                    with col_det:
                        st.write(f"**Conductor:** {row['conductor']}")
                        st.write(f"**Destino:** {row['destino']}")
                    
                    with col_acc:
                        c_cond = "".join(filter(str.isdigit, str(row['celular'])))
                        if len(c_cond) == 10: c_cond = "57" + c_cond
                        
                        msj_wa = f"Hola {row['conductor']}, soy {usuario_actual}. Te confirmo mi reserva del vehículo {row['placa']} para el {row['fecha']} ({row['franja']}). Destino: {row['destino']}."
                        wa_url = f"https://wa.me/{c_cond}?text={urllib.parse.quote(msj_wa)}"
                        
                        st.markdown(f"""
                            <a href="{wa_url}" target="_blank" style="text-decoration: none;">
                                <div style="background-color: #25D366; color: white; padding: 8px; text-align: center; border-radius: 5px; font-weight: bold; margin-bottom: 10px;">
                                    📱 Avisar por WhatsApp
                                </div>
                            </a>
                        """, unsafe_allow_html=True)

                        if st.button(f"🗑️ Liberar Vehículo", key=f"lib_v2_{row['id']}", use_container_width=True):
                            try:
                                with conn.session as s:
                                    s.execute(text("UPDATE reservas SET estado = 'Liberada' WHERE id = :id"), {"id": row['id']})
                                    s.commit()
                                
                                st.warning(f"Vehículo {row['placa']} liberado.")
                                
                                msj_lib = f"Hola {row['conductor']}, el trabajador {usuario_actual} ha liberado el vehículo {row['placa']}. Ya no está reservado."
                                url_lib = f"https://wa.me/{c_cond}?text={urllib.parse.quote(msj_lib)}"
                                
                                st.session_state.lib_pendiente = {
                                    "placa": row['placa'],
                                    "conductor": row['conductor'],
                                    "url": url_lib
                                }
                                st.rerun()
                            except Exception as e:
                                st.error(f"No se pudo liberar: {e}")
