#!/usr/bin/env python3
"""
從飛書多維表格「常用路線設定」導出 favorites.json
用於 GitHub Pages 巴士到站查詢工具

用法：
  python export_favorites.py

環境變數：
  LARK_APP_ID      飛書應用 App ID
  LARK_APP_SECRET  飛書應用 App Secret
"""

import json
import os
import sys
import urllib.request
import urllib.error

# 飛書 Base 配置
BASE_TOKEN = "An0abQoUBalSqJsG66ucDzT3ncg"
TABLE_ID = "tblWmiIDRroz446h"

# 欄位名稱
FIELD_ROUTE = "路線"
FIELD_COMPANY = "巴士公司"
FIELD_STOP_NAME = "車站名"
FIELD_STOP_ID = "Stop ID"
FIELD_DIR = "方向"
FIELD_SERVICE_TYPE = "service_type"

# 公司名稱映射
COMPANY_MAP = {
    "九巴": "KMB",
    "城巴": "CTB",
    "新巴": "CTB",
}

# 方向映射
DIR_MAP = {
    "去程(O)": "O",
    "回程(I)": "I",
}


def get_tenant_access_token(app_id, app_secret):
    """獲取 tenant_access_token"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    data = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if result.get("code") != 0:
        raise Exception(f"獲取 token 失敗: {result}")
    return result["tenant_access_token"]


def get_records(token, base_token, table_id):
    """讀取多維表格記錄"""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{base_token}/tables/{table_id}/records?page_size=100"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if result.get("code") != 0:
        raise Exception(f"讀取記錄失敗: {result}")
    return result["data"]["items"]


def extract_field_value(field_data, field_name):
    """從欄位數據中提取值"""
    if field_name not in field_data:
        return ""
    value = field_data[field_name]
    if isinstance(value, list):
        if len(value) == 0:
            return ""
        first = value[0]
        if isinstance(first, dict):
            return first.get("text", first.get("name", ""))
        return str(first)
    if isinstance(value, dict):
        return value.get("text", value.get("name", ""))
    return str(value) if value else ""


def records_to_favorites(records):
    """將飛書記錄轉換為 favorites.json 格式"""
    favorites = []
    for record in records:
        fields = record.get("fields", {})

        route = extract_field_value(fields, FIELD_ROUTE)
        company_raw = extract_field_value(fields, FIELD_COMPANY)
        stop_name = extract_field_value(fields, FIELD_STOP_NAME)
        stop_id = extract_field_value(fields, FIELD_STOP_ID)
        dir_raw = extract_field_value(fields, FIELD_DIR)
        service_type = extract_field_value(fields, FIELD_SERVICE_TYPE)

        # 跳過缺少必要欄位嘅記錄
        if not route or not stop_id:
            print(f"  跳過記錄（缺少路線或Stop ID）: {route} {stop_name}")
            continue

        # 映射公司
        company = COMPANY_MAP.get(company_raw, "")
        if not company:
            print(f"  跳過記錄（不支援嘅巴士公司: {company_raw}）: {route} {stop_name}")
            continue

        # 映射方向
        dir_code = DIR_MAP.get(dir_raw, "O")

        item = {
            "company": company,
            "route": route,
            "stopId": stop_id,
            "stopName": stop_name,
            "dir": dir_code,
        }

        # 九巴需要 service_type
        if company == "KMB" and service_type:
            item["service_type"] = service_type
        elif company == "KMB":
            item["service_type"] = "1"

        favorites.append(item)
        print(f"  已加入: {company} {route} - {stop_name} (Stop ID: {stop_id}, dir: {dir_code})")

    return favorites


def main():
    app_id = os.environ.get("LARK_APP_ID", "")
    app_secret = os.environ.get("LARK_APP_SECRET", "")

    if not app_id or not app_secret:
        print("錯誤：請設置 LARK_APP_ID 和 LARK_APP_SECRET 環境變數")
        sys.exit(1)

    print("=== 從飛書 Base 導出常用路線 ===")
    print(f"Base Token: {BASE_TOKEN}")
    print(f"Table ID: {TABLE_ID}")

    # 獲取 token
    print("\n1. 獲取 tenant_access_token...")
    token = get_tenant_access_token(app_id, app_secret)
    print("   成功")

    # 讀取記錄
    print("\n2. 讀取常用路線記錄...")
    records = get_records(token, BASE_TOKEN, TABLE_ID)
    print(f"   共 {len(records)} 條記錄")

    # 轉換格式
    print("\n3. 轉換為 favorites.json 格式...")
    favorites = records_to_favorites(records)
    print(f"\n   共 {len(favorites)} 條有效記錄")

    # 寫入文件
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "favorites.json")
    print(f"\n4. 寫入 {output_path}...")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(favorites, f, ensure_ascii=False, indent=2)
    print("   成功")

    print("\n=== 完成 ===")
    print(f"favorites.json 已生成，包含 {len(favorites)} 條常用路線")


if __name__ == "__main__":
    main()
