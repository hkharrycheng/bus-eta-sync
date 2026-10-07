#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
香港巴士實時到站 → 飛書多維表格 同步腳本（統一版）

自動偵測認證方式：
- 有 LARK_APP_ID + LARK_APP_SECRET 環境變數 → 用 tenant_access_token（適合 GitHub Actions / 雲端）
- 冇 → 用 lark-cli（適合本地，已登入就用到）

用法：
  python bus_eta_sync.py
"""

import requests
import json
import os
import sys
import subprocess
from datetime import datetime, timezone, timedelta

# ============================================================
# 配置（一般唔使改）
# ============================================================
BASE_TOKEN = "An0abQoUBalSqJsG66ucDzT3ncg"
TABLE_ID = "tblBuTcGDrvBilZE"
APP_ID = os.environ.get("LARK_APP_ID", "")
APP_SECRET = os.environ.get("LARK_APP_SECRET", "")

KMB_ETA_URL = "https://data.etabus.gov.hk/v1/transport/kmb/eta/{stop_id}/{route}/1"

# ============================================================
# 認證：自動選擇模式
# ============================================================
USE_TENANT_TOKEN = bool(APP_ID and APP_SECRET)

def get_token():
    """獲取飛書 API token，自動選擇模式"""
    if USE_TENANT_TOKEN:
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET}, timeout=10)
        data = resp.json()
        if data.get("code") != 0:
            print(f"[錯誤] tenant_access_token 獲取失敗: {data}")
            sys.exit(1)
        print("  認證模式: App Secret (tenant_access_token)")
        return data["tenant_access_token"]
    else:
        print("  認證模式: lark-cli（本地用戶身份）")
        return None  # lark-cli 模式唔需要 token，直接 call lark-cli


def api_call(method, path, token=None, data=None, params=None):
    """統一 API 呼叫：有 token 用 requests，冇 token 用 lark-cli"""
    if token:
        # tenant_access_token 模式
        url = f"https://open.feishu.cn{path}"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        if method == "GET":
            resp = requests.get(url, headers=headers, params=params, timeout=15)
        else:
            resp = requests.post(url, headers=headers, json=data, timeout=15)
        result = resp.json()
        if result.get("code") != 0:
            print(f"  [API錯誤] {result}")
            return None
        return result
    else:
        # lark-cli 模式
        cmd = ["lark-cli", "api", method, path]
        if params:
            cmd.extend(["--params", json.dumps(params, ensure_ascii=False)])
        if data is not None:
            cmd.extend(["--data", json.dumps(data, ensure_ascii=False)])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            print(f"  [lark-cli錯誤] {result.stderr.strip()[:200]}")
            return None
        try:
            parsed = json.loads(result.stdout)
            if not parsed.get("ok"):
                print(f"  [API錯誤] {parsed.get('error', parsed)}")
                return None
            return parsed
        except json.JSONDecodeError:
            return None


# ============================================================
# 讀取多維表格記錄
# ============================================================
def list_records(token):
    records = []
    page_token = None
    path = f"/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{TABLE_ID}/records"

    while True:
        params = {"page_size": 100}
        if page_token:
            params["page_token"] = page_token
        resp = api_call("GET", path, token=token, params=params)
        if not resp:
            raise Exception("讀取記錄失敗")
        # lark-cli 返回 data 直接係 items；tenant 模式返回 data.items
        items = resp.get("data", {}).get("items", [])
        records.extend(items)
        has_more = resp.get("data", {}).get("has_more", False)
        if not has_more:
            break
        page_token = resp.get("data", {}).get("page_token")

    return records


# ============================================================
# 巴士 API
# ============================================================
def get_bus_eta(stop_id, route):
    url = KMB_ETA_URL.format(stop_id=stop_id, route=route)
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        return [item["eta"] for item in data.get("data", []) if item.get("eta")][:3]
    except Exception as e:
        print(f"    [警告] 查詢失敗: {e}")
        return []


# ============================================================
# 批量更新記錄
# ============================================================
def batch_update_records(token, updates):
    if not updates:
        return
    path = f"/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{TABLE_ID}/records/batch_update"
    for i in range(0, len(updates), 200):
        batch = updates[i:i+200]
        resp = api_call("POST", path, token=token, data={"records": batch})
        if resp:
            print(f"  ✓ 成功更新 {len(batch)} 條記錄")
        else:
            print(f"  ✗ 更新失敗")


# ============================================================
# 工具函數
# ============================================================
def get_text(fields, key):
    val = fields.get(key, "")
    if isinstance(val, list):
        return val[0].get("text", "") if val else ""
    return str(val) if val else ""


def iso_to_ms(iso_str):
    if not iso_str:
        return None
    try:
        return int(datetime.fromisoformat(iso_str).timestamp() * 1000)
    except Exception:
        return None


# ============================================================
# 主流程
# ============================================================
def main():
    print(f"{'='*55}")
    print(f"  巴士到站同步  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*55}")

    token = get_token()

    print(f"\n[1/3] 讀取多維表格記錄...")
    records = list_records(token)
    print(f"  ✓ 讀取到 {len(records)} 條記錄")

    print(f"\n[2/3] 查詢巴士到站時間...")
    updates = []
    now_iso = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%dT%H:%M:%S+08:00")

    for rec in records:
        fields = rec.get("fields", {})
        route = get_text(fields, "路線")
        stop_id = get_text(fields, "Stop ID")
        stop_name = get_text(fields, "車站名")

        if not route or not stop_id:
            print(f"  [跳過] 缺少路線或Stop ID")
            continue

        etas = get_bus_eta(stop_id, route)
        eta_str = " | ".join([f"第{i+1}班 {e[11:16]}" for i, e in enumerate(etas)]) if etas else "暫無數據"
        print(f"  {route:6} {stop_name[:20]:20} → {eta_str}")

        update_fields = {"更新時間": iso_to_ms(now_iso)}
        for i in range(3):
            update_fields[f"到站時間{i+1}"] = iso_to_ms(etas[i]) if i < len(etas) else None

        updates.append({"record_id": rec["record_id"], "fields": update_fields})

    print(f"\n[3/3] 寫入多維表格...")
    batch_update_records(token, updates)

    print(f"\n{'='*55}")
    print(f"  完成！共處理 {len(updates)} 條路線")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
