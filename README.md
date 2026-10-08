# 香港巴士到站查詢工具 (Bus ETA Sync)

一個實時查詢香港巴士（九巴、城巴/新巴、小巴）到站時間嘅網頁工具，配合飛書多維表格管理常用路線。

---

## 📋 目錄

1. [ADMIN 使用說明](#admin-使用說明)
2. [Logic Flow](#logic-flow)
3. [Business Flow](#business-flow)
4. [JSON Structure](#json-structure)
5. [API Reference](#api-reference)
6. [文件結構](#文件結構)
7. [常見問題](#常見問題)

---

## ADMIN 使用說明

### 前置條件

- GitHub Account（用於存放程式同 GitHub Pages 託管）
- 飛書/豆包 Account（用於多維表格管理常用路線）
- 飛書開放平台應用（App ID + App Secret）
- GitHub Personal Access Token（repo 權限）

### 初始設定

#### 1. 飛書應用設定

1. 前往 [飛書開放平台](https://open.feishu.cn/) 創建應用
2. 開通以下權限（應用身份）：
   - `bitable:app`
   - `bitable:app:readonly`
   - `base:record:retrieve`
3. 發布應用
4. 將應用加為多維表格協作者

#### 2. GitHub Secrets 設定

在 Repo → Settings → Secrets and variables → Actions 新增：

| Secret Name | 說明 |
|-------------|------|
| `LARK_APP_ID` | 飛書應用 App ID |
| `LARK_APP_SECRET` | 飛書應用 App Secret |

#### 3. 飛書常數設定表

在「常數設定」表中填入：

| Item | Parameter |
|------|-----------|
| Github Personal Access Token | `ghp_xxxxxxxxxxxx` |
| J01 | 同步常用路線到GitHub |
| J02 | HTML/Workflow更新與備份 |

### 日常操作

#### 更新常用路線

1. 在飛書「常用路線」表新增/修改路線
2. 執行 J01（呼叫助手執行）
3. 助手會自動：
   - 讀取常用路線表
   - 查詢 Stop ID
   - 生成 `favorites.json`
   - 上傳到 GitHub

#### 更新 HTML/Workflow

1. 向助手提出更新要求
2. 助手建立本地 Prototype 讓你測試
3. 你答「OK」後，助手會：
   - 更新所有 CODE
   - 上傳到 GitHub
   - 更新 README.md
   - 備份整個 Repository 到雲端

#### 手動觸發 GitHub Actions

1. 前往 Repo → Actions
2. 選擇 `Export Favorites` workflow
3. 點擊 `Run workflow`

---

## Logic Flow

### 整體系統架構

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   飛書多維表格   │────▶│  Update-Favorites │────▶│    GitHub Repo  │
│  (常用路線設定)  │     │   .ps1 (J01)    │     │  favorites.json │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                          │
                                                          ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  用戶瀏覽器     │◀────│  GitHub Pages   │◀────│  bus-eta.html   │
│  (查詢到站時間)  │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                          │
                                                          ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  九巴 API       │◀────│                 │────▶│  城巴/新巴 API   │
│  data.etabus    │     │   bus-eta.html  │     │  rt.data.gov.hk  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                          │
                                                          ▼
                                               ┌─────────────────┐
                                               │  小巴 API       │
                                               │  data.etagmb    │
                                               └─────────────────┘
```

### HTML 載入流程

```
用戶打開 bus-eta.html
        │
        ▼
  initFavorites()
        │
        ├─ fetch('favorites.json')
        │       │
        │       ├─ 成功 → FAVORITES = 數據
        │       └─ 失敗 → FAVORITES = []
        │
        ▼
  initTagFilter()
        │
        ├─ 提取所有 usage Tag
        └─ 預設全部顯示
        │
        ▼
  showFavorites() ← 預設顯示常用路線
        │
        ├─ 顯示常用路線視圖
        ├─ loadFavoritesETA()
        │       │
        │       ├─ 遍歷 FAVORITES
        │       ├─ 按 Tag 篩選
        │       ├─ 呼叫對應 API（九巴/城巴/小巴）
        │       └─ 渲染到站時間
        │
        └─ 設定 30 秒自動刷新
```

### 查詢路線流程

```
用戶輸入路線號 → 選擇巴士公司 → 點擊查詢
        │
        ▼
  searchRoute()
        │
        ├─ 九巴：GET /route/ → 過濾路線
        ├─ 城巴：GET /route/ctb → 自動建立去程/回程
        └─ 小巴：GET /route/{region} → 搜索路線
        │
        ▼
  顯示方向標籤（如多於一個方向）
        │
        ▼
  loadStops()
        │
        ├─ 九巴：GET /route-stop/{route}/{bound}/{service_type}
        ├─ 城巴：GET /route-stop/ctb/{route}/{bound}
        └─ 小巴：GET /route-stop/{route_id}/{route_seq}
        │
        ▼
  渲染車站列表
        │
        ▼
  用戶點擊車站
        │
        ▼
  selectStop(index)
        │
        ├─ 移除舊 ETA Panel
        ├─ 插入新 ETA Panel 到車站之間
        ├─ loadETA(index)
        │       │
        │       ├─ 九巴：GET /eta/{stop_id}/{route}/{service_type}
        │       ├─ 城巴：GET /batch/stop-eta/CTB/{stop_id}
        │       └─ 小巴：GET /eta/stop/{stop_id}
        │       │
        │       ├─ 按方向過濾
        │       └─ 渲染到站時間 + Google Maps
        │
        └─ 設定 30 秒自動刷新
```

---

## Business Flow

### J01：同步常用路線到 GitHub

```
觸發：用戶呼叫「執行 J01」
        │
        ▼
  1. 讀取飛書常數設定表
     └─ 獲取 GitHub Personal Access Token
        │
        ▼
  2. 讀取飛書常用路線表
     └─ 獲取所有路線記錄（路線、車站名、巴士公司、用法、Stop ID、方向）
        │
        ▼
  3. 檢查數據完整性
     ├─ Stop ID 是否為空？
     │   └─ 是 → 查詢 API 獲取 Stop ID → 更新飛書表
     └─ 方向是否為空？
         └─ 是 → 查詢 API 獲取方向 → 更新飛書表
        │
        ▼
  4. 生成 favorites.json
     └─ 按照飛書表次序排列
        │
        ▼
  5. 上傳到 GitHub
     └─ PUT /repos/{owner}/{repo}/contents/favorites.json
        │
        ▼
  6. 驗證上傳成功
     └─ 回傳 commit SHA
        │
        ▼
  完成 ✅
```

### J02：HTML/Workflow 更新與備份

```
觸發：用戶提出更新要求 或 直接呼叫備份
        │
        ▼
  情況 A：有更新要求
        │
        ├─ 1. 建立本地 Prototype
        │   └─ 修改 HTML/Workflow → 本地測試
        │
        ├─ 2. 用戶測試並確認
        │   ├─ 用戶答「OK」→ 繼續
        │   └─ 用戶要求修改 → 回到步驟 1
        │
        ├─ 3. 更新 GitHub
        │   ├─ 上傳修改後嘅 HTML
        │   ├─ 上傳修改後嘅 Workflow
        │   └─ 更新 README.md
        │
        └─ 4. 備份 Repository → 跳到情況 B
        │
  情況 B：直接備份
        │
        ├─ 1. 下載 GitHub Repo ZIP
        │
        ├─ 2. 解壓 ZIP
        │
        ├─ 3. 上傳到飛書雲端
        │   ├─ 按照 GitHub 文件夾層級創建文件夾
        │   ├─ 逐個上傳文件
        │   └─ 包含：.html, .py, .yml, .json, README.md
        │
        └─ 4. 驗證備份完成
        │
        ▼
  完成 ✅
```

---

## JSON Structure

### favorites.json

常用路線數據，由 J01 自動生成，HTML 讀取此文件顯示常用路線。

```json
[
  {
    "route": "S56",
    "stopName": "映灣園四期, 文東路",
    "company": "CTB",
    "usage": "上班",
    "stopId": "BA04195A105130",
    "dir": "1",
    "service_type": "1"
  },
  {
    "route": "S64P",
    "stopName": "映灣園第二期 (TC160)",
    "company": "KMB",
    "usage": "上班",
    "stopId": "D7AAC19538A45549",
    "dir": "O",
    "service_type": "1"
  },
  {
    "route": "901",
    "stopName": "文東路, 映灣園三期",
    "company": "GMB",
    "usage": "上班 + 下班",
    "stopId": "20007565",
    "dir": "1",
    "service_type": "1"
  }
]
```

#### 字段說明

| 字段 | 類型 | 說明 | 範例 |
|------|------|------|------|
| `route` | string | 路線號 | `"S56"`, `"901"` |
| `stopName` | string | 車站名稱（中文） | `"映灣園四期, 文東路"` |
| `company` | string | 巴士公司 | `"KMB"` / `"CTB"` / `"GMB"` |
| `usage` | string | 用法標籤（用於篩選） | `"上班"`, `"下班"`, `"大陸用"` |
| `stopId` | string | 車站 ID | `"BA04195A105130"` |
| `dir` | string | 方向 | 九巴：`"O"`/`"I"`，城巴：`"1"`/`"2"`，小巴：`"1"` |
| `service_type` | string | 服務類型 | `"1"`（通常為 1） |

#### company 枚舉值

| 值 | 公司 | 顏色標籤 |
|----|------|----------|
| `KMB` | 九巴 | 紅色 |
| `CTB` | 城巴/新巴 | 橙色 |
| `GMB` | 小巴 | 綠色 |

---

## API Reference

### 九巴 API (KMB)

Base URL: `https://data.etabus.gov.hk/v1/transport/kmb`

| 端點 | 方法 | 說明 |
|------|------|------|
| `/route/` | GET | 獲取所有路線 |
| `/route/{route}` | GET | 獲取指定路線詳情 |
| `/route-stop/{route}/{bound}/{service_type}` | GET | 獲取路線車站列表 |
| `/stop/{stop_id}` | GET | 獲取車站詳情 |
| `/eta/{stop_id}/{route}/{service_type}` | GET | 獲取到站時間 |

#### 九巴 ETA 回應範例

```json
{
  "data": [
    {
      "eta": "2026-10-08T15:30:00+08:00",
      "dir": "O",
      "dest_tc": "機場",
      "route": "S56",
      "seq": 1,
      "service_type": 1
    }
  ]
}
```

### 城巴/新巴 API (CTB/NWFB)

Base URL: `https://rt.data.gov.hk/v1/transport/citybus-nwfb`

| 端點 | 方法 | 說明 |
|------|------|------|
| `/route/ctb` | GET | 獲取所有城巴路線 |
| `/route-stop/ctb/{route}/{bound}` | GET | 獲取路線車站列表 |
| `/stop/{stop_id}` | GET | 獲取車站詳情 |

Batch ETA API: `https://rt.data.gov.hk/v1/transport/batch`

| 端點 | 方法 | 說明 |
|------|------|------|
| `/stop-eta/CTB/{stop_id}` | GET | 獲取車站所有路線到站時間 |

#### 城巴 ETA 回應範例

```json
{
  "data": [
    {
      "eta": "2026-10-08T15:30:00+08:00",
      "dir": "1",
      "dest": "機場",
      "route": "S56"
    }
  ]
}
```

### 小巴 API (GMB)

Base URL: `https://data.etagmb.gov.hk`

| 端點 | 方法 | 說明 |
|------|------|------|
| `/route/{region}` | GET | 獲取區域內所有路線（NT/KLN/HKI） |
| `/route/{region}/{route_code}` | GET | 獲取路線詳情 |
| `/route-stop/{route_id}/{route_seq}` | GET | 獲取路線車站列表 |
| `/eta/stop/{stop_id}` | GET | 獲取車站到站時間 |

#### 小巴 ETA 回應範例

```json
{
  "data": {
    "data": [
      {
        "route_id": 2000987,
        "eta": [
          {
            "timestamp": "2026-10-08T15:30:00+08:00",
            "diff": 5,
            "remarks": "正常"
          }
        ]
      }
    ]
  }
}
```

**注意**：小巴 API 結構不同，`data.data` 是數組，每個元素包含 `eta` 數組。

---

## 文件結構

### GitHub Repository

```
bus-eta-sync/
├── .github/
│   └── workflows/
│       └── export-favorites.yml    # 導出常用路線 workflow
├── bus-eta.html                    # 巴士到站查詢工具（主頁面）
├── export_favorites.py             # 導出常用路線到 JSON（舊版）
├── favorites.json                  # 常用路線數據
├── kmb-stop-id.html                # 九巴 Stop ID 查詢工具
└── README.md                       # 本文件
```

### 飛書多維表格

```
Base: 巴士實時到站 (An0abQoUBalSqJsG66ucDzT3ncg)
├── 常用路線 (tblWmiIDRroz446h)
│   ├── 路線 (text)
│   ├── 車站名 (text)
│   ├── 巴士公司 (select: 城巴/九巴/小巴)
│   ├── 用法 (select: 上班/下班/上班 + 下班/大陸用)
│   ├── Stop ID (text)
│   ├── 方向 (text)
│   └── service_type (text)
└── 常數設定 (tbldGpfjk9ylijwU)
    ├── Item (text)
    ├── 工作名 (text)
    ├── 工作詳細 (text)
    └── Parameter (text)
```

### 飛書雲端備份

```
Github/ (LEuBfUDaRl9dxSdEhVwcqxv3nFf)
├── .github/
│   └── workflows/
│       └── export-favorites.yml
├── bus-eta.html
├── export_favorites.py
├── favorites.json
├── kmb-stop-id.html
├── README.md
└── bus-eta-sync-backup-YYYYMMDD-HHMMSS.zip
```

---

## 常見問題

### Q: HTML 打開後顯示「暫無到站數據」點算？

A: 可能原因：
1. 該方向而家冇巴士即將到達
2. Stop ID 錯誤 → 檢查飛書表中嘅 Stop ID
3. 方向設定錯誤 → 九巴用 `O`/`I`，城巴用 `1`/`2`

### Q: 點解小巴顯示「Invalid Date」？

A: 小巴 API 結構不同，`data.data` 是數組，每個元素包含 `eta` 數組。確保 HTML 版本支援小巴 API。

### Q: 點樣新增常用路線？

A: 
1. 在飛書「常用路線」表新增記錄
2. 填入路線、車站名、巴士公司、用法
3. 呼叫助手執行 J01，自動查詢 Stop ID 並同步到 GitHub

### Q: GitHub Actions 同步失敗點算？

A: 檢查：
1. GitHub Secrets (`LARK_APP_ID`, `LARK_APP_SECRET`) 是否正確
2. 飛書應用是否已發布
3. 飛書應用是否已加為多維表格協作者

### Q: 可以查詢邊啲巴士公司？

A: 目前支援：
- ✅ 九巴 (KMB)
- ✅ 城巴/新巴 (CTB/NWFB)
- ✅ 小巴 (GMB)

### Q: 到站時間幾耐更新一次？

A: HTML 頁面每 30 秒自動刷新到站時間。常用路線數據 (`favorites.json`) 需要手動執行 J01 先會更新。

---

## 更新記錄

| 日期 | 版本 | 說明 |
|------|------|------|
| 2026-10-08 | v2.0 | 新增小巴支援、用法Tag篩選、預設顯示常用路線、移除Obsolete功能 |
| 2026-10-07 | v1.0 | 初始版本，九巴+城巴到站查詢 |

---

## License

MIT License
