"""Diagnostic: where exactly is Bedrock failing?

Usage:
    source .env && python -m scripts.check_bedrock

Runs 4 checks in order and prints the FIRST failure:
  1. Are AWS creds loaded in the current process env?
  2. Does `sts get-caller-identity` succeed? (creds reach AWS at all?)
  3. Does `bedrock list-foundation-models` return the configured model?
  4. Does a real invocation through the app's `invoke_nova_lite` succeed?

Step 4 uses the same function the live pipeline uses (so payload schema
and model ID stay in sync), rather than hand-rolling a request.
"""

from __future__ import annotations

import json
import os
import sys


def main() -> int:
    print("=== AWS Bedrock diagnostic ===\n")

    # ---------- 1. env vars ----------
    required = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]
    optional = ["AWS_SESSION_TOKEN", "AWS_DEFAULT_REGION"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"[1/4] FAIL: missing env vars: {missing}")
        print("      → run: source .env (or `set -a && source .env && set +a`)")
        return 1
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    key_id = os.environ["AWS_ACCESS_KEY_ID"]
    print(f"[1/4] OK: AWS_ACCESS_KEY_ID={key_id[:4]}...{key_id[-4:]} region={region}")
    has_session = bool(os.environ.get("AWS_SESSION_TOKEN"))
    print(f"      AWS_SESSION_TOKEN present: {has_session}"
          f"  (required if key_id starts with ASIA)")
    if key_id.startswith("ASIA") and not has_session:
        print("      → ASIA keys are temporary; you MUST set AWS_SESSION_TOKEN too")
        return 1
    for k in optional:
        val = os.environ.get(k)
        if val:
            print(f"      {k} is set")

    # ---------- 2. STS ----------
    try:
        import boto3
    except ImportError:
        print("[2/4] FAIL: boto3 not installed")
        return 2
    try:
        sts = boto3.client("sts", region_name=region)
        ident = sts.get_caller_identity()
        print(f"[2/4] OK: caller={ident.get('Arn')} account={ident.get('Account')}")
    except Exception as exc:  # noqa: BLE001
        print(f"[2/4] FAIL: STS error: {type(exc).__name__}: {exc}")
        print("      → credentials are wrong, expired, or blocked")
        return 2

    # ---------- 3. list models ----------
    from src import config
    target_id = config.BEDROCK_MODEL_ID
    # Cross-region inference profile ids start with "us."/"eu." etc. — strip the
    # prefix when matching against listed foundation-model ids, which always
    # start with the provider name (e.g. "anthropic.claude-...").
    target_suffix = target_id.split(".", 1)[1] if target_id.startswith(("us.", "eu.", "apac.")) else target_id
    try:
        brc = boto3.client("bedrock", region_name=region)
        models = brc.list_foundation_models()
        ids = [m["modelId"] for m in models.get("modelSummaries", [])]
        match = [m for m in ids if target_suffix in m or target_id in m]
        if match:
            print(f"[3/4] OK: {len(ids)} models listed; configured model matches: {match[:3]}")
        else:
            # Cross-region profiles are acceptable even if the base model isn't
            # in list_foundation_models — they're managed separately. Print a
            # warning but don't fail.
            if target_id.startswith(("us.", "eu.", "apac.")):
                print(f"[3/4] WARN: {len(ids)} models listed; {target_id} is a cross-region "
                      f"inference profile — not in foundation-models list (expected).")
            else:
                print(f"[3/4] FAIL: {target_id} not listed. First 5 models: {ids[:5]}")
                print(f"      → Bedrock model access not granted for {target_id} in region {region}")
                print(f"      → AWS Console → Bedrock → Model access → Request the model")
                return 3
    except Exception as exc:  # noqa: BLE001
        print(f"[3/4] FAIL: list_foundation_models: {type(exc).__name__}: {exc}")
        print(f"      → role lacks 'bedrock:ListFoundationModels' permission, "
              f"or Bedrock is not in region {region}")
        return 3

    # ---------- 4. real invoke via the app's client (same code path as live) ----------
    try:
        import asyncio
        from src.llm.bedrock_client import invoke_nova_lite, reset_client
        reset_client()
        result = asyncio.run(
            invoke_nova_lite(
                "You are a test persona.",
                "Respond with the single number 0.5 and nothing else.",
            )
        )
        text = result.get("response_text", "").strip()
        cache_hit = result.get("cache_hit", False)
        latency = result.get("latency_ms", 0)
        print(f"[4/4] OK: invoke via {target_id}")
        print(f"      response_text={text!r}  latency={latency:.0f}ms  cache_hit={cache_hit}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[4/4] FAIL: invoke_model: {type(exc).__name__}: {exc}")
        print(f"      → most likely cause shown above. Common:")
        print(f"         - AccessDeniedException → role lacks bedrock:InvokeModel,")
        print(f"           or model access not enabled in Bedrock console for {target_id}")
        print(f"         - ValidationException → wrong modelId string, or payload")
        print(f"           schema mismatch (Nova vs Anthropic)")
        print(f"         - ThrottlingException → rate-limited, retry")
        print(f"         - ExpiredTokenException → session expired, re-source .env")
        print(f"         - InvalidSignatureException → clock drift; `sudo date -s ...`")
        return 4


if __name__ == "__main__":
    sys.exit(main())
