# Structure Doctor AI — PPT-Style Streamlit Prototype

AI-assisted crack detection and preliminary structural screening prototype.

## Files

- `app.py` — Streamlit application and PPT-style UI
- `risk_engine.py` — explainable screening/risk logic
- `requirements.txt` — deployment dependencies
- `.streamlit/config.toml` — Streamlit theme
- `README.md` — setup instructions

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Cloud

1. Upload these files to your GitHub repository.
2. Open Streamlit Cloud.
3. Select the repository and `app.py`.
4. Deploy.

## Important

This prototype does not determine actual structural strength, remaining load capacity, reinforcement condition, or certify safety. It is intended for preliminary visual screening and demonstration only.

No Roboflow or `inference-sdk` dependency is used.
