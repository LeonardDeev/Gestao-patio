import streamlit as st
import pandas as pd
from datetime import datetime

# Configuração da página web
st.set_page_config(page_title="Gestão de Pátio", layout="wide")

# 1. Criação automática do Pátio Completo (Alas A, B, C, D, E | Vagas 1 a 40)
if 'patio' not in st.session_state:
    alas = ["Ala A", "Ala B", "Ala C", "Ala D", "Ala E"]
    vagas_por_ala = 40  # Quantidade de vagas por ala
    
    lista_inicial = []
    for ala in alas:
        for pos in range(1, vagas_por_ala + 1):
            lista_inicial.append({
                "Ala": ala,
                "Posicao": pos,
                "Chassi": "[ VAZIO ]"
            })
            
    st.session_state.patio = pd.DataFrame(lista_inicial)

if 'retirados' not in st.session_state:
    st.session_state.retirados = pd.DataFrame(columns=["Chassi", "Ala_Origem", "Posicao_Origem", "Data_Retirada"])

st.title("🚗 Sistema de Gestão e Separação de Pátio")

# 2. Área de Busca e Separação do Dia
st.subheader("🔍 Localizar Carros para Embarque")
entrada_texto = st.text_area("Digite os Chassis/Placas (um por linha):", height=100, placeholder="Ex:\nABC1234\nDEF5678")

if st.button("🔎 Localizar Veículos", type="primary"):
    lista_busca = [c.strip().upper() for c in entrada_texto.split('\n') if c.strip()]
    
    if lista_busca:
        df_patio = st.session_state.patio
        encontrados = df_patio[df_patio['Chassi'].isin(lista_busca) & (df_patio['Chassi'] != "[ VAZIO ]")].copy()
        
        chassis_encontrados = encontrados['Chassi'].tolist()
        nao_encontrados = [c for c in lista_busca if c not in chassis_encontrados]

        if not encontrados.empty:
            st.success(f"**{len(encontrados)} veículo(s) localizado(s)!**")
            st.dataframe(encontrados[['Chassi', 'Ala', 'Posicao']], use_container_width=True)
            
            # Modal / Janela de Confirmação para Retirada
            @st.dialog("⚠️ Confirmar Retirada do Pátio")
            def popup_confirmacao():
                st.write("Deseja retirar esses veículos das vagas atuais e enviá-los para a lista de **Retirados**?")
                
                col1, col2 = st.columns(2)
                if col1.button("✅ Sim, Retirar do Pátio", type="primary"):
                    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
                    novos_retirados = []
                    
                    for _, row in encontrados.iterrows():
                        novos_retirados.append({
                            "Chassi": row['Chassi'],
                            "Ala_Origem": row['Ala'],
                            "Posicao_Origem": row['Posicao'],
                            "Data_Retirada": agora
                        })
                        mask = (df_patio['Ala'] == row['Ala']) & (df_patio['Posicao'] == row['Posicao'])
                        df_patio.loc[mask, 'Chassi'] = "[ VAZIO ]"
                    
                    df_novos = pd.DataFrame(novos_retirados)
                    st.session_state.retirados = pd.concat([st.session_state.retirados, df_novos], ignore_index=True)
                    st.session_state.patio = df_patio
                    
                    st.success("Veículos retirados com sucesso!")
                    st.rerun()

                if col2.button("❌ Cancelar"):
                    st.rerun()

            if st.button("🚚 Processar Retirada dos Veículos"):
                popup_confirmacao()

        if nao_encontrados:
            st.warning(f"Veículos não localizados no pátio: {', '.join(nao_encontrados)}")
    else:
        st.info("Digite ao menos um chassi/placa para realizar a busca.")

st.divider()

# 3. Visualização em Colunas (Grade do Pátio com Scroll interno)
st.subheader("📍 Visão Geral do Pátio (Alas A até E)")
alas_unicas = sorted(st.session_state.patio['Ala'].unique())
colunas_alas = st.columns(len(alas_unicas) + 1)

for idx, ala in enumerate(alas_unicas):
    with colunas_alas[idx]:
        st.markdown(f"### {ala}")
        dados_ala = st.session_state.patio[st.session_state.patio['Ala'] == ala].sort_values('Posicao')
        
        # Caixa rolável para não deixar a tela gigante na vertical
        with st.container(height=400):
            for _, row in dados_ala.iterrows():
                cor = "🔴" if row['Chassi'] != "[ VAZIO ]" else "⚪"
                st.text(f"{cor} Pos {row['Posicao']:02d}: {row['Chassi']}")

# Coluna para Histórico de Retirados
with colunas_alas[-1]:
    st.markdown("### 📋 Retirados")
    with st.container(height=400):
        if not st.session_state.retirados.empty:
            for _, row in st.session_state.retirados.iterrows():
                st.text(f"✅ {row['Chassi']}\n   ({row['Ala_Origem']} P{row['Posicao_Origem']} - {row['Data_Retirada']})")
        else:
            st.caption("Nenhum veículo retirado hoje.")
