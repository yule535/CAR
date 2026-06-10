import streamlit as st
import yfinance as yf
import pandas as pd
import io
import traceback
from datetime import date, timedelta

# --- Core Logic Functions ---
def analyze_stock(ticker_symbol):
    """
    Replicates the complete logic:
    1. Finds the 52-week High Date using Daily Highs.
    2. Fetches Close prices from that High Date to Today.
    3. Calculates the Cumulative Average (Expanding Mean).
    4. Determines Signal based on the last 10 days trend.
    """
    # Append .NS for Indian stocks (NSE) if no suffix is provided
    yf_ticker = ticker_symbol
    if not (yf_ticker.endswith(".NS") or yf_ticker.endswith(".BO") or "." in yf_ticker):
        yf_ticker += ".NS"
        
    try:
        ticker_obj = yf.Ticker(yf_ticker)
        
        # 1. FIND 52-WEEK HIGH DATE
        # Replicates: to_date(index(sort(GOOGLEFINANCE(..., "high", today()-364, ...), 2, 0), 2, 1))
        # We fetch 1 year of daily data
        hist_1y = ticker_obj.history(period="1y")
        if hist_1y.empty:
            return None, None
            
        # Find the date where the 'High' price was at its maximum
        high_date = hist_1y['High'].idxmax()
        
        # 2. FETCH CLOSE PRICES FROM HIGH DATE TO TODAY
        # Replicates: GOOGLEFINANCE(..., "close", High_Date, TODAY())
        df = ticker_obj.history(start=high_date)
        if df.empty:
            return None, None

        df = df[['Close']].copy()
        df.reset_index(inplace=True)
        df['Date'] = df['Date'].dt.date
        
        # 3. CUMULATIVE AVERAGE (Expanding Mean)
        # Replicates: =MAP(SEQUENCE(COUNT(D2:D)), LAMBDA(n, AVERAGE(OFFSET(D2, 0, 0, n))))
        df['Cumulative_Average'] = df['Close'].expanding().mean()
        df.insert(0, 'Ticker', ticker_symbol)
        
        # 4. SIGNAL CALCULATION (Last 10 Days)
        # Replicates: SUMPRODUCT(--(G2:G10 > G3:G11)) = 9
        # This checks if the Cumulative Average has INCREASED for 9 consecutive intervals (10 days).
        if len(df) >= 10:
            last_10_days_avg = df['Cumulative_Average'].tail(10).tolist()
            
            increases = 0
            for i in range(1, 10):
                # If today's average is greater than yesterday's average
                if last_10_days_avg[i] > last_10_days_avg[i-1]:
                    increases += 1
            
            if increases == 9:
                signal = "BUY / AVERAGE OUT"
            else:
                signal = "AVOID / HOLD"
        else:
            signal = "Insufficient Data (<10 days)"

        summary = {
            "Stock Code": ticker_symbol,
            "High Date (52W)": high_date.date(),
            "Latest Date": df['Date'].iloc[-1],
            "Latest Close": round(df['Close'].iloc[-1], 2),
            "Latest Cum. Avg": round(df['Cumulative_Average'].iloc[-1], 2),
            "Signal": signal
        }
        return summary, df
    except Exception as e:
        st.sidebar.error(f"Error analyzing {ticker_symbol}: {e}")
        return None, None

# --- Streamlit UI Layout ---
st.set_page_config(page_title="Genius Stock Signal Pro", layout="wide")

st.title("🚀 Genius Stock Signal Pro")
st.markdown("""
This application replicates your Google Sheets logic fully automated:
1. **Identifies the 52-week High Date** for every stock automatically.
2. **Calculates Cumulative Average** starting from that high point.
3. **Generates a Signal** by checking if the Cumulative Average has been strictly increasing for the last 10 trading days.
""")

with st.sidebar:
    st.header("Stock Configuration")
    # Text area for bulk stock list
    raw_stock_list = st.text_area(
        "Enter Stock Symbols (one per line):", 
        value="INDUSINDBK\nRELAXO\nBATAINDIA\nDRREDDY\nHAL\nINFY\nTRENT",
        height=300
    )

    signal_filter = st.multiselect(
        "Filter Market Signal Summary",
        options=["BUY / AVERAGE OUT", "AVOID / HOLD"],
        default=["BUY / AVERAGE OUT", "AVOID / HOLD"]
    )
    
    run_button = st.button("Run Global Analysis", type="primary")

# Persist analysis data across reruns so table updates and filters do not disappear
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None
if 'selected_ticker' not in st.session_state:
    st.session_state.selected_ticker = None

status_text = st.empty()

# --- Execution ---
if run_button:
    stock_list = [s.strip().upper() for s in raw_stock_list.split('\n') if s.strip()]

    if not stock_list:
        st.error("Please provide at least one stock symbol.")
    else:
        summary_data = []
        all_calculations = []

        progress_bar = st.progress(0)
        status_text.text("Starting analysis...")

        for i, stock in enumerate(stock_list):
            status_text.text(f"🔍 Analyzing {stock}...")
            summary, calc_df = analyze_stock(stock)

            if summary:
                summary_data.append(summary)
                all_calculations.append(calc_df)

            progress_bar.progress((i + 1) / len(stock_list))

        if summary_data:
            final_summary_df = pd.DataFrame(summary_data)
            final_calc_df = pd.concat(all_calculations, ignore_index=True)
            st.session_state.analysis_results = {
                'final_summary_df': final_summary_df,
                'final_calc_df': final_calc_df,
            }

            if not st.session_state.selected_ticker or st.session_state.selected_ticker not in final_summary_df['Stock Code'].astype(str).tolist():
                st.session_state.selected_ticker = final_summary_df['Stock Code'].astype(str).tolist()[0]
        else:
            st.session_state.analysis_results = None
            st.error("No valid data could be retrieved for the provided symbols.")

if st.session_state.analysis_results is not None:
    final_summary_df = st.session_state.analysis_results['final_summary_df']
    final_calc_df = st.session_state.analysis_results['final_calc_df']

    # Create display-friendly Signal column (emoji fallback for compatibility)
    def signal_display_text(val):
        if val == "BUY / AVERAGE OUT":
            return "BUY / AVERAGE OUT 🟢"
        elif val == "AVOID / HOLD":
            return "AVOID / HOLD 🔴"
        return val

    final_summary_df['Signal_Display'] = final_summary_df['Signal'].apply(signal_display_text)

    # Apply signal filter to the display summary
    if signal_filter:
        filtered_summary_df = final_summary_df[final_summary_df['Signal'].isin(signal_filter)].copy()
    else:
        filtered_summary_df = final_summary_df.copy()

    st.subheader("Market Signal Summary")

    use_fallback = False
    available = filtered_summary_df['Stock Code'].astype(str).tolist()
    current_selected = st.session_state.get('selected_ticker', available[0]) if available else None

    try:
        from st_aggrid import AgGrid
        from st_aggrid.grid_options_builder import GridOptionsBuilder
        from st_aggrid.shared import GridUpdateMode

        display_df = filtered_summary_df[['Stock Code', 'Signal_Display', 'Latest Close', 'Latest Cum. Avg', 'Latest Date']].copy()
        display_df['Latest Date'] = display_df['Latest Date'].astype(str)

        gb = GridOptionsBuilder.from_dataframe(display_df)
        gb.configure_selection(selection_mode='single', use_checkbox=False)
        gb.configure_columns(display_df.columns.tolist())
        grid_options = gb.build()

        try:
            grid_response = AgGrid(
                display_df,
                gridOptions=grid_options,
                update_mode=GridUpdateMode.SELECTION_CHANGED,
                fit_columns_on_grid_load=True,
                allow_unsafe_jscode=True,
                key='summary_aggrid'
            )
            selected = grid_response.get('selected_rows', [])
            if selected:
                sel = selected[0].get('Stock Code')
                try:
                    sel = str(sel)
                except Exception:
                    sel = None

                if sel in available:
                    current_selected = sel
                elif sel and sel.endswith('.NS') and sel[:-3] in available:
                    current_selected = sel[:-3]

        except Exception as inner_e:
            use_fallback = True
            st.sidebar.error("AgGrid rendering/interaction error — falling back to simple table.")
            st.sidebar.exception(inner_e)
            st.sidebar.write(traceback.format_exc())

    except Exception as import_e:
        use_fallback = True
        st.sidebar.error("st_aggrid not available or failed to import — using fallback table.")
        st.sidebar.exception(import_e)
        st.sidebar.write(traceback.format_exc())

    if use_fallback:
        st.markdown("**Click 'View' to load a stock into the Historical Data Explorer below.**")

        display_df = filtered_summary_df[['Stock Code', 'Signal_Display', 'Latest Close', 'Latest Date']].copy()
        display_df['Latest Date'] = display_df['Latest Date'].astype(str)

        header_cols = st.columns([2, 1, 1, 1])
        header_cols[0].write("**Stock Code**")
        header_cols[1].write("**Signal**")
        header_cols[2].write("**Latest Close**")
        header_cols[3].write("")

        for _, row in display_df.iterrows():
            c0, c1, c2, c3 = st.columns([2, 1, 1, 1])
            c0.write(row['Stock Code'])
            c1.write(row.get('Signal_Display', ''))
            c2.write(row['Latest Close'])
            if c3.button("View", key=f"view_{row['Stock Code']}"):
                current_selected = row['Stock Code']

    if current_selected:
        st.session_state['selected_ticker'] = current_selected

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        final_summary_df.to_excel(writer, sheet_name='Summary', index=False)
        final_calc_df.to_excel(writer, sheet_name='All_Daily_Calculations', index=False)

    st.download_button(
        label="📥 Download Detailed Report (Excel)",
        data=output.getvalue(),
        file_name=f"Stock_Analysis_{date.today()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.divider()
    st.subheader("Historical Data Explorer")

    if filtered_summary_df.empty:
        st.warning("No stocks match the selected signal filter. Adjust the filter to view data.")
        available_list = []
    else:
        available_list = filtered_summary_df['Stock Code'].astype(str).tolist()
        if 'selected_ticker' not in st.session_state or st.session_state.get('selected_ticker') not in available_list:
            st.session_state['selected_ticker'] = available_list[0]

    if available_list:
        try:
            default_index = available_list.index(st.session_state['selected_ticker'])
        except ValueError:
            default_index = 0

        selected_ticker = st.selectbox(
            "Select a stock to view daily calculations:",
            available_list,
            index=default_index
        )

        st.session_state['selected_ticker'] = selected_ticker

        stock_detail = final_calc_df[final_calc_df['Ticker'] == selected_ticker]
        st.dataframe(stock_detail, use_container_width=True, hide_index=True)
else:
    if not st.session_state.analysis_results:
        st.info("Press Run Global Analysis to generate the report.")

status_text.text("Analysis Complete!")
