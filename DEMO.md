# Booth Demo — Persona Sentiment Simulator

## One-time setup (once per session)

```bash
export AWS_ACCESS_KEY_ID=...        # from Workshop Studio
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...        # expires every few hours
export AWS_REGION=us-east-1

# Verify Bedrock Nova Lite access (<5 seconds)
python -m scripts.check_bedrock
```

## Start the demo

```bash
./scripts/dev.sh
```

This launches two processes:
- **FastAPI sidecar** on `http://127.0.0.1:8001` (the LLM persona pipeline)
- **Next.js dev server** on `http://localhost:3000` (the research console UI)

Open `http://localhost:3000` in a browser.

## 30-second walkthrough

1. **Tab 1 — Map.** Click through a historical event (e.g. "Exxon announces..."). Point out the choropleth coloring by region, the demographic side-panels, and the Raw ↔ Post-Deffuant toggle.
2. **Tab 2 — Ablation.** Show the 5-way comparison table (L-M Dictionary, FinBERT, Nova Zero-Shot, Persona-Only, Persona+Graph) with Pearson IC and panel t-stats. This is the hard evaluation.
3. **Tab 3 — Simulate.** Click the **"Oil shock · XOM"** sample chip. Hit **Run simulation.**
   - Within ~15s: the map colors with the preview result (60 stratified personas, raw sentiment).
   - Within ~75s total: the map re-colors with the full result (all 300 personas + Deffuant dynamics swept at ε=0.2/0.3/0.4). The status chip flips from amber "Preview" to green "Full run". The Dynamics toggle becomes interactive.
4. **Flip the Dynamics toggle** to show how bounded-confidence opinion dynamics (Deffuant ε=0.3) reshapes the regional map — typically tightens variance and sharpens the mean in high-homophily regions.

## Q&A prep

**Why 60 personas for preview?** Stratified across 8 zip regions to preserve regional signal. LLM latency at Bedrock's 10-concurrent limit makes 300 personas ~60s; 60 fits in ~15s without sacrificing the map story.

**Why no baselines / regression on custom events?** The abnormal-returns and panel-regression metrics require 20-day market data windows post-event. A hypothetical headline has no future returns. The persona-sentiment stage is what we can defend on a custom headline; the evaluation pipeline in the Ablation tab is what we defend on historical events.

**What if Bedrock is down?** The UI surfaces a red error banner with the detail. The Map and Ablation tabs still work — they read pre-computed JSON.

**Is the ticker list hard-coded?** Yes, to the 15 Texas-domiciled tickers the pipeline was calibrated on. A free-text ticker would diverge from the prompt prefix used during the ablation and weaken the Q&A defense.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "AWS session expired" | Workshop Studio token rotated | Re-export `AWS_SESSION_TOKEN`, restart `dev.sh` |
| Port 8001 in use | Another uvicorn instance | `lsof -i :8001` then `kill <pid>`, or set `API_PORT=8002` and re-run |
| Clock drift / SigV4 signature expired | Laptop time drifted >5 min | `sudo date -s "$(curl -sI https://aws.amazon.com/ \| grep -i '^date:' \| cut -d' ' -f2-)"` |
| "parse_failure_rate > 30%" | Nova model throttled or prompt hit a guardrail | Wait 30s and retry; preview uses fewer calls and usually succeeds |
