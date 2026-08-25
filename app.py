import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
import json
from google.oauth2.service_account import Credentials

# Configuração da página web
st.set_page_config(page_title="Gestão de Pátio Renault", layout="wide")

st.title("🚗 Sistema de Gestão e Separação de Pátio")

# 1. Autenticação Segura com o Google Sheets via Service Account
@st.cache_resource
def conectar_google_sheets():
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        creds_data = st.secrets["gcp_service_account"]
        if isinstance(creds_data, str):
            creds_dict = json.loads(creds_data)
        else:
            creds_dict = dict(creds_data)
            
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Erro ao conectar com o Google Sheets: {e}")
        return None

# Menu lateral para inserir a URL ou ID da planilha
with st.sidebar:
    st.header("⚙️ Conexão com Google Sheets")
    url_planilha = st.text_input(
        "Link da Planilha do Google Sheets:", 
        placeholder="Cole a URL da planilha aqui"
    )

def extrair_sheet_id(url):
    try:
        if "/d/" in url:
            return url.split("/d/")[1].split("/")[0]
        return url
    except:
        return None

sheet_id = extrair_sheet_id(url_planilha) if url_planilha else None

if not sheet_id:
    st.info("👈 Por favor, cole a URL da sua Planilha no menu lateral para carregar o pátio.")
    st.stop()

gc = conectar_google_sheets()
if not gc:
    st.stop()

# Função auxiliar para padronizar qualquer chassi para 6 dígitos
def formatar_chassi(val):
    val_str = str(val).strip()
    if not val_str or val_str.lower() in ['nan', 'none', '[ vazio ]']:
        return '[ VAZIO ]'
    if val_str.isdigit() and len(val_str) < 6:
        return val_str.zfill(6)
    return val_str

# 2. Carregamento dos dados em tempo real da planilha
def carregar_dados():
    try:
        sh = gc.open_by_key(sheet_id)
        worksheet_patio = sh.worksheet("Patio")
        dados = worksheet_patio.get_all_records()
        df_p = pd.DataFrame(dados)
        
        if df_p.empty:
            return pd.DataFrame(), sh

        # Normaliza nomes de colunas (remove espaços extras nos nomes das colunas)
        df_p.columns = [str(col).strip() for col in df_p.columns]

        df_p['Ala'] = df_p['Ala'].astype(str).str.strip()
        df_p['Ala'] = df_p['Ala'].apply(lambda x: "Ala A (Muro)" if x.upper() in ["ALA A", "ALA A (MURO)", "A"] else x)
        df_p['Chassi'] = df_p['Chassi'].apply(formatar_chassi)
        df_p['Modelo'] = df_p['Modelo'].fillna('-').astype(str).str.strip() if 'Modelo' in df_p.columns else '-'
        df_p['Cor'] = df_p['Cor'].fillna('-').astype(str).str.strip() if 'Cor' in df_p.columns else '-'
        df_p['Posicao'] = pd.to_numeric(df_p['Posicao'], errors='coerce').fillna(0).astype(int)
        
        return df_p, sh
    except Exception as e:
        st.error(f"Erro ao acessar a planilha: {e}")
        return pd.DataFrame(), None

df_lido, spreadsheet = carregar_dados()

# Estrutura base de 5 alas x 60 vagas
alas = ["Ala A (Muro)", "Ala B", "Ala C", "Ala D", "Ala E"]
vagas_por_ala = 60

estrutura_base = []
for ala in alas:
    for pos in range(1, vagas_por_ala + 1):
        estrutura_base.append({
            "Ala": ala, 
            "Posicao": pos, 
            "Chassi": "[ VAZIO ]",
            "Modelo": "-",
            "Cor": "-"
        })

df_patio = pd.DataFrame(estrutura_base)

if not df_lido.empty and set(['Ala', 'Posicao', 'Chassi']).issubset(df_lido.columns):
    for _, row in df_lido.iterrows():
        mask = (df_patio['Ala'] == str(row['Ala']).strip()) & (df_patio['Posicao'] == int(row['Posicao']))
        chassi_val = str(row['Chassi']).strip()
        if chassi_val != "" and chassi_val != "[ VAZIO ]":
            df_patio.loc[mask, 'Chassi'] = chassi_val
            df_patio.loc[mask, 'Modelo'] = row.get('Modelo', '-')
            df_patio.loc[mask, 'Cor'] = row.get('Cor', '-')

# 3. Busca e Separação
st.subheader("🔍 Localizar Carros para Embarque")
entrada_texto = st.text_area(
    "Digite os Chassis (6 dígitos numéricos, um por linha):", 
    height=120, 
    placeholder="Ex:\n012345\n654321"
)

if st.button("🔎 Localizar Veículos", type="primary"):
    lista_busca = [formatar_chassi(c) for c in entrada_texto.split('\n') if formatar_chassi(c) != '[ VAZIO ]']
    if lista_busca:
        encontrados = df_patio[df_patio['Chassi'].isin(lista_busca) & (df_patio['Chassi'] != "[ VAZIO ]")].copy()
        chassis_encontrados = encontrados['Chassi'].tolist()
        nao_encontrados = [c for c in lista_busca if c not in chassis_encontrados]

        if not encontrados.empty:
            st.session_state['encontrados_busca'] = encontrados
            st.session_state['nao_encontrados_busca'] = nao_encontrados
        else:
            st.warning("Nenhum dos chassis informados foi localizado no pátio.")
            st.session_state['encontrados_busca'] = pd.DataFrame()
            st.session_state['nao_encontrados_busca'] = lista_busca

# Pop-up de Confirmação com Atualização Direta na Planilha
if 'encontrados_busca' in st.session_state and not st.session_state['encontrados_busca'].empty:
    encontrados = st.session_state['encontrados_busca']
    st.success(f"**{len(encontrados)} veículo(s) localizado(s)!**")
    st.dataframe(encontrados[['Chassi', 'Modelo', 'Cor', 'Ala', 'Posicao']], use_container_width=True)
    
    @st.dialog("⚠️ Confirmar Retirada e Atualizar Planilha")
    def popup_confirmacao():
        st.write("Deseja confirmar a retirada? Os dados serão atualizados na planilha do Google Sheets!")
        for _, r in encontrados.iterrows():
            st.markdown(f"- **Chassi: {r['Chassi']}** ({r['Modelo']} - {r['Cor']}) ➔ {r['Ala']}, Vaga **{r['Posicao']:02d}**")
            
        col1, col2 = st.columns(2)
        if col1.button("✅ Confirmar e Gravar na Planilha", type="primary"):
            try:
                ws_patio = spreadsheet.worksheet("Patio")
                
                # Abre ou cria a aba 'Retirados'
                try:
                    ws_retirados = spreadsheet.worksheet("Retirados")
                except:
                    ws_retirados = spreadsheet.add_worksheet(title="Retirados", rows="1000", cols="10")
                    ws_retirados.append_row(["Chassi", "Modelo", "Cor", "Ala", "Posicao", "Data_Hora_Retirada"])

                hora_atual = datetime.now().strftime("%d/%m/%Y %H:%M")
                
                # Busca localização das células na aba 'Patio'
                headers = [str(h).strip() for h in ws_patio.row_values(1)]
                col_chassi_idx = headers.index("Chassi") + 1 if "Chassi" in headers else 3
                
                # Pega todas as células da coluna Chassi
                col_valores = ws_patio.col_values(col_chassi_idx)
                
                for _, r in encontrados.iterrows():
                    chassi_alvo = str(r['Chassi']).strip()
                    
                    # 1. Registra a saída na aba 'Retirados'
                    ws_retirados.append_row([
                        chassi_alvo, 
                        str(r['Modelo']), 
                        str(r['Cor']), 
                        str(r['Ala']), 
                        int(r['Posicao']), 
                        hora_atual
                    ])
                    
                    # 2. Apaga o chassi da aba 'Patio' na linha correspondente
                    for num_linha, val in enumerate(col_valores, start=1):
                        if str(val).strip() == chassi_alvo:
                            ws_patio.update_cell(num_linha, col_chassi_idx, "")
                            break
                            
                st.success("Planilha atualizada com sucesso!")
                del st.session_state['encontrados_busca']
                st.cache_resource.clear()  # Limpa o cache para forçar a reler a planilha atualizada
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar na planilha: {e}")

        if col2.button("❌ Cancelar"):
            st.rerun()

    if st.button("🚚 Processar Retirada e Atualizar Sheets"):
        popup_confirmacao()

st.divider()

# 4. Grade de 5 Alas do Pátio
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
                esta_ocupado = chassi_val != "" and chassi_val != "[ VAZIO ]"
                cor_indicador = "🔴" if esta_ocupado else "⚪"
                
                if esta_ocupado:
                    detalhes = f"{row['Modelo']}/{row['Cor']}" if row['Modelo'] != '-' or row['Cor'] != '-' else ""
                    texto_exibicao = f"{chassi_val} ({detalhes})" if detalhes else chassi_val
                else:
                    texto_exibicao = "[ VAZIO ]"
                    
                st.text(f"{cor_indicador} Pos {int(row['Posicao']):02d}: {texto_exibicao}")

st.divider()

# 5. Tabela de Retirados (Lendo direto da aba 'Retirados' da planilha)
st.subheader("📋 Veículos Retirados (Histórico na Planilha)")

try:
    ws_ret = spreadsheet.worksheet("Retirados")
    dados_ret = ws_ret.get_all_records()
    df_ret_sheet = pd.DataFrame(dados_ret)
    
    if not df_ret_sheet.empty:
        st.dataframe(df_ret_sheet, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum veículo retirado registrado na aba 'Retirados'.")
except:
    st.info("A aba 'Retirados' será criada na planilha assim que a primeira retirada for efetuada.")
