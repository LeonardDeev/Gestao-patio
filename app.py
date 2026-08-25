import streamlit as st
import pandas as pd
from datetime import datetime

# Configuração da página web
st.set_page_config(page_title="Gestão de Pátio Renault", layout="wide")

st.title("🚗 Sistema de Gestão e Separação de Pátio")

# 1. Campo no menu lateral para conectar a Planilha do Google Sheets
with st.sidebar:
    st.header("⚙️ Conexão com Google Sheets")
    url_planilha = st.text_input(
        "Link da Planilha do Google Sheets:", 
        placeholder="Cole o link de compartilhamento aqui"
    )
    st.caption("A planilha deve estar compartilhada como 'Qualquer pessoa com o link - Editor'.")

def extrair_sheet_id(url):
    try:
        if "/d/" in url:
            return url.split("/d/")[1].split("/")[0]
    except:
        return None
    return None

sheet_id = extrair_sheet_id(url_planilha) if url_planilha else None

if not sheet_id:
    st.info("👈 Por favor, cole o link da sua Planilha do Google Sheets no menu lateral para carregar o pátio.")
    st.stop()

# URL de exportação CSV para leitura direta da aba 'Patio'
url_patio_csv = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet=Patio"

# 2. Carregamento dos dados da planilha
@st.cache_data(ttl=3) # Atualiza a cada 3 segundos
def carregar_dados():
    try:
        df_p = pd.read_csv(url_patio_csv)
        # Limpeza e formatação dos chassis (6 dígitos numéricos)
        df_p['Chassi'] = df_p['Chassi'].fillna('[ VAZIO ]').astype(str).str.strip()
        # Garante 6 dígitos com zeros à esquerda se for número (ex: 012345)
        df_p['Chassi'] = df_p['Chassi'].apply(lambda x: x.zfill(6) if x.isdigit() and len(x) < 6 else x)
        return df_p
    except Exception as e:
        st.error(f"Erro ao ler a aba 'Patio'. Verifique o link e se a aba se chama exatamente 'Patio'. Detalhes: {e}")
        return pd.DataFrame()

df_lido = carregar_dados()

# Montagem do Pátio Completo Base (Ala A (Muro), B, C, D, E | 60 Vagas por ala)
alas = ["Ala A (Muro)", "Ala B", "Ala C", "Ala D", "Ala E"]
vagas_por_ala = 60  # Atualizado para 60 vagas por ala (total de 300 vagas)

estrutura_base = []
for ala in alas:
    for pos in range(1, vagas_por_ala + 1):
        estrutura_base.append({"Ala": ala, "Posicao": pos, "Chassi": "[ VAZIO ]"})

df_patio = pd.DataFrame(estrutura_base)

# Mescla os dados lidos da planilha na estrutura completa
if not df_lido.empty and set(['Ala', 'Posicao', 'Chassi']).issubset(df_lido.columns):
    for _, row in df_lido.iterrows():
        mask = (df_patio['Ala'] == str(row['Ala']).strip()) & (df_patio['Posicao'] == int(row['Posicao']))
        chassi_val = str(row['Chassi']).strip()
        if chassi_val != "" and chassi_val != "nan":
            df_patio.loc[mask, 'Chassi'] = chassi_val

# 3. Área de Busca e Separação do Dia
st.subheader("🔍 Localizar Carros para Embarque")
entrada_texto = st.text_area(
    "Digite os Chassis (6 dígitos numéricos, um por linha):", 
    height=120, 
    placeholder="Ex:\n123456\n654321\n098765"
)

if st.button("🔎 Localizar Veículos", type="primary"):
    # Normaliza a busca para 6 dígitos numéricos
    lista_busca = []
    for c in entrada_texto.split('\n'):
        item = c.strip()
        if item:
            if item.isdigit() and len(item) < 6:
                item = item.zfill(6) # Adiciona zeros à esquerda se necessário
            lista_busca.append(item)
    
    if lista_busca:
        encontrados = df_patio[df_patio['Chassi'].isin(lista_busca) & (df_patio['Chassi'] != "[ VAZIO ]")].copy()
        
        chassis_encontrados = encontrados['Chassi'].tolist()
        nao_encontrados = [c for c in lista_busca if c not in chassis_encontrados]

        if not encontrados.empty:
            st.session_state['encontrados_busca'] = encontrados
            st.session_state['nao_encontrados_busca'] = nao_encontrados
        else:
            st.warning("Nenhum dos chassis informados foi localizado em vagas ocupadas.")
            st.session_state['encontrados_busca'] = pd.DataFrame()
            st.session_state['nao_encontrados_busca'] = lista_busca
    else:
        st.info("Digite ao menos um chassi de 6 dígitos para realizar a busca.")

# Exibição dos Resultados da Busca
if 'encontrados_busca' in st.session_state and not st.session_state['encontrados_busca'].empty:
    encontrados = st.session_state['encontrados_busca']
    st.success(f"**{len(encontrados)} veículo(s) localizado(s) no pátio!**")
    st.dataframe(encontrados[['Chassi', 'Ala', 'Posicao']], use_container_width=True)
    
    # Modal / Pop-up de Confirmação para Retirada
    @st.dialog("⚠️ Confirmar Retirada do Pátio")
    def popup_confirmacao():
        st.write("Retire os veículos abaixo das vagas para envio às lojas:")
        for _, r in encontrados.iterrows():
            st.markdown(f"- **Chassi: {r['Chassi']}** ➔ {r['Ala']}, Vaga **{r['Posicao']:02d}**")
            
        col1, col2 = st.columns(2)
        if col1.button("✅ Confirmar Retirada", type="primary"):
            st.success("Retirada confirmada! Apague ou remova o chassi da planilha para liberar a vaga no sistema.")
            if 'encontrados_busca' in st.session_state:
                del st.session_state['encontrados_busca']
            st.rerun()

        if col2.button("❌ Cancelar"):
            st.rerun()

    if st.button("🚚 Processar Retirada dos Veículos"):
        popup_confirmacao()

if 'nao_encontrados_busca' in st.session_state and st.session_state['nao_encontrados_busca']:
    st.warning(f"Chassis não localizados no pátio: {', '.join(st.session_state['nao_encontrados_busca'])}")

st.divider()

# 4. Visualização em Colunas (Grade do Pátio com Scroll)
st.subheader("📍 Visão Geral do Pátio (Alas A até E)")
alas_unicas = sorted(df_patio['Ala'].unique())
colunas_alas = st.columns(len(alas_unicas))

for idx, ala in enumerate(alas_unicas):
    with colunas_alas[idx]:
        st.markdown(f"### {ala}")
        dados_ala = df_patio[df_patio['Ala'] == ala].sort_values('Posicao')
        
        with st.container(height=450):
            for _, row in dados_ala.iterrows():
                chassi_val = str(row['Chassi']).strip()
                esta_ocupado = chassi_val != "" and chassi_val != "[ VAZIO ]" and chassi_val != "nan"
                cor = "🔴" if esta_ocupado else "⚪"
                texto_chassi = chassi_val if esta_ocupado else "[ VAZIO ]"
                st.text(f"{cor} Pos {int(row['Posicao']):02d}: {texto_chassi}")
