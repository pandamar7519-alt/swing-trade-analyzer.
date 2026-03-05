import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go

# --- Configuração da Página ---
st.set_page_config(page_title="Swing Trade Analyzer", layout="wide")

# --- Título e Disclaimer ---
st.title("📊 Analisador Científico de Swing Trade")
st.markdown("""
    **Atenção:** Esta ferramenta utiliza análise técnica baseada em indicadores estatísticos. 
    **Não constitui recomendação de investimento.** O mercado de renda variável envolve riscos.
    Sempre faça sua própria análise (DYOR).
""")

# --- Barra Lateral de Inputs ---
st.sidebar.header("Configurações da Operação")
ticker = st.sidebar.text_input("Ativo (Ex: PETR4.SA, AAPL)", "PETR4.SA")
periodo = st.sidebar.selectbox("Período de Dados", ["6mo", "1y", "2y"], index=1)
capital = st.sidebar.number_input("Capital Disponível (R$)", value=10000.0)
risco_por_operacao = st.sidebar.slider("Risco por Operação (%)", 1.0, 5.0, 2.0)

# --- Funções de Análise ---
def get_data(ticker, period):
    try:
        data = yf.download(ticker, period=period, progress=False)
        if data.empty:
            return None
        # Ajuste para colunas multi-index se necessário (depende da versão do yfinance)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except Exception as e:
        st.error(f"Erro ao buscar dados: {e}")
        return None

def analyze_swing_trade(df):
    df = df.copy()
    
    # 1. Indicadores de Tendência (EMAs)
    df['EMA9'] = ta.ema(df['Close'], length=9)
    df['EMA21'] = ta.ema(df['Close'], length=21)
    df['EMA50'] = ta.ema(df['Close'], length=50)
    
    # 2. Indicadores de Momentum (RSI e MACD)
    df['RSI'] = ta.rsi(df['Close'], length=14)
    macd = ta.macd(df['Close'])
    df = pd.concat([df, macd], axis=1) # Adiciona MACD_12_26_9, MACDs_12_26_9, MACDh_12_26_9
    
    # 3. Volatilidade (ATR para Stops Dinâmicos)
    df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
    
    # 4. Bandas de Bollinger (Opcional para volatilidade)
    bbands = ta.bbands(df['Close'], length=20)
    df = pd.concat([df, bbands], axis=1)

    return df

def generate_signal(df, risk_pct):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    signal = "NEUTRO"
    color = "gray"
    entry_price = 0.0
    stop_loss = 0.0
    stop_gain = 0.0
    quantity = 0
    risk_value = 0.0
    
    # Lógica de Compra (Baseada na pesquisa científica anterior)
    # Condição 1: Tendência de Alta (Preço > EMA21 e EMA21 > EMA50)
    trend_ok = last['Close'] > last['EMA21'] and last['EMA21'] > last['EMA50']
    
    # Condição 2: Momentum (RSI entre 40 e 70 - Espaço para subir)
    rsi_ok = 40 < last['RSI'] < 70
    
    # Condição 3: Gatilho (Cruzamento ou Força)
    # Ex: MACD positivo e Histograma crescendo
    macd_ok = last['MACD_12_26_9'] > last['MACDs_12_26_9']
    
    if trend_ok and rsi_ok and macd_ok:
        signal = "COMPRA (SWING)"
        color = "green"
        entry_price = last['Close']
        
        # Cálculo de Risk Management Científico
        # Stop Loss Técnico: 2x ATR abaixo da entrada
        stop_loss = entry_price - (2.0 * last['ATR'])
        
        # Stop Gain (Alvo): Mínimo 1:2 ou 1:3 de Risco/Retorno
        risk_per_share = entry_price - stop_loss
        reward_target = entry_price + (3.0 * risk_per_share) # Alvo 1:3
        stop_gain = reward_target
        
        # Dimensionamento de Posição (Position Sizing)
        risk_value = capital * (risco_por_operacao / 100)
        if risk_per_share > 0:
            quantity = int(risk_value / risk_per_share)
        else:
            quantity = 0
            
    # Lógica de Venda (Exemplo simplificado)
    elif last['Close'] < last['EMA50']:
        signal = "VENDA / AGUARDAR"
        color = "red"

    return {
        "signal": signal,
        "color": color,
        "entry": entry_price,
        "stop_loss": stop_loss,
        "stop_gain": stop_gain,
        "quantity": quantity,
        "risk_value": risk_value,
        "last_rsi": last['RSI'],
        "last_macd": last['MACD_12_26_9']
    }

# --- Execução Principal ---
if st.sidebar.button("Analisar Ativo"):
    with st.spinner('Baixando dados e processando indicadores...'):
        df = get_data(ticker, periodo)
        
        if df is not None and not df.empty:
            df = analyze_swing_trade(df)
            result = generate_signal(df, risco_por_operacao)
            
            # 1. Exibição de Métricas (KPIs)
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Sinal", result['signal'], delta_color="normal")
            col2.metric("Preço Atual", f"R$ {df['Close'].iloc[-1]:.2f}")
            col3.metric("RSI (14)", f"{result['last_rsi']:.2f}")
            col4.metric("MACD", f"{result['last_macd']:.4f}")
            
            # 2. Painel de Operação (Se houver sinal de compra)
            if result['signal'] == "COMPRA (SWING)":
                st.success(f"✅ Oportunidade Identificada em {ticker}")
                k1, k2, k3, k4 = st.columns(4)
                k1.info(f"🎯 **Entrada:** R$ {result['entry']:.2f}")
                k2.error(f"🛑 **Stop Loss:** R$ {result['stop_loss']:.2f}")
                k3.success(f"💰 **Stop Gain:** R$ {result['stop_gain']:.2f}")
                k4.warning(f"📦 **Qtd Ações:** {result['quantity']} (Risco: R$ {result['risk_value']:.2f})")
                
                st.info(f"💡 **Relação Risco/Retorno:** 1:3 (Baseado em ATR)")
            else:
                st.warning("⚠️ Nenhum sinal de compra claro no momento. Aguarde configuração.")
            
            # 3. Gráfico Interativo
            st.subheader("Análise Gráfica")
            fig = go.Figure()
            
            # Candlestick
            fig.add_trace(go.Candlestick(x=df.index,
                            open=df['Open'], high=df['High'],
                            low=df['Low'], close=df['Close'], name='Preço'))
            
            # Médias Móveis
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA21'], line=dict(color='orange', width=1), name='EMA 21'))
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA50'], line=dict(color='blue', width=1), name='EMA 50'))
            
            # Marcadores de Compra (Exemplo visual)
            # (Em um app avançado, plotaríamos apenas onde houve sinal)
            
            fig.update_layout(height=600, xaxis_rangeslider_visible=False, template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)
            
            # 4. Tabela de Dados Recentes
            with st.expander("Ver Dados Técnicos Recentes"):
                st.dataframe(df[['Close', 'EMA21', 'EMA50', 'RSI', 'ATR']].tail(10))
        else:
            st.error("Não foi possível obter dados para este ativo. Verifique o ticker (ex: use .SA para B3).")

# --- Rodapé ---
st.markdown("---")
st.caption("Desenvolvido com Python, Streamlit e Pandas_TA. Dados fornecidos por Yahoo Finance.")
