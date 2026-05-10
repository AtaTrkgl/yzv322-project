"""
kibana_setup.py
Owner: Venera Vangjeli (150240933)

Creates the Kibana data-view (index pattern) and four dashboards
programmatically via the Kibana Saved-Objects API.

Run once after Kibana is healthy:
    python kibana_setup.py

Environment variables:
    KIBANA_HOST   (default: http://kibana:5601)
    ES_INDEX      (default: stock_market)
"""

import os
import time
import json
import logging
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

KIBANA_HOST = os.environ.get("KIBANA_HOST", "http://kibana:5601")
ES_INDEX    = os.environ.get("ES_INDEX", "stock_market")
HEADERS     = {"kbn-xsrf": "true", "Content-Type": "application/json"}

DATA_VIEW_ID  = "stock-market-dv"
DATA_VIEW_TITLE = ES_INDEX

# ── wait helpers ───────────────────────────────────────────────────────────────

def wait_for_kibana(retries: int = 40, delay: int = 5) -> None:
    url = f"{KIBANA_HOST}/api/status"
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                logging.info("Kibana is ready.")
                return
        except Exception:
            pass
        logging.warning(f"Kibana not ready — attempt {attempt}/{retries}. Retrying in {delay}s …")
        time.sleep(delay)
    raise RuntimeError("Kibana did not become available in time.")


# ── data view ─────────────────────────────────────────────────────────────────

def create_data_view() -> None:
    url = f"{KIBANA_HOST}/api/data_views/data_view"
    payload = {
        "data_view": {
            "id":         DATA_VIEW_ID,
            "title":      DATA_VIEW_TITLE,
            "timeFieldName": "trade_date",
        }
    }
    r = requests.post(url, headers=HEADERS, json=payload)
    if r.status_code in (200, 409):
        logging.info(f"Data view '{DATA_VIEW_TITLE}' ready (status {r.status_code}).")
    else:
        logging.error(f"Failed to create data view: {r.status_code} {r.text}")


# ── saved objects ─────────────────────────────────────────────────────────────

def import_saved_objects(objects: list[dict]) -> None:
    """Bulk-import Kibana saved objects (visualisations, dashboards)."""
    ndjson = "\n".join(json.dumps(obj) for obj in objects)
    url = f"{KIBANA_HOST}/api/saved_objects/_import?overwrite=true"
    headers = {"kbn-xsrf": "true"}
    r = requests.post(url, headers=headers,
                      files={"file": ("export.ndjson", ndjson, "application/ndjson")})
    if r.ok:
        logging.info("Saved objects imported successfully.")
    else:
        logging.error(f"Import failed: {r.status_code} {r.text}")


# ── visualisation definitions ─────────────────────────────────────────────────

def build_saved_objects() -> list[dict]:
    """
    Returns a list of Kibana saved-object dicts for:
      1. Candlestick (OHLC) — Line chart (close) per ticker
      2. SMA Overlay        — Multi-line: close, sma_7, sma_30
      3. Volume Bar Chart   — Bar chart by trade_date
      4. Volatility Heatmap — daily_spread by ticker × trade_date (heat-map)
    All use the Lens visualization type for maximum flexibility.
    """
    dv = DATA_VIEW_ID

    # 1. Candlestick — close price over time per ticker
    candlestick_vis = {
        "type": "visualization",
        "id": "candlestick-close-line",
        "attributes": {
            "title": "Daily Close Price (Candlestick View)",
            "visState": json.dumps({
                "type": "line",
                "params": {
                    "grid": {"categoryLines": False},
                    "legendPosition": "right",
                    "seriesParams": [{"show": True, "type": "line", "mode": "normal",
                                      "data": {"label": "Close", "id": "1"},
                                      "valueAxis": "ValueAxis-1", "drawLinesBetweenPoints": True,
                                      "lineWidth": 2, "showCircles": True}],
                    "categoryAxes": [{"id": "CategoryAxis-1", "type": "category",
                                      "position": "bottom", "show": True,
                                      "labels": {"show": True, "truncate": 100}}],
                    "valueAxes": [{"id": "ValueAxis-1", "name": "LeftAxis-1",
                                   "type": "value", "position": "left",
                                   "show": True, "labels": {"show": True, "rotate": 0,
                                                             "truncate": 100},
                                   "title": {"text": "Close Price (USD)"}}],
                    "times": [], "addTooltip": True, "addLegend": True,
                    "radiusRatio": 9, "thresholdLine": {"show": False}
                },
                "aggs": [
                    {"id": "1", "enabled": True, "type": "avg", "schema": "metric",
                     "params": {"field": "close", "customLabel": "Close"}},
                    {"id": "2", "enabled": True, "type": "date_histogram", "schema": "segment",
                     "params": {"field": "trade_date", "useNormalizedEsInterval": True,
                                "interval": "1d", "min_doc_count": 1}},
                    {"id": "3", "enabled": True, "type": "terms", "schema": "group",
                     "params": {"field": "ticker", "size": 15, "order": "desc",
                                "orderBy": "1", "otherBucket": False}}
                ]
            }),
            "uiStateJSON": "{}",
            "description": "Daily closing price line chart grouped by ticker",
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "index": dv, "query": {"language": "kuery", "query": ""},
                    "filter": []
                })
            }
        },
        "references": [{"name": "kibanaSavedObjectMeta.searchSourceJSON.index",
                         "type": "index-pattern", "id": dv}]
    }

    # 2. SMA Overlay — close, sma_7, sma_30
    sma_vis = {
        "type": "visualization",
        "id": "sma-overlay-line",
        "attributes": {
            "title": "SMA Overlay (Close vs SMA-7 vs SMA-30)",
            "visState": json.dumps({
                "type": "line",
                "params": {
                    "grid": {"categoryLines": False},
                    "legendPosition": "right",
                    "seriesParams": [
                        {"show": True, "type": "line", "mode": "normal",
                         "data": {"label": "Close", "id": "1"},
                         "valueAxis": "ValueAxis-1", "lineWidth": 2, "showCircles": False},
                        {"show": True, "type": "line", "mode": "normal",
                         "data": {"label": "SMA-7", "id": "2"},
                         "valueAxis": "ValueAxis-1", "lineWidth": 2, "showCircles": False},
                        {"show": True, "type": "line", "mode": "normal",
                         "data": {"label": "SMA-30", "id": "3"},
                         "valueAxis": "ValueAxis-1", "lineWidth": 2, "showCircles": False},
                    ],
                    "categoryAxes": [{"id": "CategoryAxis-1", "type": "category",
                                      "position": "bottom", "show": True,
                                      "labels": {"show": True, "truncate": 100}}],
                    "valueAxes": [{"id": "ValueAxis-1", "name": "LeftAxis-1",
                                   "type": "value", "position": "left", "show": True,
                                   "labels": {"show": True}, "title": {"text": "Price (USD)"}}],
                    "addTooltip": True, "addLegend": True,
                    "thresholdLine": {"show": False}
                },
                "aggs": [
                    {"id": "1", "enabled": True, "type": "avg", "schema": "metric",
                     "params": {"field": "close", "customLabel": "Close"}},
                    {"id": "2", "enabled": True, "type": "avg", "schema": "metric",
                     "params": {"field": "sma_7", "customLabel": "SMA-7"}},
                    {"id": "3", "enabled": True, "type": "avg", "schema": "metric",
                     "params": {"field": "sma_30", "customLabel": "SMA-30"}},
                    {"id": "4", "enabled": True, "type": "date_histogram", "schema": "segment",
                     "params": {"field": "trade_date", "interval": "1d", "min_doc_count": 1}},
                    {"id": "5", "enabled": True, "type": "terms", "schema": "group",
                     "params": {"field": "ticker", "size": 10, "order": "desc", "orderBy": "1"}}
                ]
            }),
            "uiStateJSON": "{}",
            "description": "Close price with SMA-7 and SMA-30 overlays",
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "index": dv, "query": {"language": "kuery", "query": ""},
                    "filter": []
                })
            }
        },
        "references": [{"name": "kibanaSavedObjectMeta.searchSourceJSON.index",
                         "type": "index-pattern", "id": dv}]
    }

    # 3. Volume Bar Chart
    volume_vis = {
        "type": "visualization",
        "id": "volume-bar-chart",
        "attributes": {
            "title": "Daily Trading Volume",
            "visState": json.dumps({
                "type": "histogram",
                "params": {
                    "grid": {"categoryLines": False},
                    "legendPosition": "right",
                    "seriesParams": [{"show": True, "type": "histogram", "mode": "stacked",
                                      "data": {"label": "Volume", "id": "1"},
                                      "valueAxis": "ValueAxis-1", "drawLinesBetweenPoints": False}],
                    "categoryAxes": [{"id": "CategoryAxis-1", "type": "category",
                                      "position": "bottom", "show": True,
                                      "labels": {"show": True, "truncate": 100}}],
                    "valueAxes": [{"id": "ValueAxis-1", "name": "LeftAxis-1",
                                   "type": "value", "position": "left", "show": True,
                                   "labels": {"show": True}, "title": {"text": "Volume"}}],
                    "addTooltip": True, "addLegend": True,
                    "thresholdLine": {"show": False}
                },
                "aggs": [
                    {"id": "1", "enabled": True, "type": "sum", "schema": "metric",
                     "params": {"field": "volume", "customLabel": "Volume"}},
                    {"id": "2", "enabled": True, "type": "date_histogram", "schema": "segment",
                     "params": {"field": "trade_date", "interval": "1w", "min_doc_count": 1}},
                    {"id": "3", "enabled": True, "type": "terms", "schema": "group",
                     "params": {"field": "ticker", "size": 10, "order": "desc", "orderBy": "1"}}
                ]
            }),
            "uiStateJSON": "{}",
            "description": "Weekly trading volume stacked bar chart per ticker",
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "index": dv, "query": {"language": "kuery", "query": ""},
                    "filter": []
                })
            }
        },
        "references": [{"name": "kibanaSavedObjectMeta.searchSourceJSON.index",
                         "type": "index-pattern", "id": dv}]
    }

    # 4. Volatility Heatmap (daily_spread by ticker, monthly buckets)
    heatmap_vis = {
        "type": "visualization",
        "id": "volatility-heatmap",
        "attributes": {
            "title": "Volatility Heatmap (Daily Spread)",
            "visState": json.dumps({
                "type": "heatmap",
                "params": {
                    "addTooltip": True, "addLegend": True,
                    "enableHover": True, "legendPosition": "right",
                    "times": [], "colorsNumber": 8,
                    "colorSchema": "Reds",
                    "setColorRange": False,
                    "colorsRange": [],
                    "invertColors": False,
                    "percentageMode": False,
                    "valueAxes": [{"show": False, "id": "ValueAxis-1"}]
                },
                "aggs": [
                    {"id": "1", "enabled": True, "type": "avg", "schema": "metric",
                     "params": {"field": "daily_spread", "customLabel": "Avg Daily Spread"}},
                    {"id": "2", "enabled": True, "type": "terms", "schema": "segment",
                     "params": {"field": "ticker", "size": 15, "order": "desc", "orderBy": "1"}},
                    {"id": "3", "enabled": True, "type": "date_histogram", "schema": "group",
                     "params": {"field": "trade_date", "interval": "1M", "min_doc_count": 1}}
                ]
            }),
            "uiStateJSON": json.dumps({"vis": {"defaultColors": {"0 - 10": "rgb(247,251,255)"}}}),
            "description": "Heatmap showing average daily spread (High-Low) per ticker per month",
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "index": dv, "query": {"language": "kuery", "query": ""},
                    "filter": []
                })
            }
        },
        "references": [{"name": "kibanaSavedObjectMeta.searchSourceJSON.index",
                         "type": "index-pattern", "id": dv}]
    }

    # Dashboard
    dashboard = {
        "type": "dashboard",
        "id": "financial-analytics-dashboard",
        "attributes": {
            "title": "Financial Market Analytics Dashboard",
            "description": "OHLCV candlestick view, SMA overlay, volume, and volatility heatmap",
            "panelsJSON": json.dumps([
                {"panelIndex": "1", "gridData": {"x": 0, "y": 0, "w": 24, "h": 15, "i": "1"},
                 "type": "visualization", "id": "candlestick-close-line",
                 "version": "8.11.0"},
                {"panelIndex": "2", "gridData": {"x": 24, "y": 0, "w": 24, "h": 15, "i": "2"},
                 "type": "visualization", "id": "sma-overlay-line",
                 "version": "8.11.0"},
                {"panelIndex": "3", "gridData": {"x": 0, "y": 15, "w": 24, "h": 15, "i": "3"},
                 "type": "visualization", "id": "volume-bar-chart",
                 "version": "8.11.0"},
                {"panelIndex": "4", "gridData": {"x": 24, "y": 15, "w": 24, "h": 15, "i": "4"},
                 "type": "visualization", "id": "volatility-heatmap",
                 "version": "8.11.0"},
            ]),
            "optionsJSON": json.dumps({"useMargins": True, "syncColors": False,
                                       "hidePanelTitles": False}),
            "timeRestore": False,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({"query": {"language": "kuery", "query": ""},
                                                "filter": []})
            }
        },
        "references": [
            {"name": "1:panel_1", "type": "visualization", "id": "candlestick-close-line"},
            {"name": "2:panel_2", "type": "visualization", "id": "sma-overlay-line"},
            {"name": "3:panel_3", "type": "visualization", "id": "volume-bar-chart"},
            {"name": "4:panel_4", "type": "visualization", "id": "volatility-heatmap"},
        ]
    }

    return [candlestick_vis, sma_vis, volume_vis, heatmap_vis, dashboard]


def main() -> None:
    wait_for_kibana()
    create_data_view()
    objects = build_saved_objects()
    import_saved_objects(objects)
    logging.info("Kibana setup complete. Open http://localhost:5601 → Dashboards → "
                 "'Financial Market Analytics Dashboard'")


if __name__ == "__main__":
    main()
