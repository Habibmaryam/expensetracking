# app.py
import os
import pandas as pd
import streamlit as st
import altair as alt
from dotenv import load_dotenv
from wallet_fetch import get_txlist_seiscan, get_txs_via_rpc
from web3 import Web3

# Load env variables
load_dotenv()
RPC_URL = os.getenv("RPC_URL")

st.set_page_config(
    page_title="Sei Wallet Expense Tracker",
    page_icon="💸",
    layout="wide"
)

st.title("💸 Sei Wallet Expense Tracker")
st.write("Track recent transactions, expenses, and wallet activity on the Sei blockchain.")

# Input
address = st.text_input("Enter SEI wallet address (EVM format):")
use_seiscan = st.checkbox("Use Seiscan API (if available)", value=True)

if st.button("Fetch Transactions"):
    if not address:
        st.warning("Please enter a wallet address")
    else:
        # Try Seiscan first, fallback to RPC
        if use_seiscan and os.getenv("SEISCAN_API_URL"):
            df = get_txlist_seiscan(address)
        else:
            w3 = Web3(Web3.HTTPProvider(RPC_URL))
            latest = w3.eth.block_number
            df = get_txs_via_rpc(address, latest-500, latest)  # last 500 blocks

        if df.empty:
            st.info("No transactions found in the sampled range.")
        else:
            # Ensure datetime column
            if "timeStamp" in df.columns:
                df["datetime"] = pd.to_datetime(df["timeStamp"], unit="s", errors="coerce")
            elif "timestamp" in df.columns:
                df["datetime"] = pd.to_datetime(df["timestamp"], unit="s", errors="coerce")

            # Normalize value
            df["value"] = pd.to_numeric(df["value"], errors="coerce")

            # Direction: +incoming, -outgoing
            df["direction"] = df.apply(
                lambda x: 1 if str(x.get("to","")).lower() == address.lower() else -1, axis=1
            )
            df["net"] = df["value"] * df["direction"]
            df = df.sort_values("datetime")

            # ---- Summary ----
            incoming = df[df["direction"] == 1]["value"].sum()
            outgoing = df[df["direction"] == -1]["value"].sum()

            col1, col2 = st.columns(2)
            col1.metric("Total Incoming (SEI)", f"{incoming:.4f}")
            col2.metric("Total Outgoing (SEI)", f"{outgoing:.4f}")

            # ---- Recent Transactions Table ----
            st.subheader("📋 Recent Transactions")
            st.dataframe(df[["hash","from","to","value","blockNumber","datetime"]].tail(20))

            # ---- Chart 1: Transaction Values ----
            st.subheader("📈 Transaction Values (last 50 txs)")
            st.line_chart(df.set_index("datetime")["value"].tail(50))

            # ---- Chart 2: Daily Transaction Volume ----
            st.subheader("📊 Daily Transaction Volume")
            tx_count_by_day = df.groupby(df["datetime"].dt.date).size()
            st.bar_chart(tx_count_by_day)

            # ---- Chart 3: Cumulative Balance ----
            st.subheader("💹 Cumulative Balance Trend")
            df["cumulative_balance"] = df["net"].cumsum()
            st.line_chart(df.set_index("datetime")["cumulative_balance"])

            # ---- Chart 4: Incoming vs Outgoing (Pie) ----
            st.subheader("🥧 Incoming vs Outgoing Breakdown")
            pie_df = pd.DataFrame({
                "Type": ["Incoming", "Outgoing"],
                "Amount": [incoming, abs(outgoing)]
            })
            pie_chart = alt.Chart(pie_df).mark_arc(innerRadius=50).encode(
                theta="Amount",
                color="Type",
                tooltip=["Type", "Amount"]
            )
            st.altair_chart(pie_chart, use_container_width=True)
