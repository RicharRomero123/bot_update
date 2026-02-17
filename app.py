import streamlit as st
import pandas as pd
import plotly.express as px
import os
import io
import time
import requests 
from datetime import datetime, timezone, timedelta

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Tablero SARE Interactivo", layout="wide", page_icon="📊")

URL_API = "https://unbased-pallidly-donn.ngrok-free.dev"
FILE_PATH = "Reporte_General_Sare.xlsx"

# --- FUNCIONES DE APOYO ---
def ejecutar_actualizacion():
    status_box = st.status("🚀 Conectando con la PC local...", expanded=True)
    try:
        headers = {"ngrok-skip-browser-warning": "true"}
        respuesta = requests.get(f"{URL_API}/actualizar_datos", headers=headers, timeout=300)
        if respuesta.status_code == 200:
            with open(FILE_PATH, "wb") as f:
                f.write(respuesta.content)
            status_box.update(label="✅ ¡Actualización Exitosa!", state="complete", expanded=False)
            st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")

def obtener_info_archivo(ruta):
    timestamp = os.path.getmtime(ruta)
    dt_utc = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    tz_peru = timezone(timedelta(hours=-5))
    fecha_obj = dt_utc.astimezone(tz_peru)
    return fecha_obj.strftime("%d/%m/%Y"), fecha_obj.strftime("%H:%M:%S")

def generar_tabla_comparativa(df, col_responsable):
    if df.empty: return pd.DataFrame()
    resumen = df.groupby([col_responsable, 'Estado']).size().unstack(fill_value=0)
    for col in ['Dentro de fecha', 'Vencido']:
        if col not in resumen.columns: resumen[col] = 0
    resumen['TOTAL'] = resumen['Dentro de fecha'] + resumen['Vencido']
    return resumen.sort_values(by=['Vencido', 'TOTAL'], ascending=False)

# --- BARRA LATERAL (FILTROS) ---
with st.sidebar:
    st.title("⚙️ Filtros del Tablero")
    
    if st.button("🔄 ACTUALIZAR DESDE PC (ROBOT)", type="primary", use_container_width=True):
        ejecutar_actualizacion()
    
    st.divider()
    
    # FILTRO 1: Días de Vencimiento Dinámico
    st.subheader("📌 Regla de Negocio")
    dias_limite = st.slider("Definir umbral de 'Vencido' (Días)", 1, 60, 15)
    st.caption(f"Actualmente: >= {dias_limite} días es Vencido")

    st.divider()
    
    # Filtros de Producto (Se llenarán después de cargar la data)
    st.subheader("🔍 Filtros de Datos")

# --- CARGA DE DATOS ---
if os.path.exists(FILE_PATH):
    try:
        fecha_arch, hora_arch = obtener_info_archivo(FILE_PATH)
        st.info(f"📅 Datos actualizados el: **{fecha_arch}** a las **{hora_arch}**")

        xls = pd.ExcelFile(FILE_PATH)
        df_rec = pd.read_excel(xls, 'Data_Reclamos') if 'Data_Reclamos' in xls.sheet_names else pd.DataFrame()
        df_req = pd.read_excel(xls, 'Data_Requerimientos') if 'Data_Requerimientos' in xls.sheet_names else pd.DataFrame()

        # UNIFICAMOS PARA FILTROS GLOBALES
        df_all = pd.concat([df_rec, df_req], ignore_index=True)

        # --- APLICAR FILTRO DE PRODUCTO/SERVICIO EN SIDEBAR ---
        col_filtro_nombre = "Producto/Servicio - Proced./Admin."
        if col_filtro_nombre in df_all.columns:
            opciones_prod = sorted(df_all[col_filtro_nombre].dropna().unique().tolist())
            seleccion_prod = st.sidebar.multiselect("Filtrar por Producto/Servicio:", opciones_prod, default=opciones_prod)
            
            # Filtrar Dataframes
            df_rec = df_rec[df_rec[col_filtro_nombre].isin(seleccion_prod)]
            df_req = df_req[df_req[col_filtro_nombre].isin(seleccion_prod)]

        # --- RE-CALCULAR ESTADO SEGÚN EL SLIDER ---
        def recalcular(df):
            if not df.empty and 'Días Demora' in df.columns:
                df['Estado'] = df['Días Demora'].apply(
                    lambda x: 'Vencido' if pd.notnull(x) and x >= dias_limite else 'Dentro de fecha'
                )
            return df

        df_rec = recalcular(df_rec)
        df_req = recalcular(df_req)

        # --- INTERFAZ ---
        col_izq, col_der = st.columns(2)

        with col_izq:
            st.header("⚖️ RECLAMOS")
            if not df_rec.empty:
                vencidos = len(df_rec[df_rec['Estado'] == 'Vencido'])
                st.metric("Total Reclamos", len(df_rec), f"{vencidos} Vencidos", delta_color="inverse")
                tabla = generar_tabla_comparativa(df_rec, 'Asignado a:')
                st.dataframe(tabla, use_container_width=True)
                fig = px.pie(df_rec, names='Estado', color='Estado', hole=0.5, 
                             color_discrete_map={'Vencido': '#FF4B4B', 'Dentro de fecha': '#00CC96'})
                st.plotly_chart(fig, use_container_width=True)

        with col_der:
            st.header("📝 REQUERIMIENTOS")
            if not df_req.empty:
                vencidos = len(df_req[df_req['Estado'] == 'Vencido'])
                st.metric("Total Requerimientos", len(df_req), f"{vencidos} Vencidos", delta_color="inverse")
                tabla = generar_tabla_comparativa(df_req, 'Asignado a:')
                st.dataframe(tabla, use_container_width=True)
                fig = px.pie(df_req, names='Estado', color='Estado', hole=0.5,
                             color_discrete_map={'Vencido': '#FF4B4B', 'Dentro de fecha': '#00CC96'})
                st.plotly_chart(fig, use_container_width=True)

        # DATA RAW
        with st.expander("📂 Ver Detalles Filtrados"):
            st.write(pd.concat([df_rec, df_req]))

    except Exception as e:
        st.error(f"Error al procesar datos: {e}")
else:
    st.warning("⚠️ No hay datos. Usa el botón de la izquierda para actualizar.")
