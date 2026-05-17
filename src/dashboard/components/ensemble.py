from __future__ import annotations

import json
import streamlit as st


def display_ensemble_config(ticker: str, ensemble_config_path: str) -> None:
    """Display ensemble configuration as a visual panel."""
    try:
        with open(ensemble_config_path) as f:
            config = json.load(f)
        
        if ticker.lower() not in config:
            st.warning(f"Ensemble config not found for {ticker.upper()}.")
            return
        
        cfg = config[ticker.lower()]
        
        st.markdown(f"### 🎯 Ensemble Configuration - {ticker.upper()}")
        
        # Create a 2-column layout for key info
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric(
                "Active Seeds",
                ", ".join(map(str, cfg.get("active_seeds", []))),
                help="Seeds used in the multi-seed voting ensemble"
            )
            st.metric(
                "Ensemble Method",
                cfg.get("ensemble_method", "voting").title(),
                help="How predictions are combined across seeds"
            )
        
        with col2:
            st.metric(
                "Top 3 Mean Sharpe",
                f"{cfg.get('top_3_mean_sharpe', 0):.3f}",
                help="Expected Sharpe ratio from top 3 performers"
            )
            st.metric(
                "Val-Test Gap",
                f"{cfg.get('top_3_mean_val_test_gap', 0):.2%}",
                help="Validation-test gap (overfitting indicator). <5% is healthy."
            )
        
        # Production status and notes
        status = "✅ Production Ready" if cfg.get("production_ready") else "⚠️ Development"
        st.info(
            f"**Status:** {status}\n\n"
            f"**Configuration:** {cfg.get('notes', 'No notes')}"
        )
        
        # Data preprocessing notes by ticker
        if ticker.lower() == "nvda":
            st.caption("📊 **Data:** Raw features (no stationarity transform)")
        elif ticker.lower() == "amd":
            st.caption("📊 **Data:** Stationary features (differencing applied)")
        
    except FileNotFoundError:
        st.warning(f"Ensemble config file not found: {ensemble_config_path}")
    except json.JSONDecodeError:
        st.error("Failed to parse ensemble config JSON")
    except Exception as e:
        st.error(f"Error loading ensemble config: {str(e)}")
