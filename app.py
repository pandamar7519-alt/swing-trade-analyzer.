import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import re

# --- Configuração da Página ---
st.set_page_config(
    page_title="Swing Trade Analyzer", 
    layout="wide",
    page_icon="📊"
)

# --- Título e Disclaimer ---
st.title("📊 Analisador Científico de Swing Trade")
st.markdown("""
    **Atenção:** Esta ferramenta utiliza análise técnica baseada em indicadores estatísticos. 
    **Não constitui recomendação de investimento.** O mercado de renda variável envolve riscos.
    Sempre faça sua própria análise (DYOR) e consulte um profissional certificado.
""")

# --- Barra Lateral de Inputs ---
st.sidebar.header("⚙️ Configurações da Operação")

# Input do ticker com validação
ticker = st.sidebar.text_input(
    "🏷️ Ativo (Ex: PETR4.SA, AAPL)", 
    "PETR4.SA",
    help="Use .SA para ações da B3 ou código direto para NYSE/NASDAQ"
)

# Validação básica do ticker
def validate_ticker(ticker):
    """Valida formato básico do ticker"""
    if not ticker or len(ticker.strip()) < 3:
        return False
    ticker_clean = ticker.strip().upper()
    pattern = r'^[A-Z0-9.\-]+$'
    return bool(re.match(pattern, ticker_clean))

# Período de dados expandido até 5 anos
# ✅ Padrão ajustado para 1y (índice 3) - ideal para iniciantes
periodo = st.sidebar.selectbox(
    "📅 Período de Dados", 
    options=["1mo", "3mo", "6mo", "1y", "2y", "5y"],
    index=3,
    help="Períodos maiores fornecem mais contexto histórico para análise"
)

# Capital com limites e validação
# ✅ Padrão ajustado para R$ 1.000 - ideal para iniciantes
capital = st.sidebar.number_input(
    "💰 Capital Disponível (R$)", 
    min_value=100.0,
    max_value=10000.0,
    value=1000.0,
    step=50.0,
    format="%.2f",
    help="Valor entre R$ 100 e R$ 10.000 para cálculo de posição"
)

# Risco por operação com slider mais preciso
# ✅ Padrão ajustado para 1.0% - conservador para iniciantes
risco_por_operacao = st.sidebar.slider(
    "⚠️ Risco por Operação (%)", 
    min_value=0.5,
    max_value=5.0,
    value=1.0,
    step=0.5,
    help="Porcentagem do capital que você aceita perder se o stop-loss for acionado"
)

# Configurações avançadas (opcional)
with st.sidebar.expander("🔧 Configurações Avançadas", expanded=False):
    # ✅ Padrão ajustado para 2.5 - stop nem muito apertado, nem muito folgado
    atr_multiplier = st.slider(
        "🎯 Multiplicador ATR para Stop-Loss",
        min_value=1.0,
        max_value=4.0,
        value=2.5,
        step=0.5,
        help="Fator multiplicador do ATR para calcular distância do stop-loss"
    )
    # ✅ Padrão já estava em 3.0 (índice 3) - relação risco/retorno favorável
    risk_reward_ratio = st.selectbox(
        "📊 Relação Risco/Retorno Alvo",
        options=[1.5, 2.0, 2.5, 3.0, 4.0],
        index=3,
        help="Mínimo de retorno esperado para cada unidade de risco assumido"
    )

# --- Funções de Análise ---
def get_data(ticker, period):
    """Baixa dados históricos do Yahoo Finance com tratamento de erros"""
    try:
        ticker_clean = ticker.strip().upper()
        data = yf.download(ticker_clean, period=period, progress=False)
        
        if data is None or data.empty:
            return None
            
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in data.columns for col in required_cols):
            return None
            
        return data
    except Exception as e:
        st.error(f"❌ Erro ao buscar dados: {str(e)}")
        return None

def analyze_swing_trade(df):
    """Calcula indicadores técnicos para análise de swing trade"""
    df = df.copy()
    
    # Indicadores de Tendência (EMAs)
    df['EMA9'] = ta.ema(df['Close'], length=9)
    df['EMA21'] = ta.ema(df['Close'], length=21)
    df['EMA50'] = ta.ema(df['Close'], length=50)
    
    # Indicadores de Momentum (RSI e MACD)
    df['RSI'] = ta.rsi(df['Close'], length=14)
    
    # MACD com tratamento de nomes de coluna (varia por versão do pandas_ta)
    macd = ta.macd(df['Close'])
    df = pd.concat([df, macd], axis=1)
    
    # Normaliza nomes de colunas do MACD para garantir compatibilidade
    macd_cols = [col for col in df.columns if 'MACD' in col and 'signal' not in col.lower() and 'hist' not in col.lower()]
    macd_sig_cols = [col for col in df.columns if 'MACDs' in col or ('signal' in col.lower() and 'MACD' in col)]
    macd_hist_cols = [col for col in df.columns if 'MACDh' in col or ('hist' in col.lower() and 'MACD' in col)]
    
    if macd_cols:
        df['_MACD'] = df[macd_cols[0]]
    if macd_sig_cols:
        df['_MACD_signal'] = df[macd_sig_cols[0]]
    if macd_hist_cols:
        df['_MACD_hist'] = df[macd_hist_cols[0]]
    
    # Volatilidade (ATR para Stops Dinâmicos)
    df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
    
    # Bandas de Bollinger (opcional - não usado na lógica atual, mas mantido para referência)
    # bbands = ta.bbands(df['Close'], length=20)
    # df = pd.concat([df, bbands], axis=1)

    return df

def calculate_position_size(capital, risk_pct, entry_price, stop_loss):
    """
    Calcula o tamanho da posição baseado no risco
    Fórmula: Posição = (Capital × Risco%) / (Entrada - Stop)
    """
    if entry_price <= 0 or stop_loss >= entry_price:
        return 0, 0.0
    
    risk_value = capital * (risk_pct / 100)
    risk_per_share = entry_price - stop_loss
    
    if risk_per_share <= 0:
        return 0, risk_value
    
    quantity = int(risk_value / risk_per_share)
    position_value = quantity * entry_price
    
    return quantity, risk_value

def generate_signal(df, capital, risk_pct, atr_mult=2.0, rr_ratio=3.0):
    """Gera sinal de trade com cálculos completos de risk management"""
    if len(df) < 50:
        return None
        
    last = df.iloc[-1]
    
    signal = "NEUTRO"
    color = "gray"
    entry_price = 0.0
    stop_loss = 0.0
    stop_gain = 0.0
    quantity = 0
    risk_value = 0.0
    position_value = 0.0
    
    # --- Lógica de Compra (Swing Trade) ---
    # ✅ CORREÇÃO: Comparação segura da EMA21 (evita erro com .shift() em valor escalar)
    ema21_rising = df['EMA21'].iloc[-1] > df['EMA21'].iloc[-2]
    
    trend_ok = (
        last['Close'] > last['EMA21'] and 
        last['EMA21'] > last['EMA50'] and
        ema21_rising
    )
    
    rsi_ok = 40 < last['RSI'] < 70
    
    # ✅ CORREÇÃO: Usa nomes normalizados do MACD para evitar KeyError
    try:
        macd_val = last.get('_MACD', 0)
        macd_sig = last.get('_MACD_signal', 0)
        macd_hist = last.get('_MACD_hist', 0)
        macd_ok = macd_val > macd_sig and macd_hist > 0
    except:
        macd_ok = False  # Fallback seguro
    
    # ✅ REMOVIDO: bb_ok não era usado e causava KeyError
    # bb_ok = last['Close'] > last['BBL_20_2.0']  # ❌ Removido
    
    if trend_ok and rsi_ok and macd_ok:
        signal = "COMPRA (SWING)"
        color = "green"
        entry_price = last['Close']
        
        # Stop Loss Técnico: baseado em ATR
        stop_loss = entry_price - (atr_mult * last['ATR'])
        stop_loss = max(stop_loss, last['EMA50'] * 0.98)
        
        # Stop Gain: baseado na relação risco/retorno
        risk_per_share = entry_price - stop_loss
        reward_target = entry_price + (rr_ratio * risk_per_share)
        stop_gain = reward_target
        
        # Dimensionamento de Posição
        quantity, risk_value = calculate_position_size(
            capital, risk_pct, entry_price, stop_loss
        )
        position_value = quantity * entry_price
        
        # Validação: posição não pode exceder capital
        if position_value > capital:
            quantity = int(capital / entry_price)
            position_value = quantity * entry_price
            risk_value = (entry_price - stop_loss) * quantity
            
    elif last['Close'] < last['EMA50']:
        signal = "AGUARDAR / VENDA"
        color = "red"
    elif last['RSI'] > 75:
        signal = "SOBRECOMPRA - AGUARDAR"
        color = "orange"
    elif last['RSI'] < 30:
        signal = "SOBREVENDA - OPORTUNIDADE?"
        color = "yellow"

    return {
        "signal": signal,
        "color": color,
        "entry": entry_price,
        "stop_loss": stop_loss,
        "stop_gain": stop_gain,
        "quantity": quantity,
        "risk_value": risk_value,
        "position_value": position_value,
        "last_rsi": last['RSI'],
        "last_macd": last.get('_MACD', 0),
        "last_atr": last['ATR'],
        "trend_ok": trend_ok,
        "rsi_ok": rsi_ok,
        "macd_ok": macd_ok
    }

# --- Execução Principal ---
if st.sidebar.button("🔍 Analisar Ativo", type="primary"):
    
    # Validações antes de executar
    if not validate_ticker(ticker):
        st.error("❌ Formato de ticker inválido. Exemplos: PETR4.SA, AAPL, TSLA")
        st.stop()
    
    if capital < 100 or capital > 10000:
        st.error("❌ Capital deve estar entre R$ 100 e R$ 10.000")
        st.stop()
    
    with st.spinner(f'📡 Buscando dados de {ticker.strip().upper()}...'):
        df = get_data(ticker, periodo)
        
        if df is not None and not df.empty:
            df = analyze_swing_trade(df)
            result = generate_signal(df, capital, risco_por_operacao, atr_multiplier, risk_reward_ratio)
            
            if result is None:
                st.warning("⚠️ Dados insuficientes para análise. Tente um período maior.")
                st.stop()
            
            # === 1. Painel de Sinal Principal ===
            st.subheader(f"🎯 Resultado da Análise: {ticker.strip().upper()}")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(label="📡 Sinal", value=result['signal'])
            
            with col2:
                st.metric(
                    label="💲 Preço Atual",
                    value=f"R$ {df['Close'].iloc[-1]:.2f}",
                    delta=f"{df['Close'].pct_change().iloc[-1]*100:.2f}%"
                )
            
            with col3:
                rsi_val = result['last_rsi']
                rsi_emoji = "🟢" if 40 < rsi_val < 70 else "🔴" if rsi_val > 70 or rsi_val < 30 else "🟡"
                st.metric(label="📊 RSI (14)", value=f"{rsi_emoji} {rsi_val:.1f}")
            
            with col4:
                st.metric(label="📈 MACD", value=f"{result['last_macd']:.4f}")
            
            # === 2. Painel de Operação (apenas para sinal de compra) ===
            if result['signal'] == "COMPRA (SWING)":
                st.success(f"✅ **Oportunidade de COMPRA identificada em {ticker.strip().upper()}**")
                
                k1, k2, k3, k4 = st.columns(4)
                
                with k1:
                    st.info(f"🎯 **Entrada**\n- Preço: **R$ {result['entry']:.2f}**\n- ATR: {result['last_atr']:.2f}")
                
                with k2:
                    dist_stop = ((result['entry'] - result['stop_loss'])/result['entry']*100)
                    st.error(f"🛑 **Stop-Loss**\n- Preço: **R$ {result['stop_loss']:.2f}**\n- Distância: {dist_stop:.2f}%")
                
                with k3:
                    dist_gain = ((result['stop_gain'] - result['entry'])/result['entry']*100)
                    st.success(f"💰 **Alvo**\n- Preço: **R$ {result['stop_gain']:.2f}**\n- Potencial: {dist_gain:.2f}%")
                
                with k4:
                    st.warning(f"📦 **Posição**\n- Qtd: **{result['quantity']} ações**\n- Valor: R$ {result['position_value']:.2f}\n- Risco: R$ {result['risk_value']:.2f}")
                
                # Resumo de Risk/Reward
                if result['stop_loss'] > 0 and result['entry'] > result['stop_loss']:
                    potential_profit = result['stop_gain'] - result['entry']
                    potential_loss = result['entry'] - result['stop_loss']
                    rr_actual = potential_profit / potential_loss if potential_loss > 0 else 0
                    
                    st.markdown(f"""
                    <div style='background-color: #1e3a5f; padding: 15px; border-radius: 10px; margin: 10px 0;'>
                        <strong>📋 Resumo da Operação:</strong><br>
                        • Relação Risco/Retorno: <strong>1:{rr_actual:.1f}</strong> (Alvo: 1:{risk_reward_ratio})<br>
                        • Capital em uso: <strong>{(result['position_value']/capital*100):.1f}%</strong><br>
                        • Risco total: <strong>R$ {result['risk_value']:.2f}</strong> ({risco_por_operacao}% do capital)
                    </div>
                    """, unsafe_allow_html=True)
                    
            else:
                if result['signal'] == "AGUARDAR / VENDA":
                    st.warning(f"⚠️ {ticker.strip().upper()} abaixo da EMA50 - Tendência de baixa. Aguarde reversão.")
                elif result['signal'] == "SOBRECOMPRA - AGUARDAR":
                    st.warning(f"⚠️ RSI elevado ({result['last_rsi']:.1f}) - Aguarde correção.")
                elif result['signal'] == "SOBREVENDA - OPORTUNIDADE?":
                    st.info(f"💡 RSI baixo ({result['last_rsi']:.1f}) - Pode indicar oportunidade, confirme com outros indicadores.")
                else:
                    st.info("ℹ️ Condições atuais não atendem aos critérios. Continue monitorando.")
            
            # === 3. Gráfico Interativo ===
            st.subheader("📈 Análise Gráfica")
            
            fig = go.Figure()
            
            fig.add_trace(go.Candlestick(
                x=df.index, open=df['Open'], high=df['High'],
                low=df['Low'], close=df['Close'], name='Preço',
                increasing_line_color='#00cc96', decreasing_line_color='#ef553b'
            ))
            
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA21'], line=dict(color='orange', width=2), name='EMA 21'))
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA50'], line=dict(color='blue', width=2), name='EMA 50'))
            
            if result['signal'] == "COMPRA (SWING)" and result['entry'] > 0:
                fig.add_trace(go.Scatter(x=[df.index[-1]], y=[result['entry']], mode='markers', marker=dict(symbol='triangle-up', size=15, color='green'), name='🎯 Entrada'))
                fig.add_trace(go.Scatter(x=[df.index[-1]], y=[result['stop_loss']], mode='markers', marker=dict(symbol='x', size=12, color='red'), name='🛑 Stop'))
                fig.add_trace(go.Scatter(x=[df.index[-1]], y=[result['stop_gain']], mode='markers', marker=dict(symbol='star', size=12, color='gold'), name='💰 Alvo'))
            
            fig.update_layout(height=600, xaxis_rangeslider_visible=False, template="plotly_dark", title=f"{ticker.strip().upper()} - Análise Técnica", hovermode='x unified')
            st.plotly_chart(fig, use_container_width=True)
            
            # === 4. Tabela de Dados Técnicos ===
            with st.expander("📋 Ver Dados Técnicos Recentes", expanded=False):
                display_df = df[['Close', 'EMA21', 'EMA50', 'RSI', 'ATR']].tail(10).copy()
                display_df.columns = ['Preço', 'EMA 21', 'EMA 50', 'RSI', 'ATR']
                st.dataframe(display_df.style.format({
                    'Preço': 'R$ {:.2f}', 'EMA 21': 'R$ {:.2f}', 'EMA 50': 'R$ {:.2f}',
                    'RSI': '{:.1f}', 'ATR': '{:.2f}'
                }), use_container_width=True)
                
        else:
            st.error(f"❌ Não foi possível obter dados para '{ticker}'. Verifique o ticker e tente novamente.")

# --- Rodapé ---
st.markdown("---")
st.caption("🔧 Python • Streamlit • Pandas_TA • yfinance • Plotly | 📊 Dados: Yahoo Finance | ⚠️ Uso educacional")

# --- Ajuda ---
with st.expander("❓ Ajuda e Referências"):
    st.markdown("""
    ### 📚 Como usar:
    1. Digite o ticker (ex: `PETR4.SA`, `AAPL`)
    2. Selecione o período (até 5 anos)
    3. Informe capital (R$ 100 - R$ 10.000) e risco (0,5% - 5%)
    4. Clique em "Analisar Ativo"
    
    ### 🎯 Sinais:
    - 🟢 **COMPRA**: Condições favoráveis
    - 🔴 **AGUARDAR**: Tendência de baixa
    - 🟡 **SOBREVENDA**: RSI < 30, possível oportunidade
    - 🟠 **SOBRECOMPRA**: RSI > 75, aguarde correção
    
    ### 📐 Cálculos:
    - **Stop-Loss**: Entrada - (ATR × multiplicador)
    - **Posição**: `(Capital × Risco%) ÷ (Entrada - Stop)`
    - **Alvo**: Entrada + (Risco × Relação Risco/Retorno)
    """)
