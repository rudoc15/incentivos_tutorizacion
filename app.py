import streamlit as st
import pandas as pd
import numpy as np

# Configuración de la página
st.set_page_config(
    page_title="Gestión de Incentivos de Tutorización",
    page_icon="🎓",
    layout="wide"
)

# -----------------------------------------------------------------------------
# Carga y Procesamiento de Datos
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    file_path = "Dataset para IA.xlsx"
    df = pd.read_excel(file_path, sheet_name="Nueva Tabla Madre")
    
    # Mapeo de Becario y Tutor
    df['Becario_Nombre'] = df.iloc[:, 0].astype(str).str.strip()
    df['Becario_Apellidos'] = df.iloc[:, 1].astype(str).str.strip()
    df['Becario_Completo'] = df['Becario_Nombre'] + " " + df['Becario_Apellidos']
    
    tutor_col = 'Tutor' if 'Tutor' in df.columns else df.columns[3]
    df['Tutor'] = df[tutor_col].astype(str).str.strip()
    
    # Requisito 1: Duración en meses (>= 3 meses)
    df['Duracion_Meses'] = pd.to_numeric(df['Duración'], errors='coerce').fillna(0)
    
    # Requisito 2: Nota de evaluación del becario/a (>= 8)
    df['Nota_Evaluacion'] = pd.to_numeric(df['SATISFACCIÓN'], errors='coerce')
    
    # Requisito 3: Cuestionario respondido por el tutor (valor numérico)
    df['Cuestionario_Tutor_Num'] = pd.to_numeric(df['DESEMPEÑO'], errors='coerce')
    df['Respondio_Cuestionario'] = df['Cuestionario_Tutor_Num'].notna()
    
    # Determinación del Curso Académico (01/09 a 31/08)
    df['ALTA_DT'] = pd.to_datetime(df['ALTA'], errors='coerce')
    
    def get_curso_academico(fecha):
        if pd.isna(fecha):
            return "Sin Fecha"
        year = fecha.year
        if fecha.month >= 9:
            return f"{year}/{year+1}"
        else:
            return f"{year-1}/{year}"
            
    df['Curso_Academico'] = df['ALTA_DT'].apply(get_curso_academico)
    
    # Verificación Criterios
    df['Cumple_Req1_Dias'] = df['Duracion_Meses'] >= 3
    df['Cumple_Req2_Nota'] = df['Nota_Evaluacion'] >= 8.0
    df['Cumple_Req3_Cuestionario'] = df['Respondio_Cuestionario']
    
    df['Elegible_Individual'] = (
        df['Cumple_Req1_Dias'] & 
        df['Cumple_Req2_Nota'] & 
        df['Cumple_Req3_Cuestionario']
    )
    
    # Co-tutorización (Medio incentivo si hay más de 1 tutor)
    tutores_por_becario = df.groupby('Becario_Completo')['Tutor'].transform('nunique')
    df['Incentivo_Base'] = np.where(tutores_por_becario > 1, 0.5, 1.0)
    
    return df

try:
    df_data = load_data()
except Exception as e:
    st.error(f"Error al cargar el archivo de datos: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# Interfaz de Usuario
# -----------------------------------------------------------------------------
st.title("🎓 Sistema de Evaluación e Incentivos de Tutorización")
st.markdown("Herramienta para determinar la asignación de incentivos por tutorización de prácticas.")

st.sidebar.header("🔍 Consultas y Búsqueda")

lista_tutores = ["-- Seleccionar Tutor/a --"] + sorted(df_data['Tutor'].dropna().unique().tolist())
lista_becarios = ["-- Seleccionar Becario/a --"] + sorted(df_data['Becario_Completo'].dropna().unique().tolist())

tutor_seleccionado = st.sidebar.selectbox("Nombre del Tutor/a:", lista_tutores)
becario_seleccionado = st.sidebar.selectbox("Nombre del Becario/a:", lista_becarios)

btn_historico = st.sidebar.button("📜 Ver Histórico del Tutor/a")

if tutor_seleccionado != "-- Seleccionar Tutor/a --" or becario_seleccionado != "-- Seleccionar Becario/a --":
    st.subheader("📋 Estado de Criterios por Practicante / Tutor")
    filtro = df_data.copy()
    if tutor_seleccionado != "-- Seleccionar Tutor/a --":
        filtro = filtro[filtro['Tutor'] == tutor_seleccionado]
    if becario_seleccionado != "-- Seleccionar Becario/a --":
        filtro = filtro[filtro['Becario_Completo'] == becario_seleccionado]
        
    st.dataframe(
        filtro[[
            'Tutor', 'Becario_Completo', 'Curso_Academico', 'Duracion_Meses', 
            'Nota_Evaluacion', 'Respondio_Cuestionario', 'Elegible_Individual'
        ]].rename(columns={
            'Becario_Completo': 'Becario/a',
            'Duracion_Meses': 'Duración (Meses)',
            'Nota_Evaluacion': 'Nota Becario (≥8)',
            'Respondio_Cuestionario': 'Cuestionario Cumplimentado',
            'Elegible_Individual': '¿Elegible?'
        }),
        use_container_width=True
    )

if btn_historico:
    if tutor_seleccionado == "-- Seleccionar Tutor/a --":
        st.error("Por favor, selecciona un tutor/a en el panel lateral.")
    else:
        st.divider()
        st.header(f"📊 Histórico del Tutor/a: {tutor_seleccionado}")
        
        df_tutor = df_data[df_data['Tutor'] == tutor_seleccionado].copy()
        
        # Eliminar duplicados por becario (sin repetir incentivo)
        df_tutor = df_tutor.sort_values(by=['Nota_Evaluacion'], ascending=False)
        df_tutor_unicos = df_tutor.drop_duplicates(subset=['Becario_Completo']).copy()
        
        df_tutor_unicos['Incentivo_Concedido'] = np.where(
            df_tutor_unicos['Elegible_Individual'], 
            df_tutor_unicos['Incentivo_Base'], 
            0.0
        )
        
        resumen_curso = df_tutor_unicos.groupby('Curso_Academico').agg(
            Incentivos_Elegibles=('Incentivo_Concedido', 'sum'),
            Evaluacion_Promedio=('Nota_Evaluacion', 'mean'),
            Becarios_Tutorizados=('Becario_Completo', 'count')
        ).reset_index()
        
        # Límite máximo de 6 por curso académico
        resumen_curso['Incentivos_Finales_Abonar'] = resumen_curso['Incentivos_Elegibles'].apply(lambda x: min(x, 6.0))
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Becarios Tutorizados", int(len(df_tutor_unicos)))
        col2.metric("Evaluación Promedio", f"{df_tutor['Nota_Evaluacion'].mean():.2f} / 10")
        col3.metric("Total Incentivos Aprobados", f"{resumen_curso['Incentivos_Finales_Abonar'].sum():.1f}")
        
        st.subheader("📅 Resumen por Curso Académico")
        st.dataframe(resumen_curso, use_container_width=True)