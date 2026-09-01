import streamlit as st

# Configuración de la página para celulares con combo box dinámico
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
st.write("Agrega múltiples materiales y calcula el despiece de tu proyecto en tiempo real.")

# Grosor del disco en la parte superior
espesor_disco_cm = st.number_input("Espesor del disco de corte (cm):", min_value=0.0, max_value=1.0, value=0.3, step=0.1)

# --- INICIALIZAR MEMORIA DE LA SESIÓN ---
if 'materiales' not in st.session_state:
    st.session_state.materiales = []
if 'num_filas' not in st.session_state:
    st.session_state.num_filas = 1

# Lista de materiales predeterminados que siempre usas
if 'base_materiales' not in st.session_state:
    st.session_state.base_materiales = [
        "Tubo 3/4 x 3/4",
        "Tubo 1½ x 3/4",
        "Tubo ½ x ½",
        "➕ Agregar material nuevo..."
    ]

# --- FORMULARIO PRINCIPAL ---
with st.form("Formulario Material"):
    st.subheader("➕ Configurar Material")
    
    # 📦 COMBO BOX (Selectbox) para elegir el material
    seleccion_material = st.selectbox(
        "Selecciona el material:",
        st.session_state.base_materiales
    )
    
    # Si elige "Agregar material nuevo...", se abre una casilla de texto para escribirlo
    nombre_final = ""
    if seleccion_material == "➕ Agregar material nuevo...":
        nombre_nuevo = st.text_input("Escribe el nombre del nuevo material:", placeholder="Ej: Ángulo 1x1")
        nombre_final = nombre_nuevo.strip()
    else:
        nombre_final = seleccion_material

    largo_m = st.number_input("Longitud de la barra comercial (metros):", min_value=1.0, max_value=12.0, value=6.0, step=0.5)
    
    st.markdown("---")
    st.markdown("**📏 Medidas de los cortes requeridos:**")
    
    medidas_detectadas = []
    cantidades_detectadas = []
    
    # Generar filas dinámicas
    for i in range(st.session_state.num_filas):
        col1, col2 = st.columns(2)
        with col1:
            medida = st.number_input(f"Tamaño Corte {i+1} (cm):", min_value=0.0, value=0.0, key=f"med_{i}")
            medidas_detectadas.append(medida)
        with col2:
            cantidad = st.number_input(f"Cantidad del Corte {i+1}:", min_value=0, value=0, key=f"cant_{i}")
            cantidades_detectadas.append(cantidad)
            
    st.markdown("---")
    submit = st.form_submit_button("📥 Agregar este Material a la Lista")

# BOTÓN DE AGREGAR FILA DE CORTE (Fuera del formulario)
if st.button("➕ Añadir otra medida a este material"):
    st.session_state.num_filas += 1
    st.rerun()

# --- PROCESAR E INYECTAR EN LA LISTA ---
if submit and nombre_final:
    cortes_expandidos = []
    for med, cant in zip(medidas_detectadas, cantidades_detectadas):
        if med > 0 and cant > 0:
            cortes_expandidos.extend([med] * cant)
            
    if cortes_expandidos:
        # 📝 MEMORIA FUTURA: Si el usuario escribió un material nuevo, lo guardamos en el Combo Box para siempre
        if seleccion_material == "➕ Agregar material nuevo..." and nombre_final not in st.session_state.base_materiales:
            # Lo insertamos antes de la última opción ("➕ Agregar material nuevo...")
            st.session_state.base_materiales.insert(-1, nombre_final)
            
        # Guardamos en el proyecto actual
        st.session_state.materiales.append({
            "nombre": nombre_final,
            "largo_cm": largo_m * 100,
            "largo_m": largo_m,
            "cortes": cortes_expandidos
        })
        
        st.session_state.num_filas = 1
        st.success(f"✅ ¡{nombre_final} guardado y agregado a la lista general abajo!")
        st.rerun()
    else:
        st.error("⚠️ Debes rellenar al menos una medida y cantidad mayor a cero.")

# --- MOSTRAR RESULTADOS ACUMULADOS ABAJO ---
if st.session_state.materiales:
    st.markdown("---")
    st.header("📊 Proyecto Completo: Despiece por Material")
    
    if st.button("🗑️ Borrar todo el proyecto y empezar de nuevo"):
        st.session_state.materiales = []
        st.session_state.num_filas = 1
        st.rerun()
        
    for idx, mat in enumerate(st.session_state.materiales):
        with st.expander(f"📦 {mat['nombre']} (Barras de {mat['largo_m']}m)", expanded=True):
            tubos_calculados = optimizar_cortes(mat['cortes'], mat['largo_cm'], espesor_disco_cm)
            
            st.metric(label="Total de unidades a comprar", value=f"{len(tubos_calculados)} tubos")
            
            for i, (tubo, sobrante) in enumerate(tubos_calculados, 1):
                sobrante_real = sobrante + espesor_disco_cm
                st.write(f"**Tubo {i}:** {tubo} | *Sobrante libre:* {sobrante_real:.1f} cm")
