import streamlit as st
import streamlit.components.v1 as components

# ⚙️ 1. CONFIGURACIÓN DE LA PÁGINA (Ícono para la pestaña del navegador)
st.set_page_config(page_title="Optimero Taller", page_icon="🛠️", layout="centered")

# 📱 2. INYECCIÓN PWA: Truco para forzar el ícono profesional en la pantalla de inicio del celular
icono_url = "https://flaticon.com"

html_pwa = f"""
<head>
    <!-- Configuración para iPhone / iOS -->
    <link rel="apple-touch-icon" href="{icono_url}">
    <meta name="apple-mobile-web-app-title" content="Optimero Taller">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    
    <!-- Configuración para Android / Chrome -->
    <link rel="icon" sizes="192x192" href="{icono_url}">
    <link rel="icon" sizes="512x512" href="{icono_url}">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#0E1117">
</head>
"""
# Inyectamos el bloque HTML en la cabecera de la aplicación
components.html(html_pwa, height=0, width=0)


# --- 3. ALGORITMO DE OPTIMIZACIÓN ---
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

# --- INICIALIZAR MEMORIA GLOBAL ---
if 'proyectos' not in st.session_state:
    st.session_state.proyectos = {{
        "Proyecto Demo": []
    }}

if 'proyecto_activo' not in st.session_state:
    st.session_state.proyecto_activo = "Proyecto Demo"

if 'num_filas' not in st.session_state:
    st.session_state.num_filas = 1

if 'limpiar_inputs' not in st.session_state:
    st.session_state.limpiar_inputs = False

if 'base_materiales' not in st.session_state:
    st.session_state.base_materiales = ["Tubo 3/4 x 3/4", "Tubo 1½ x 3/4", "Tubo ½ x ½", "➕ Agregar material nuevo..."]

# --- SECCIÓN 1: GESTIÓN DE PROYECTOS (COMBO BOX SUPERIOR) ---
st.title("🛠️ Optimizador de Cortes Profesional")
st.markdown("---")

st.subheader("📁 Gestión de Proyectos")
col_proj1, col_proj2 = st.columns(2)

with col_proj1:
    lista_nombres_proyectos = list(st.session_state.proyectos.keys())
    proyecto_seleccionado = st.selectbox(
        "Buscar / Seleccionar Proyecto:",
        options=lista_nombres_proyectos,
        index=lista_nombres_proyectos.index(st.session_state.proyecto_activo)
    )
    if proyecto_seleccionado != st.session_state.proyecto_activo:
        st.session_state.proyecto_activo = proyecto_seleccionado
        st.session_state.num_filas = 1
        st.rerun()

with col_proj2:
    st.write("") 
    st.write("") 
    if st.button("🗑️ Borrar Proyecto", use_container_width=True):
        if len(st.session_state.proyectos) > 1:
            nombre_a_borrar = st.session_state.proyecto_activo
            del st.session_state.proyectos[nombre_a_borrar]
            st.session_state.proyecto_activo = list(st.session_state.proyectos.keys())
            st.toast(f"Proyecto '{nombre_a_borrar}' eliminado", icon="🗑️")
        else:
            st.session_state.proyectos[st.session_state.proyecto_activo] = []
            st.toast("Se limpiaron los materiales del proyecto único", icon="🧹")
        st.session_state.num_filas = 1
        st.rerun()

with st.expander("➕ Crear Nuevo Proyecto en Blanco", expanded=False):
    nuevo_nombre_proyecto = st.text_input("Nombre del nuevo proyecto:", placeholder="Ej: Estructuras Metálicas")
    if st.button("🚀 Inicializar Proyecto Vacío"):
        if nuevo_nombre_proyecto.strip() and nuevo_nombre_proyecto.strip() not in st.session_state.proyectos:
            nombre_limpio = nuevo_nombre_proyecto.strip()
            st.session_state.proyectos[nombre_limpio] = []
            st.session_state.proyecto_activo = nombre_limpio
            st.session_state.num_filas = 1
            st.success(f"¡Proyecto '{nombre_limpio}' creado!")
            st.rerun()
        else:
            st.error("Nombre inválido o el proyecto ya existe.")

st.markdown(f"**📍 Trabajando en:** `{st.session_state.proyecto_activo}`")
st.markdown("---")

espesor_disco_cm = st.number_input("Espesor del disco de corte (cm):", min_value=0.0, max_value=1.0, value=0.3, step=0.1)

# --- SECCIÓN 2: FORMULARIO PARA AGREGAR MATERIALES ---
with st.form("Formulario Material"):
    st.subheader("📦 Añadir Material al Proyecto")
    
    seleccion_material = st.selectbox("Selecciona el material:", st.session_state.base_materiales)
    
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
    
    for i in range(st.session_state.num_filas):
        col1, col2 = st.columns(2)
        with col1:
            medida = st.number_input(f"Tamaño Corte {i+1} (cm):", min_value=0.0, value=0.0, key=f"med_{i}_{st.session_state.limpiar_inputs}")
            medidas_detectadas.append(medida)
        with col2:
            cantidad = st.number_input(f"Cantidad del Corte {i+1}:", min_value=0, value=0, key=f"cant_{i}_{st.session_state.limpiar_inputs}")
            cantidades_detectadas.append(cantidad)
            
    st.markdown("---")
    submit = st.form_submit_button("📥 Guardar Material en este Proyecto")

if st.button("➕ Añadir otra medida a este material"):
    st.session_state.num_filas += 1
    st.session_state.limpiar_inputs = not st.session_state.limpiar_inputs
    st.rerun()

if submit and nombre_final:
    cortes_expandidos = []
    for med, cant in zip(medidas_detectadas, cantidades_detectadas):
        if med > 0 and cant > 0:
            cortes_expandidos.extend([med] * cant)
            
    if cortes_expandidos:
        if seleccion_material == "➕ Agregar material nuevo..." and nombre_final not in st.session_state.base_materiales:
            st.session_state.base_materiales.insert(-1, nombre_final)
            
        st.session_state.proyectos[st.session_state.proyecto_activo].append({
            "nombre": nombre_final,
            "largo_cm": largo_m * 100,
            "largo_m": largo_m,
            "cortes": cortes_expandidos
        })
        
        st.session_state.num_filas = 1
        st.session_state.limpiar_inputs = not st.session_state.limpiar_inputs
        st.toast(f"Material añadido a {st.session_state.proyecto_activo}", icon="✅")
        st.rerun()
    else:
        st.error("⚠️ Debes rellenar al menos una medida y cantidad mayor a cero.")

# --- SECCIÓN 3: MOSTRAR RESULTADOS ---
materiales_proyecto_actual = st.session_state.proyectos[st.session_state.proyecto_activo]

if materiales_proyecto_actual:
    st.markdown("---")
    st.header(f"📊 Despiece de: {st.session_state.proyecto_activo}")
    
    for idx, mat in enumerate(materiales_proyecto_actual):
        tubos_calculados = optimizar_cortes(mat['cortes'], mat['largo_cm'], espesor_disco_cm)
        total_unidades = len(tubos_calculados)
        
        titulo_pestana = f"📦 {mat['nombre']} (Barras de {mat['largo_m']}m) ➡️ Requiere: {total_unidades} tubos"
        
        with st.expander(titulo_pestana, expanded=False):
            st.metric(label="Total de unidades a comprar", value=f"{total_unidades} tubos")
            for i, (tubo, sobrante) in enumerate(tubos_calculados, 1):
                sobrante_real = sobrante + espesor_disco_cm
                st.write(f"**Tubo {i}:** {tubo} | *Sobrante libre:* {sobrante_real:.1f} cm")
