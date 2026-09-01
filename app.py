import streamlit as st

# Configuración de la página para celulares con enfoque dinámico por filas
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
st.write("Calcula el despiece real para cualquier tipo de material lineal en tu taller, incluyendo la merma del disco.")

# Grosor del disco en la parte superior
espesor_disco_cm = st.number_input("Espesor del disco de corte (cm):", min_value=0.0, max_value=1.0, value=0.3, step=0.1)

# Inicializar estados de la aplicación si no existen
if 'materiales' not in st.session_state:
    st.session_state.materiales = []
if 'num_filas' not in st.session_state:
    st.session_state.num_filas = 1  # Empezamos con una sola fila de corte

# Formulario principal
with st.form("Formulario Material"):
    st.subheader("➕ Configurar nuevo material")
    nombre = st.text_input("Nombre del material:", placeholder="Ej: Tubo Rectangular 1 1/2 x 3/4")
    largo_m = st.number_input("Longitud de la unidad comercial (metros):", min_value=1.0, max_value=12.0, value=6.0, step=0.5)
    
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
    # Botón de calcular dentro del formulario
    submit = st.form_submit_button("⚡ Calcular y Guardar Material")

# BOTÓN DE AGREGAR FILA (Debe estar FUERA del formulario para que pueda actualizar la pantalla)
if st.button("➕ Agregar otra medida"):
    st.session_state.num_filas += 1
    st.rerun()

# Procesar los datos si el usuario hunde el botón de calcular
if submit and nombre:
    cortes_expandidos = []
    for med, cant in zip(medidas_detectadas, cantidades_detectadas):
        if med > 0 and cant > 0:
            cortes_expandidos.extend([med] * cant)
            
    if cortes_expandidos:
        st.session_state.materiales.append({
            "nombre": nombre,
            "largo_cm": largo_m * 100,
            "largo_m": largo_m,
            "cortes": cortes_expandidos
        })
        # Resetear el contador de filas para el próximo material
        st.session_state.num_filas = 1
        st.success(f"¡{nombre} calculado con éxito abajo!")
        st.rerun()
    else:
        st.error("⚠️ Debes rellenar al menos una medida y cantidad mayor a cero.")

# --- MOSTRAR RESULTADOS ABAJO ---
if st.session_state.materiales:
    st.markdown("---")
    st.header("📊 Lista de Materiales y Despiece")
    
    if st.button("🗑️ Borrar todo y empezar de nuevo"):
        st.session_state.materiales = []
        st.session_state.num_filas = 1
        st.rerun()
        
    for idx, mat in enumerate(st.session_state.materiales):
        with st.expander(f"📦 {mat['nombre']} (Unidades de {mat['largo_m']}m)", expanded=True):
            tubos_calculados = optimizar_cortes(mat['cortes'], mat['largo_cm'], espesor_disco_cm)
            
            st.metric(label="Total de Unidades a comprar", value=f"{len(tubos_calculados)} unidades")
            
            for i, (tubo, sobrante) in enumerate(tubos_calculados, 1):
                sobrante_real = sobrante + espesor_disco_cm
                st.write(f"**Unidad {i}:** {tubo} | *Sobrante libre:* {sobrante_real:.1f} cm")
