import streamlit as st
import yfinance as yf
import pandas as pd
import io
from datetime import date, timedelta

INSUFFICIENT = "Insufficient Data (<10 days)"
SIGNAL_OPTIONS = ["BUY / AVERAGE OUT", "AVOID / HOLD", INSUFFICIENT]


# --- Core Logic Functions ---
@st.cache_data(ttl=900, show_spinner=False)
def fetch_history(yf_ticker: str) -> pd.DataFrame:
    """Fetch ~52 weeks of daily data. Cached for 15 minutes."""
    start = date.today() - timedelta(days=364)
    return yf.Ticker(yf_ticker).history(start=start)


def normalize_ticker(ticker_symbol: str) -> str:
    """Append .NS for Indian (NSE) stocks if no exchange suffix is provided."""
    return ticker_symbol if "." in ticker_symbol else ticker_symbol + ".NS"


def analyze_stock(ticker_symbol: str):
    """
    1. Finds the 52-week High Date using Daily Highs.
    2. Slices Close prices from that High Date to Today (no second fetch).
    3. Calculates the Cumulative Average (Expanding Mean).
    4. Determines Signal: Cumulative Average strictly increasing for the
       last 9 intervals (10 days).

    Returns (summary_dict | None, calc_df | None, error_msg | None).
    """
    yf_ticker = normalize_ticker(ticker_symbol)

    try:
        hist_1y = fetch_history(yf_ticker)
        if hist_1y.empty:
            return None, None, f"No data returned for {ticker_symbol} ({yf_ticker})."

        # 1. 52-week high date
        high_date = hist_1y['High'].idxmax()

        # 2. Close prices from high date onward (slice existing data)
        df = hist_1y.loc[high_date:, ['Close']].copy()
        df.reset_index(inplace=True)
        df['Date'] = df['Date'].dt.date

        # 3. Cumulative average (expanding mean)
        df['Cumulative_Average'] = df['Close'].expanding().mean()
        df.insert(0, 'Ticker', ticker_symbol)

        # 4. Signal: strictly increasing cumulative average over last 10 days
        if len(df) >= 10:
            increasing = df['Cumulative_Average'].tail(10).diff().dropna().gt(0).all()
            signal = "BUY / AVERAGE OUT" if increasing else "AVOID / HOLD"
        else:
            signal = INSUFFICIENT

        summary = {
            "Stock Code": ticker_symbol,
            "High Date (52W)": high_date.date(),
            "Latest Date": df['Date'].iloc[-1],
            "Latest Close": round(df['Close'].iloc[-1], 2),
            "Latest Cum. Avg": round(df['Cumulative_Average'].iloc[-1], 2),
            "Signal": signal,
        }
        return summary, df, None

    except Exception as e:
        return None, None, f"Error analyzing {ticker_symbol}: {e}"


def signal_display_text(val: str) -> str:
    if val == "BUY / AVERAGE OUT":
        return "BUY / AVERAGE OUT 🟢"
    if val == "AVOID / HOLD":
        return "AVOID / HOLD 🔴"
    return val


@st.cache_data(show_spinner=False)
def build_excel(summary_df: pd.DataFrame, calc_df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        calc_df.to_excel(writer, sheet_name='All_Daily_Calculations', index=False)
    return output.getvalue()


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
    raw_stock_list = st.text_area(
        "Enter Stock Symbols (one per line):",
        value="INDUSINDBK\nRELAXO\nBATAINDIA\nDRREDDY\nHAL\nINFY\nTRENT",
        height=300,
    )

    signal_filter = st.multiselect(
        "Filter Market Signal Summary",
        options=SIGNAL_OPTIONS,
        default=SIGNAL_OPTIONS,
    )

    run_button = st.button("Run Global Analysis", type="primary")

# Persist analysis data across reruns
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None

status_text = st.empty()

# --- Execution ---
if run_button:
    stock_list = list(dict.fromkeys(  # de-duplicate, preserve order
        s.strip().upper() for s in raw_stock_list.split('\n') if s.strip()
    ))

    if not stock_list:
        st.error("Please provide at least one stock symbol.")
    else:
        summary_data, all_calculations, errors = [], [], []
        progress_bar = st.progress(0)

        for i, stock in enumerate(stock_list):
            status_text.text(f"🔍 Analyzing {stock}...")
            summary, calc_df, err = analyze_stock(stock)

            if summary:
                summary_data.append(summary)
                all_calculations.append(calc_df)
            elif err:
                errors.append(err)

            progress_bar.progress((i + 1) / len(stock_list))

        progress_bar.empty()
        status_text.text("Analysis Complete!")

        for err in errors:
            st.sidebar.error(err)

        if summary_data:
            st.session_state.analysis_results = {
                'final_summary_df': pd.DataFrame(summary_data),
                'final_calc_df': pd.concat(all_calculations, ignore_index=True),
            }
            # Reset selection if it no longer exists
            codes = st.session_state.analysis_results['final_summary_df']['Stock Code'].astype(str).tolist()
            if st.session_state.get('selected_ticker') not in codes:
                st.session_state['selected_ticker'] = codes[0]
        else:
            st.session_state.analysis_results = None
            st.error("No valid data could be retrieved for the provided symbols.")

# --- Display ---
if st.session_state.analysis_results is not None:
    final_summary_df = st.session_state.analysis_results['final_summary_df'].copy()
    final_calc_df = st.session_state.analysis_results['final_calc_df']

    final_summary_df['Signal_Display'] = final_summary_df['Signal'].apply(signal_display_text)

    filtered_summary_df = (
        final_summary_df[final_summary_df['Signal'].isin(signal_filter)].copy()
        if signal_filter else final_summary_df.copy()
    )

    st.subheader("Market Signal Summary")

    use_fallback = False
    available = filtered_summary_df['Stock Code'].astype(str).tolist()
    current_selected = st.session_state.get('selected_ticker')

    try:
        from st_aggrid import AgGrid
        from st_aggrid.grid_options_builder import GridOptionsBuilder
        from st_aggrid.shared import GridUpdateMode

        display_df = filtered_summary_df[
            ['Stock Code', 'Signal_Display', 'Latest Close', 'Latest Cum. Avg', 'Latest Date']
        ].copy()
        display_df['Latest Date'] = display_df['Latest Date'].astype(str)

        gb = GridOptionsBuilder.from_dataframe(display_df)
        gb.configure_selection(selection_mode='single', use_checkbox=False)
        # Allow selecting/copying text from cells (Ctrl/Cmd+C works)
        gb.configure_grid_options(
            enableCellTextSelection=True,
            ensureDomOrder=True,
        )
        grid_options = gb.build()

        grid_response = AgGrid(
            display_df,
            gridOptions=grid_options,
            update_mode=GridUpdateMode.SELECTION_CHANGED,
            fit_columns_on_grid_load=True,
            key='summary_aggrid',
        )

        # st-aggrid < 1.0 returns a list of dicts; >= 1.0 returns a DataFrame
        selected = grid_response.get('selected_rows', None)
        sel = None
        if isinstance(selected, pd.DataFrame) and not selected.empty:
            sel = str(selected.iloc[0]['Stock Code'])
        elif isinstance(selected, list) and selected:
            sel = str(selected[0].get('Stock Code'))

        if sel in available:
            current_selected = sel

    except Exception:
        use_fallback = True

    if use_fallback:
        st.caption("Interactive grid unavailable — using fallback table. "
                   "Click 'View' to load a stock into the explorer below.")

        display_df = filtered_summary_df[['Stock Code', 'Signal_Display', 'Latest Close', 'Latest Date']].copy()
        display_df['Latest Date'] = display_df['Latest Date'].astype(str)

        header_cols = st.columns([2, 1, 1, 1])
        header_cols[0].write("**Stock Code**")
        header_cols[1].write("**Signal**")
        header_cols[2].write("**Latest Close**")

        for _, row in display_df.iterrows():
            c0, c1, c2, c3 = st.columns([2, 1, 1, 1])
            c0.write(row['Stock Code'])
            c1.write(row['Signal_Display'])
            c2.write(row['Latest Close'])
            if c3.button("View", key=f"view_{row['Stock Code']}"):
                current_selected = row['Stock Code']

    if current_selected:
        st.session_state['selected_ticker'] = current_selected

    st.download_button(
        label="📥 Download Detailed Report (Excel)",
        data=build_excel(final_summary_df.drop(columns=['Signal_Display']), final_calc_df),
        file_name=f"Stock_Analysis_{date.today()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.divider()
    st.subheader("Historical Data Explorer")

    if filtered_summary_df.empty:
        st.warning("No stocks match the selected signal filter. Adjust the filter to view data.")
    else:
        if st.session_state.get('selected_ticker') not in available:
            st.session_state['selected_ticker'] = available[0]

        selected_ticker = st.selectbox(
            "Select a stock to view daily calculations:",
            available,
            index=available.index(st.session_state['selected_ticker']),
        )
        st.session_state['selected_ticker'] = selected_ticker

        stock_detail = final_calc_df[final_calc_df['Ticker'] == selected_ticker]
        st.dataframe(stock_detail, use_container_width=True, hide_index=True)
else:
    st.info("Press Run Global Analysis to generate the report.")