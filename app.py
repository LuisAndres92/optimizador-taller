import streamlit as st

# Configuración de la página para celulares con enfoque multi-material acumulativo
st.set_page_config(page_title="Optimero Taller", page_icon="🛠️", layout="centered")

def optimizar_cortes(cortes, longitud_tubo_cm, espesor_disco_cm):
    cortes.sort(reverse=True)
    tubos = []
    for corte in cortes:
        encontrado = False
        for i, (tubo, espacio) in enumerate(tubos):
            if espacio >= (corte + espesor_disco_cm):
                tubo.append(corte)
                tubos[i] = (tubo, espacio - corte - espesor_disco_cm)
                encontrado = True
                break
        if not encontrado:
            tubos.append(([corte], longitud_tubo_cm - corte - espesor_disco_cm))
    return tubos

# --- INTERFAZ DINÁMICA DE LA APLICACIÓN ---
st.title("🛠️ Optimizador de Cortes Profesional")
st.write("Agrega múltiples tipos de materiales y calcula el despiece completo de tu proyecto en tiempo real.")

# Grosor del disco en la parte superior (aplica para todos los cortes)
espesor_disco_cm = st.number_input("Espesor del disco de corte (cm):", min_value=0.0, max_value=1.0, value=0.3, step=0.1)

# Inicializar estados de la aplicación si no existen
if 'materiales' not in st.session_state:
    st.session_state.materiales = []
if 'num_filas' not in st.session_state:
    st.session_state.num_filas = 1  # Empezamos con una sola fila de corte para el material actual

# Formulario principal para configurar un material a la vez
with st.form("Formulario Material"):
    st.subheader("➕ Configurar Material")
    nombre = st.text_input("Nombre del material:", placeholder="Ej: Tubo 3/4 x 3/4")
    largo_m = st.number_input("Longitud de la barra comercial (metros):", min_value=1.0, max_value=12.0, value=6.0, step=0.5)
    
    st.markdown("---")
    st.markdown("**📏 Medidas de los cortes requeridos:**")
    
    # Listas para capturar lo que el usuario digite en cada fila dinámica
    medidas_detectadas = []
    cantidades_detectadas = []
    
    # Generar de forma dinámica las filas en base al contador de la sesión
    for i in range(st.session_state.num_filas):
        col1, col2 = st.columns(2)
        with col1:
            medida = st.number_input(f"Tamaño Corte {i+1} (cm):", min_value=0.0, value=0.0, key=f"med_{i}")
            medidas_detectadas.append(medida)
        with col2:
            cantidad = st.number_input(f"Cantidad del Corte {i+1}:", min_value=0, value=0, key=f"cant_{i}")
            cantidades_detectadas.append(cantidad)
            
    st.markdown("---")
    # Botón para procesar y añadir el material a la lista global
    submit = st.form_submit_button("📥 Agregar este Material a la Lista")

# BOTÓN DE AGREGAR FILA DE CORTE (Debe estar FUERA del formulario para actualizar la pantalla)
if st.button("➕ Añadir otra medida a este material"):
    st.session_state.num_filas += 1
    st.rerun()

# Procesar los datos si el usuario hunde el botón de guardar
if submit and nombre:
    cortes_expandidos = []
    for med, cant in zip(medidas_detectadas, cantidades_detectadas):
        if med > 0 and cant > 0:
            cortes_expandidos.extend([med] * cant)
            
    if cortes_expandidos:
        # Añadimos el material con todos sus datos a la lista acumulativa de la sesión
        st.session_state.materiales.append({
            "nombre": nombre,
            "largo_cm": largo_m * 100,
            "largo_m": largo_m,
            "cortes": cortes_expandidos
        })
        # Reseteamos el contador de filas para que el siguiente material empiece limpio desde 1
        st.session_state.num_filas = 1
        st.success(f"✅ ¡{nombre} agregado a la lista general abajo!")
        st.rerun()
    else:
        st.error("⚠️ Debes rellenar al menos una medida y cantidad mayor a cero.")

# --- MOSTRAR RESULTADOS ACUMULADOS ABAJO ---
if st.session_state.materiales:
    st.markdown("---")
    st.header("📊 Proyecto Completo: Despiece por Material")
    
    # Botón general para limpiar todo el proyecto actual
    if st.button("🗑️ Borrar todo el proyecto y empezar de nuevo"):
        st.session_state.materiales = []
        st.session_state.num_filas = 1
        st.rerun()
        
    # El programa recorre y muestra el desglose de CADA material guardado
    for idx, mat in enumerate(st.session_state.materiales):
        with st.expander(f"📦 {mat['nombre']} (Barras de {mat['largo_m']}m)", expanded=True):
            tubos_calculados = optimizar_cortes(mat['cortes'], mat['largo_cm'], espesor_disco_cm)
            
            st.metric(label="Total de unidades a comprar", value=f"{len(tubos_calculados)} tubos")
            
            for i, (tubo, sobrante) in enumerate(tubos_calculados, 1):
                sobrante_real = sobrante + espesor_disco_cm
                st.write(f"**Tubo {i}:** {tubo} | *Sobrante libre:* {sobrante_real:.1f} cm")
