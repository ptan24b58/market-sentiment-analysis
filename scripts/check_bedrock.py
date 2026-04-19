"""Diagnostic: where exactly is Bedrock failing?

Usage:
    source .env && python -m scripts.check_bedrock

Runs 4 checks in order and prints the FIRST failure:
  1. Are AWS creds loaded in the current process env?
  2. Does `sts get-caller-identity` succeed? (creds reach AWS at all?)
  3. Does `bedrock list-foundation-models` return Nova Lite? (model access?)
  4. Does a real `invoke_model` on Nova Lite succeed with a trivial prompt?

Prints the exact exception class + message for each failure so you can fix it.
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
    try:
        brc = boto3.client("bedrock", region_name=region)
        models = brc.list_foundation_models()
        ids = [m["modelId"] for m in models.get("modelSummaries", [])]
        nova = [m for m in ids if "nova-lite" in m.lower()]
        if nova:
            print(f"[3/4] OK: {len(ids)} models listed; Nova Lite ids: {nova}")
        else:
            print(f"[3/4] FAIL: Nova Lite not listed. First 5 models: {ids[:5]}")
            print(f"      → Bedrock model access not granted for Nova Lite in region {region}")
            print(f"      → AWS Console → Bedrock → Model access → Request Amazon Nova Lite")
            return 3
    except Exception as exc:  # noqa: BLE001
        print(f"[3/4] FAIL: list_foundation_models: {type(exc).__name__}: {exc}")
        print(f"      → role lacks 'bedrock:ListFoundationModels' permission, "
              "or Bedrock is not in region {region}")
        return 3

    # ---------- 4. real invoke ----------
    try:
        brt = boto3.client("bedrock-runtime", region_name=region)
        body = json.dumps({
            "messages": [{"role": "user", "content": [{"text": "Reply with 0.5"}]}],
        })
        resp = brt.invoke_model(modelId=config.BEDROCK_MODEL_ID, body=body)
        payload = json.loads(resp["body"].read())
        text = (payload.get("output", {})
                .get("message", {})
                .get("content", [{}])[0]
                .get("text", ""))
        print(f"[4/4] OK: invoke_model returned: {text!r}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[4/4] FAIL: invoke_model: {type(exc).__name__}: {exc}")
        print(f"      → most likely cause shown above. Common:")
        print(f"         - AccessDeniedException → role lacks bedrock:InvokeModel")
        print(f"         - ValidationException → wrong modelId or region")
        print(f"         - ThrottlingException → rate-limited, retry")
        print(f"         - ExpiredTokenException → session expired, re-source .env")
        return 4


if __name__ == "__main__":
    sys.exit(main())
