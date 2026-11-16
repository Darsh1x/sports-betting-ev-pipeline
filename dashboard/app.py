import altair as alt
import pandas as pd
import streamlit as st

from data import load_opportunities, source_name

INK = "#1f6feb"

st.set_page_config(page_title="+EV Opportunities", layout="wide")


@st.cache_data(ttl=300)
def get_data():
    return load_opportunities()


def fmt_price(price):
    return f"+{price}" if price > 0 else str(price)


df = get_data()

st.title("+EV Opportunities")
st.caption(
    "Prices that beat the no-vig consensus fair probability across sportsbooks. "
    "A data pipeline demo, not betting advice."
)
if source_name() == "sample":
    st.info("Showing generated sample data. Set DATA_SOURCE=snowflake to use the live warehouse.")

with st.sidebar:
    st.header("Filters")
    min_ev = st.slider("Minimum EV", 0.02, 0.20, 0.02, 0.005, format="%.3f")
    books = sorted(df["bookmaker_title"].unique())
    chosen_books = st.multiselect("Sportsbooks", books, default=books)
    best_only = st.checkbox("Best price per outcome only", value=False)

filtered = df[(df["expected_value"] >= min_ev) & (df["bookmaker_title"].isin(chosen_books))]
if best_only:
    filtered = filtered[filtered["is_best_price"]]

current_tab, history_tab = st.tabs(["Current opportunities", "History"])

with current_tab:
    latest = filtered[filtered["is_latest_snapshot"]]
    snapshot_time = df.loc[df["is_latest_snapshot"], "fetched_at"].max()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Open opportunities", len(latest))
    c2.metric("Best EV", f"{latest['expected_value'].max():.1%}" if len(latest) else "n/a")
    c3.metric("Average edge", f"{latest['edge'].mean():.1%}" if len(latest) else "n/a")
    c4.metric("Games with edges", latest["event_id"].nunique())
    st.caption(f"Latest snapshot: {snapshot_time:%b %d, %H:%M} UTC")

    if latest.empty:
        st.write("No opportunities in the latest snapshot match these filters.")
    else:
        table = latest.sort_values("expected_value", ascending=False).assign(
            Game=lambda d: d["away_team"] + " @ " + d["home_team"],
            Bet=lambda d: d["outcome_name"],
            Book=lambda d: d["bookmaker_title"],
            Price=lambda d: d["price_american"].map(fmt_price),
            Fair=lambda d: d["consensus_fair_prob"] * 100,
            Edge=lambda d: d["edge"] * 100,
            EV=lambda d: d["expected_value"] * 100,
            Books=lambda d: d["book_count"],
            Kickoff=lambda d: d["commence_time"].dt.strftime("%a %b %d %H:%M"),
        )[["Game", "Bet", "Book", "Price", "Fair", "Edge", "EV", "Books", "Kickoff"]]
        st.dataframe(
            table,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Fair": st.column_config.NumberColumn(format="%.1f%%", help="Consensus no-vig probability"),
                "Edge": st.column_config.NumberColumn(format="%.1f%%", help="Fair probability minus the price's implied probability"),
                "EV": st.column_config.NumberColumn(format="%.1f%%", help="Expected profit per $1 at the fair probability"),
            },
        )

with history_tab:
    st.caption(
        "How often and where edges appeared. Win/loss results need game scores, "
        "which the pipeline does not ingest yet."
    )
    if filtered.empty:
        st.write("No opportunities match these filters.")
    else:
        per_snapshot = (
            filtered.groupby("fetched_at")
            .agg(opportunities=("expected_value", "size"), avg_ev=("expected_value", "mean"))
            .reset_index()
        )
        left, right = st.columns(2)

        with left:
            st.subheader("Opportunities per snapshot")
            st.altair_chart(
                alt.Chart(per_snapshot)
                .mark_line(color=INK, strokeWidth=2, point=alt.OverlayMarkDef(size=60, color=INK))
                .encode(
                    x=alt.X("fetched_at:T", title=None),
                    y=alt.Y("opportunities:Q", title=None, scale=alt.Scale(zero=True)),
                    tooltip=[
                        alt.Tooltip("fetched_at:T", title="Snapshot (UTC)"),
                        alt.Tooltip("opportunities:Q", title="Opportunities"),
                        alt.Tooltip("avg_ev:Q", title="Average EV", format=".1%"),
                    ],
                )
                .properties(height=280),
                use_container_width=True,
            )

        with right:
            st.subheader("Average EV by sportsbook")
            by_book = (
                filtered.groupby("bookmaker_title")
                .agg(avg_ev=("expected_value", "mean"), opportunities=("expected_value", "size"))
                .reset_index()
                .sort_values("avg_ev", ascending=False)
            )
            st.altair_chart(
                alt.Chart(by_book)
                .mark_bar(color=INK, size=14, cornerRadiusEnd=4)
                .encode(
                    y=alt.Y("bookmaker_title:N", sort="-x", title=None),
                    x=alt.X("avg_ev:Q", title=None, axis=alt.Axis(format="%")),
                    tooltip=[
                        alt.Tooltip("bookmaker_title:N", title="Sportsbook"),
                        alt.Tooltip("avg_ev:Q", title="Average EV", format=".1%"),
                        alt.Tooltip("opportunities:Q", title="Opportunities"),
                    ],
                )
                .properties(height=280),
                use_container_width=True,
            )

        with st.expander("View data as a table"):
            st.dataframe(per_snapshot, hide_index=True, use_container_width=True)
