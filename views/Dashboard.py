import streamlit as st
import yfinance as yf
import numpy as np
import pandas as pd
import plotly.graph_objects as go

TICKER = "^INDIAVIX"
LOOKBACK = 255

# Palette (validated categorical order — see dataviz skill)
COLOR_HISTORY = "#2a78d6"   # categorical slot 1 (blue)
COLOR_TODAY = "#eb6834"     # categorical slot 2 (orange)
COLOR_MUTED = "#898781"     # axis/gridline ink for the mean reference line

st.title("📊 India VIX Dashboard")


@st.cache_data(ttl=900, show_spinner=False)
def fetch_vix_history() -> pd.Series:
    """Daily India VIX closes, NaNs dropped, sorted ascending. Cached 15 min."""
    df = yf.Ticker(TICKER).history(period="2y")
    close = df["Close"].dropna()
    close.index = close.index.tz_localize(None)
    close.name = "close"
    return close


def percentile_rank(level: float, reference: np.ndarray) -> float:
    """Percent of `reference` below `level` (mid-rank: ties count as half)."""
    ref = reference[~np.isnan(reference)]
    if ref.size == 0:
        return float("nan")
    below = float((ref < level).sum())
    ties = float((ref == level).sum())
    return 100.0 * (below + 0.5 * ties) / ref.size


series = fetch_vix_history()

if series.empty:
    st.error("No India VIX data returned. Yahoo may be rate-limiting — try again shortly.")
    st.stop()

lookback = min(LOOKBACK, len(series))
if lookback < LOOKBACK:
    st.caption(f"Only {lookback} sessions available; using all of them instead of {LOOKBACK}.")

window = series.iloc[-lookback:]
values = window.to_numpy()
level = float(values[-1])
reference = values[:-1]  # prior sessions only — today is the test point

mean_val = float(values.mean())
pct = percentile_rank(level, reference)

col1, col2, col3 = st.columns(3)
col1.metric(f"Mean VIX ({lookback}d)", f"{mean_val:.2f}")
col2.metric("Today's VIX", f"{level:.2f}", help=f"As of {window.index[-1]:%d %b %Y}")
col3.metric("Today's Percentile", f"{pct:.1f}th", help=f"Rank within the prior {reference.size} sessions")

fig = go.Figure()
fig.add_trace(go.Bar(
    x=window.index[:-1],
    y=values[:-1],
    name="Prior sessions",
    marker_color=COLOR_HISTORY,
    hovertemplate="%{x|%d %b %Y}<br>VIX: %{y:.2f}<extra></extra>",
))
fig.add_trace(go.Bar(
    x=[window.index[-1]],
    y=[level],
    name="Today",
    marker_color=COLOR_TODAY,
    hovertemplate="%{x|%d %b %Y}<br>VIX: %{y:.2f} (today)<extra></extra>",
))
fig.add_hline(
    y=mean_val,
    line_dash="dash",
    line_color=COLOR_MUTED,
    annotation_text=f"Mean {mean_val:.2f}",
    annotation_position="top left",
)
fig.update_layout(
    title=f"India VIX — trailing {lookback} sessions",
    template="plotly_white",
    yaxis_title="VIX",
    bargap=0.15,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    margin=dict(t=60),
)

st.plotly_chart(fig, width="stretch")

st.caption(
    f"Today's reading of **{level:.2f}** ({window.index[-1]:%d %b %Y}) sits at the "
    f"**{pct:.1f}th percentile** of the prior {reference.size} sessions."
)
