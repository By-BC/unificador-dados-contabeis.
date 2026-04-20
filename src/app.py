import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from ofxparse import OfxParser
import io
import re
import base64

# =============================================================================
# CONFIGURAÇÃO DA PÁGINA
# =============================================================================
st.set_page_config(
    page_title="Analisegroup | Financial Intelligence",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =============================================================================
# CSS — IDENTIDADE VISUAL PREMIUM
# =============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Montserrat', sans-serif;
        background-color: #000000;
        color: #FFFFFF;
    }

    [data-testid="stHeader"], [data-testid="stSidebar"], footer {display: none !important;}

    div[data-testid="stMetric"] {
        background: #0A0A0A !important;
        border: 1px solid #1A1A1A !important;
        border-bottom: 3px solid #C5A059 !important;
        border-radius: 4px !important;
        padding: 15px !important;
    }

    .stButton > button {
        width: 100%;
        background: linear-gradient(145deg, #C5A059, #8E794E) !important;
        color: #000 !important;
        border: none !important;
        border-radius: 2px !important;
        font-weight: 600 !important;
        letter-spacing: 2px !important;
        padding: 12px !important;
        transition: 0.4s !important;
    }

    .stButton > button:hover {
        background: #FFFFFF !important;
        color: #000 !important;
        box-shadow: 0 0 20px rgba(197, 160, 89, 0.4);
    }

    .stDataFrame {
        border: 1px solid #1A1A1A !important;
        border-radius: 8px !important;
    }

    .stTextInput input {
        background-color: #0A0A0A !important;
        color: #C5A059 !important;
        border: 1px solid #333 !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        background: #0A0A0A;
        border-bottom: 1px solid #1A1A1A;
        gap: 0;
    }
    .stTabs [data-baseweb="tab"] {
        color: #555 !important;
        font-size: 12px;
        letter-spacing: 1px;
        padding: 10px 20px;
    }
    .stTabs [aria-selected="true"] {
        color: #C5A059 !important;
        border-bottom: 2px solid #C5A059 !important;
        background: transparent !important;
    }

    .streamlit-expanderHeader {
        background: #0A0A0A !important;
        border: 1px solid #1A1A1A !important;
        border-radius: 4px !important;
        color: #C5A059 !important;
        font-size: 12px !important;
        letter-spacing: 1px !important;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# FUNÇÕES UTILITÁRIAS
# =============================================================================
def get_image_base64(path):
    try:
        with open(path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception:
        return ""

def formatar_brl(valor: float) -> str:
    """Formata número para o padrão brasileiro: 1.234,56"""
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def kpi_card(titulo: str, valor: float, cor_borda: str, cor_valor: str) -> str:
    """Gera HTML de um card de KPI no padrão visual Analisegroup."""
    return f"""
    <div style='border:1px solid {cor_borda};border-bottom:3px solid {cor_borda};
                padding:16px 20px;border-radius:4px;background:#0A0A0A;'>
        <p style='margin:0 0 6px 0;color:#666;text-transform:uppercase;
                  font-size:9px;letter-spacing:2px;'>{titulo}</p>
        <h2 style='margin:0;color:{cor_valor};font-size:20px;'>R$ {valor:,.2f}</h2>
    </div>"""

def section_label(texto: str):
    st.markdown(
        f"<p style='font-size:9px;font-weight:600;letter-spacing:3px;color:#C5A059;"
        f"text-transform:uppercase;margin-bottom:12px;'>{texto}</p>",
        unsafe_allow_html=True
    )

def section_divider():
    st.markdown(
        "<hr style='border:none;border-bottom:1px solid #111;margin:24px 0;'>",
        unsafe_allow_html=True
    )

def extrair_cnpj(memo):
    numeros = re.sub(r'[^0-9]', '', str(memo))
    if len(numeros) >= 14:
        match = re.search(r'\d{14}', numeros)
        if match:
            c = match.group(0)
            return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"
    return ""

def categorizar_transacao(historico):
    hist_upper = str(historico).upper()
    for palavra_chave, categoria in REGRAS_CATEGORIZACAO.items():
        if palavra_chave in hist_upper:
            return categoria
    return 'Não Categorizado (Pendente)'


# =============================================================================
# DADOS DE REFERÊNCIA
# =============================================================================
BANCOS_MAPEADOS = {
    '1':   'Banco do Brasil',
    '33':  'Santander',
    '104': 'Caixa Econômica',
    '237': 'Bradesco',
    '341': 'Itaú',
    '77':  'Inter',
    '260': 'Nubank',
    '634': 'Tribanco',  # COMPE oficial (Banco Triângulo S.A.)
    '382': 'Tribanco',  # Código alternativo em arquivos OFX legados
    '41':  'Banrisul',
    '422': 'Banco Safra',
    '74':  'Banco Safra'
}

REGRAS_CATEGORIZACAO = {
    'TARIFA':         'Despesas Bancárias',
    'MANUT':          'Despesas Bancárias',
    'PIX':            'Transferências Pix',
    'TED':            'Transferências',
    'DOC':            'Transferências',
    'PAGTO COBRANCA': 'Pagamento de Fornecedores',
    'PAGTO TITULO':   'Pagamento de Fornecedores',
    'DARF':           'Impostos',
    'GPS':            'Impostos',
    'SIMPLES NAC':    'Impostos',
    'SALA':           'Folha de Pagamento',
    'REND PAGO':      'Rendimentos de Aplicação',
    'IOF':            'Impostos Financeiros',
    'SAQUE':          'Saques em Espécie'
}

CORES_CATEGORIA = {
    'Despesas Bancárias':         '#C5A059',
    'Transferências Pix':         '#4A90D9',
    'Transferências':             '#5BA85B',
    'Pagamento de Fornecedores':  '#D97B4A',
    'Impostos':                   '#D94A4A',
    'Folha de Pagamento':         '#9B59B6',
    'Rendimentos de Aplicação':   '#1ABC9C',
    'Impostos Financeiros':       '#E74C3C',
    'Saques em Espécie':          '#95A5A6',
    'Não Categorizado (Pendente)':'#555555'
}


# =============================================================================
# SISTEMA DE LOGIN
# =============================================================================
def check_password():
    if st.session_state.get("password_correct", False):
        return True

    st.markdown("<div style='margin-top:15vh;'></div>", unsafe_allow_html=True)

    _, col_login, _ = st.columns([1.5, 1, 1.5])

    with col_login:
        _, col_img, _ = st.columns([1, 2, 1])
        with col_img:
            try:
                st.image("assets/logo.png", use_container_width=True)
            except Exception:
                st.error("⚠️ Logo não encontrado em assets/logo.png")

        st.markdown(
            "<p style='text-align:center;color:#C5A059;letter-spacing:2px;"
            "font-size:10px;font-weight:600;margin-top:10px;margin-bottom:25px;'>"
            "BPO FINANCEIRO & AUDITORIA DIGITAL</p>",
            unsafe_allow_html=True
        )

        with st.form("login_form", clear_on_submit=False):
            password = st.text_input("Credencial de Acesso", type="password")
            submit   = st.form_submit_button("AUTENTICAR")
            if submit:
                if password == st.secrets["general"]["access_password"]:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("Credencial incorreta. Tente novamente.")

    st.components.v1.html(
        """<script>
        setTimeout(function() {
            var i = window.parent.document.querySelector('input[type="password"]');
            if (i) i.focus();
        }, 100);
        </script>""",
        height=0, width=0
    )
    return False


if not check_password():
    st.stop()


# =============================================================================
# CABEÇALHO COM MINI LOGO + LOGOUT
# =============================================================================
logo_b64 = get_image_base64("assets/logo.png")
img_html = (
    f'<img src="data:image/png;base64,{logo_b64}" style="height:28px;margin-right:12px;">'
    if logo_b64 else ""
)

st.write("")
col_cab, col_sair = st.columns([8, 1])

with col_cab:
    st.markdown(f"""
        <div style="padding-top:5px;display:flex;align-items:center;">
            {img_html}
            <span style='color:#C5A059;font-size:20px;letter-spacing:2px;font-weight:700;text-transform:uppercase;'>
                Analisegroup
            </span>
            <span style='color:#333;font-size:20px;margin:0 10px;'>|</span>
            <span style='color:#F0F0F0;font-size:18px;font-weight:300;letter-spacing:1px;'>
                Conciliação BPO e Unificação OFX
            </span>
        </div>
    """, unsafe_allow_html=True)

with col_sair:
    if st.button("SAIR", key="btn_logout", use_container_width=True):
        st.session_state["password_correct"] = False
        st.session_state["ofx_carregado"]    = False
        st.session_state["erp_carregado"]    = False
        st.rerun()

st.markdown(
    "<hr style='border:none;border-bottom:1px solid rgba(197,160,89,0.2);"
    "margin-top:10px;margin-bottom:28px;'>",
    unsafe_allow_html=True
)


# =============================================================================
# SEÇÃO 2 — UPLOAD DE ARQUIVOS
# =============================================================================
section_label("Entrada de dados")

col_up1, col_up2 = st.columns(2)

with col_up1:
    st.markdown(
        "<p style='color:#C5A059;font-weight:bold;font-size:12px;margin-bottom:4px;'>"
        "1. A Verdade do Banco</p>",
        unsafe_allow_html=True
    )
    arquivos_ofx = st.file_uploader(
        "Extratos OFX (múltiplos bancos)",
        type=["ofx"], accept_multiple_files=True,
        help="Faça upload de um ou mais arquivos .OFX exportados pelo seu banco."
    )
    if arquivos_ofx:
        st.session_state["ofx_carregado"] = True
        nomes = ", ".join([f.name.replace(".ofx","").replace(".OFX","") for f in arquivos_ofx])
        st.success(f"✅ {len(arquivos_ofx)} arquivo(s) · {nomes}")

with col_up2:
    st.markdown(
        "<p style='color:#C5A059;font-weight:bold;font-size:12px;margin-bottom:4px;'>"
        "2. A Verdade da Empresa</p>",
        unsafe_allow_html=True
    )
    arquivo_erp = st.file_uploader(
        "Controle interno (CSV ou Excel)",
        type=["csv", "xlsx"],
        help="Planilha do ERP com colunas 'Data' e 'Valor'."
    )

    fila_erp = []

    if arquivo_erp:
        try:
            df_erp = (
                pd.read_csv(arquivo_erp, sep=';', decimal=',')
                if arquivo_erp.name.endswith('.csv')
                else pd.read_excel(arquivo_erp)
            )

            coluna_valor = [c for c in df_erp.columns if 'VALOR' in str(c).upper()]
            coluna_data  = [c for c in df_erp.columns if 'DATA'  in str(c).upper()]

            if coluna_valor and coluna_data:
                def limpar_numero(x):
                    try:
                        if pd.isna(x): return None
                        if isinstance(x, (int, float)): return float(x)
                        s = str(x).upper().replace('R$','').strip()
                        if ',' in s: s = s.replace('.','').replace(',','.')
                        return float(s)
                    except:
                        return None

                df_erp['Valor_Limpo'] = df_erp[coluna_valor[0]].apply(limpar_numero)
                df_erp['Data_Parsed'] = pd.to_datetime(df_erp[coluna_data[0]], errors='coerce')
                df_erp_valido = df_erp.dropna(subset=['Valor_Limpo','Data_Parsed'])
                fila_erp = df_erp_valido[['Data_Parsed','Valor_Limpo']].to_dict('records')
                st.session_state["erp_carregado"] = True
                st.success(f"✅ ERP carregado! {len(fila_erp)} lançamentos prontos.")
            else:
                st.error("A planilha precisa ter colunas com 'Data' e 'Valor' no nome.")
        except Exception as e:
            st.error(f"Erro na leitura: {e}")

section_divider()

if not arquivos_ofx:
    st.info("👆 Anexe os extratos OFX para iniciar a auditoria.")
    st.stop()

if not fila_erp:
    st.warning("⚠️ Operando só com a Verdade do Banco. Anexe o Controle Interno para habilitar o Motor de Match.")


# =============================================================================
# PROCESSAMENTO — OFX + MOTOR DE MATCH + TRANSFERÊNCIAS
# =============================================================================
dados = []
for f in arquivos_ofx:
    ofx          = OfxParser.parse(f)
    codigo_raw   = str(ofx.account.routing_number).strip()
    nome_banco   = BANCOS_MAPEADOS.get(codigo_raw.lstrip('0'), f"Banco {codigo_raw}")

    for t in ofx.account.statement.transactions:
        v = float(t.amount)
        # Adicionamos o Arquivo_Origem como a primeira chave do dicionário
        dados.append({
            'Arquivo_Origem': f.name, 
            'Banco':     nome_banco,
            'Data':      t.date,
            'Valor':     v,
            'Tipo':      'CREDITO' if v >= 0 else 'DEBITO',
            'Categoria': categorizar_transacao(t.memo),
            'CNPJ':      extrair_cnpj(t.memo),
            'Histórico': t.memo
        })

df = pd.DataFrame(dados)
df['Data'] = pd.to_datetime(df['Data'])

# Motor de Match (Valor exato + janela de 3 dias)
if fila_erp:
    status_match = []
    df['_data_aux'] = df['Data']

    for _, row in df.iterrows():
        v_banco = abs(row['Valor'])
        d_banco = row['_data_aux']
        achou   = False

        if pd.notnull(d_banco):
            for item in fila_erp:
                if abs(v_banco - abs(item['Valor_Limpo'])) < 0.01:
                    if abs((d_banco - item['Data_Parsed']).days) <= 3:
                        status_match.append('✅ Conciliado')
                        fila_erp.remove(item)
                        achou = True
                        break

        if not achou:
            status_match.append('❌ Pendente no ERP')

    df['Status'] = status_match
    df = df.drop(columns=['_data_aux'])
else:
    df['Status'] = '⚠️ Aguardando ERP'

# Detecção de transferências internas
df_cruz = df.copy()
df_cruz['Valor_Abs'] = df_cruz['Valor'].abs()
lista_transf = [
    grupo for _, grupo in df_cruz.groupby(['Data','Valor_Abs'])
    if len(grupo) >= 2
    and 'CREDITO' in grupo['Tipo'].values
    and 'DEBITO'  in grupo['Tipo'].values
]

tem_transf = len(lista_transf) > 0
if tem_transf:
    df_transf = pd.concat(lista_transf).drop(columns=['Valor_Abs'])


# =============================================================================
# SEÇÃO 3 — FILTROS DE AUDITORIA (banco / categoria / tipo)
# =============================================================================
section_label("Filtros de auditoria")

with st.expander("🎯 Filtros Rápidos", expanded=False):
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        bancos_sel = st.multiselect("Banco",     options=df['Banco'].unique(),     default=df['Banco'].unique())
    with fc2:
        cats_sel   = st.multiselect("Categoria", options=df['Categoria'].unique(), default=df['Categoria'].unique())
    with fc3:
        tipo_sel   = st.multiselect("Tipo",      options=df['Tipo'].unique(),      default=df['Tipo'].unique())

# Aplicação dos filtros de banco / categoria / tipo
df_f = df[
    df['Banco'].isin(bancos_sel) &
    df['Categoria'].isin(cats_sel) &
    df['Tipo'].isin(tipo_sel)
].copy()

section_divider()


# =============================================================================
# SEÇÃO 4 — RESUMO EXECUTIVO
# =============================================================================
section_label("Resumo executivo")

credito   = df_f[df_f['Tipo']=='CREDITO']['Valor'].sum()
debito    = abs(df_f[df_f['Tipo']=='DEBITO']['Valor'].sum())
saldo     = credito - debito
cor_saldo = "#C5A059" if saldo >= 0 else "#FF4B4B"

k1, k2, k3, k4 = st.columns(4)
with k1: st.markdown(kpi_card("Total Entradas", credito, "#C5A059", "#C5A059"), unsafe_allow_html=True)
with k2: st.markdown(kpi_card("Total Saídas",   debito,  "#5C4A26", "#F0F0F0"), unsafe_allow_html=True)
with k3:
    st.markdown(
        f"<div style='border:1px solid {cor_saldo};border-bottom:3px solid {cor_saldo};"
        f"padding:16px 20px;border-radius:4px;background:#0A0A0A;'>"
        f"<p style='margin:0 0 6px 0;color:#666;text-transform:uppercase;font-size:9px;letter-spacing:2px;'>Saldo Líquido</p>"
        f"<h2 style='margin:0;color:{cor_saldo};font-size:20px;'>R$ {saldo:,.2f}</h2></div>",
        unsafe_allow_html=True
    )
with k4:
    st.markdown(
        f"<div style='border:1px solid #1A1A1A;border-bottom:3px solid #333;"
        f"padding:16px 20px;border-radius:4px;background:#0A0A0A;'>"
        f"<p style='margin:0 0 6px 0;color:#666;text-transform:uppercase;font-size:9px;letter-spacing:2px;'>Lançamentos</p>"
        f"<h2 style='margin:0;color:#F0F0F0;font-size:20px;'>{len(df_f)}</h2></div>",
        unsafe_allow_html=True
    )

# Barra de status de conciliação
if '✅ Conciliado' in df['Status'].values or '❌ Pendente no ERP' in df['Status'].values:
    total  = len(df)
    conc   = len(df[df['Status']=='✅ Conciliado'])
    pend   = len(df[df['Status']=='❌ Pendente no ERP'])
    n_tr   = len(df_transf) if tem_transf else 0
    taxa   = conc / total * 100 if total > 0 else 0

    st.markdown(f"""
    <div style='background:#0A0A0A;border:1px solid #1A1A1A;border-left:4px solid #C5A059;
                border-radius:0 6px 6px 0;padding:14px 20px;margin-top:12px;'>
        <div style='display:flex;gap:32px;align-items:center;flex-wrap:wrap;'>
            <div>
                <span style='font-size:9px;color:#666;letter-spacing:2px;display:block;margin-bottom:3px;'>TOTAL NO BANCO</span>
                <b style='color:#C5A059;font-size:18px;'>{total}</b>
            </div>
            <div>
                <span style='font-size:9px;color:#666;letter-spacing:2px;display:block;margin-bottom:3px;'>CONCILIADOS</span>
                <b style='color:#4CAF50;font-size:18px;'>{conc}</b>
                <span style='color:#2a6b2a;font-size:11px;margin-left:4px;'>{taxa:.1f}%</span>
            </div>
            <div>
                <span style='font-size:9px;color:#666;letter-spacing:2px;display:block;margin-bottom:3px;'>PENDENTES</span>
                <b style='color:#FF4B4B;font-size:18px;'>{pend}</b>
            </div>
            <div>
                <span style='font-size:9px;color:#666;letter-spacing:2px;display:block;margin-bottom:3px;'>TRANSFERÊNCIAS</span>
                <b style='color:#C5A059;font-size:18px;'>{n_tr}</b>
            </div>
            <div style='flex:1;min-width:120px;'>
                <div style='height:4px;background:#1A1A1A;border-radius:2px;overflow:hidden;'>
                    <div style='height:100%;width:{taxa:.1f}%;background:linear-gradient(90deg,#4CAF50,#C5A059);border-radius:2px;'></div>
                </div>
                <span style='font-size:9px;color:#555;margin-top:4px;display:block;'>Taxa de conciliação</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

section_divider()


# =============================================================================
# SEÇÃO 5 — FILTROS DE DATA E VALOR + TRIAGEM DE CONCILIAÇÃO
# =============================================================================
section_label("Triagem de conciliação")

# --- Filtros simples: uma data e um valor ---
_data_min = df_f['Data'].min().date()
_data_max = df_f['Data'].max().date()

ff1, ff2, ff3 = st.columns([2, 2, 3])
with ff1:
    filtro_data = st.date_input(
        "Filtrar por data", value=None,
        min_value=_data_min, max_value=_data_max,
        format="DD/MM/YYYY", key="filtro_data",
        help="Deixe em branco para mostrar todas as datas."
    )
with ff2:
    filtro_valor_str = st.text_input(
        "Filtrar por valor (R$)", value="",
        placeholder="Ex: 1500,00", key="filtro_valor",
        help="Digite um valor exato para filtrar."
    )
with ff3:
    st.write("")  # espaço para alinhar visualmente

# Aplicação dos filtros de data e valor sobre df_f
df_filtrado = df_f.copy()

if filtro_data:
    df_filtrado = df_filtrado[df_filtrado['Data'].dt.date == filtro_data]

if filtro_valor_str.strip():
    try:
        filtro_valor = float(filtro_valor_str.strip().replace(',', '.'))
        df_filtrado  = df_filtrado[abs(df_filtrado['Valor'].abs() - filtro_valor) < 0.01]
    except ValueError:
        st.warning("⚠️ Valor inválido — use números (ex: 1500,00).")
        df_filtrado = df_f.copy()

# Badge de resultado
_n_total = len(df_f)
_n_exib  = len(df_filtrado)
if _n_exib < _n_total:
    st.markdown(
        f"<p style='font-size:10px;color:#4A90D9;letter-spacing:1px;margin:8px 0 4px 0;'>"
        f"🔍 {_n_exib} de {_n_total} lançamentos exibidos.</p>",
        unsafe_allow_html=True
    )

df_tela         = df_filtrado.copy()
df_tela['Data'] = df_tela['Data'].dt.strftime('%d/%m/%Y')
df_tela['Valor']= df_tela['Valor'].apply(formatar_brl)

n_pend  = len(df_tela[df_tela['Status']=='❌ Pendente no ERP']) if 'Status' in df_tela.columns else 0
n_conc  = len(df_tela[df_tela['Status']=='✅ Conciliado'])       if 'Status' in df_tela.columns else 0
n_tr_ab = len(df_transf) if tem_transf else 0

if fila_erp is not None and len(df) > 0:
    tab3, tab2, tab1, tab4 = st.tabs([
        f"📋 Todos ({len(df_tela)})",
        f"✅ Conciliados ({n_conc})",
        f"⚠️ Pendentes ({n_pend})",
        f"🔄 Transferências ({n_tr_ab})"
    ])
    with tab1:
        st.dataframe(df_tela[df_tela['Status']=='❌ Pendente no ERP'], use_container_width=True)
    with tab2:
        st.dataframe(df_tela[df_tela['Status']=='✅ Conciliado'],       use_container_width=True)
    with tab3:
        st.dataframe(df_tela,                                            use_container_width=True)
    with tab4:
        if tem_transf:
            dt = df_transf.copy()
            dt['Data']  = dt['Data'].apply(lambda x: x.strftime('%d/%m/%Y') if hasattr(x,'strftime') else str(x))
            dt['Valor'] = dt['Valor'].apply(formatar_brl)
            st.info("💡 Mesmo valor e data entre contas diferentes — anulam-se no saldo líquido.")
            st.dataframe(dt, use_container_width=True)
        else:
            st.success("Nenhuma transferência interna detectada neste período.")
else:
    st.dataframe(df_tela, use_container_width=True)

section_divider()


# =============================================================================
# SEÇÃO 6 — ANÁLISE VISUAL (fluxo de caixa + categorias lado a lado)
# =============================================================================
section_label("Análise visual")

col_g1, col_g2 = st.columns(2)

with col_g1:
    st.markdown(
        "<p style='font-size:10px;color:#888;letter-spacing:1px;margin-bottom:6px;'>FLUXO DE CAIXA</p>",
        unsafe_allow_html=True
    )
    df_evol = df_f.copy()
    df_evol['Periodo'] = (
        df_evol['Data'].dt.to_period('M').astype(str)
        if df_evol['Data'].dt.to_period('M').nunique() > 1
        else df_evol['Data'].dt.strftime('%d/%m')
    )
    df_evol_g = df_evol.groupby(['Periodo','Tipo'])['Valor'].sum().abs().reset_index()

    fig_evol = px.line(
        df_evol_g, x='Periodo', y='Valor', color='Tipo',
        markers=True, line_shape="spline",
        color_discrete_map={'CREDITO':'#C5A059','DEBITO':'#FF4B4B'},
        template="plotly_dark"
    )
    fig_evol.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None),
        xaxis=dict(title=None, showgrid=False),
        yaxis=dict(title=None, showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
        margin=dict(t=40,b=0,l=0,r=0), hovermode="x unified", height=280
    )
    fig_evol.update_traces(line=dict(width=3), marker=dict(size=6))
    st.plotly_chart(fig_evol, use_container_width=True)

with col_g2:
    st.markdown(
        "<p style='font-size:10px;color:#888;letter-spacing:1px;margin-bottom:6px;'>GASTOS POR CATEGORIA</p>",
        unsafe_allow_html=True
    )
    df_cat = (
        df_f[df_f['Tipo']=='DEBITO']
        .groupby('Categoria')['Valor'].sum().abs()
        .reset_index().sort_values('Valor', ascending=False)
    )

    if not df_cat.empty:
        fig_cat = go.Figure(go.Pie(
            labels=df_cat['Categoria'],
            values=df_cat['Valor'],
            hole=0.55,
            marker=dict(
                colors=[CORES_CATEGORIA.get(c,'#888') for c in df_cat['Categoria']],
                line=dict(color='#000', width=1)
            ),
            textinfo='percent',
            textfont=dict(size=10, color='#fff'),
            hovertemplate='<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percent}<extra></extra>'
        ))
        fig_cat.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="v", font=dict(size=10, color='#888'),
                        bgcolor='rgba(0,0,0,0)', x=1, y=0.5),
            margin=dict(t=40,b=0,l=0,r=0), height=280
        )
        st.plotly_chart(fig_cat, use_container_width=True)
    else:
        st.info("Sem débitos no período filtrado para exibir categorias.")

section_divider()


# =============================================================================
# SEÇÃO 7 — EXPORTAÇÃO (última etapa)
# =============================================================================
section_label("Exportação")

try:
    periodo = df_f['Data'].min().strftime('%m_%Y')
except:
    periodo = "GERAL"

st.markdown(
    "<p style='color:#C5A059;font-size:12px;margin-bottom:8px;'>Selecione o formato:</p>",
    unsafe_allow_html=True
)
sistema = st.radio(
    "Formato", ["Padrão Analisegroup (CSV Gerencial)", "Domínio Sistemas (TXT Contábil)"],
    horizontal=True, label_visibility="collapsed"
)

st.write("")
cb1, cb2 = st.columns(2)

with cb1:
    if sistema == "Domínio Sistemas (TXT Contábil)":
        dx = df.copy()
        dx['Conta_Debito']   = dx.apply(lambda r: 100 if r['Tipo']=='CREDITO' else 400, axis=1)
        dx['Conta_Credito']  = dx.apply(lambda r: 300 if r['Tipo']=='CREDITO' else 100, axis=1)
        dx['Data_Fmt']       = pd.to_datetime(dx['Data']).dt.strftime('%d/%m/%Y')
        dom = dx[['Data_Fmt','Conta_Debito','Conta_Credito','Valor','Histórico']].copy()
        dom.columns = ['Data','Conta_Debito','Conta_Credito','Valor','Historico']
        arq = dom.to_csv(index=False, sep=';', decimal=',', encoding='windows-1252').encode('windows-1252')
        st.download_button("⚙️ Baixar TXT para Domínio",    data=arq, file_name=f"IMPORTACAO_DOMINIO_{periodo}.txt",       mime="text/plain", use_container_width=True)
    else:
        arq = df.to_csv(index=False, sep=';', decimal=',', encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button("📄 Baixar Planilha Consolidada", data=arq, file_name=f"ANALISEGROUP_CONSOLIDADO_{periodo}.csv", mime="text/csv",   use_container_width=True)

#with cb2:
   # if tem_transf:
      #  ct = df_transf.to_csv(index=False, sep=';', decimal=',', encoding='utf-8-sig').encode('utf-8-sig')
     #   st.download_button("🔄 Baixar Relatório de Transferências", data=ct, file_name=f"TRANSFERENCIAS_{periodo}.csv", mime="text/csv", use_container_width=True)
   # else:
    #    st.button("✅ Sem transferências internas", disabled=True, use_container_width=True)