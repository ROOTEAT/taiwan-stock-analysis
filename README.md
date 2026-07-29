# 台股策略研究室

依據《台股智慧分析、策略回測與模擬投資系統》規劃落地的互動式研究工具。

## 已完成

- 上市與上櫃普通股代碼／名稱搜尋
- TWSE、TPEx 官方盤後行情、估值與月營收
- Yahoo 最新報價與歷史行情補充，失敗時降級為官方盤後資料
- SQLite 快取與每項資料來源、行情時間、擷取時間標示
- 短線、波段及中長期適合度分析
- 保守、穩健及積極風險屬性
- 技術、基本、籌碼及風險四構面評分
- 偏多／觀望／偏空訊號、信心度、理由、觀察區及失效價
- 上市上櫃成交量、漲幅與跌幅熱門清單
- 近期關注候選掃描與綜合分數排序
- ATR、均線及近期壓力推算的布局區、失效價與兩段停利參考
- 本機投資組合清單（股數、成本、備註）
- 依現價、成本與策略狀態產生補入、續抱、減碼或退出參考
- 持有與關注雙頁籤，持股股數、平均成本與備註可直接修改
- 組合股息行事曆：每股股利、預估稅前股息、除息日、最後持有參考日與發放日狀態
- 台股與美股正常交易時段開收盤倒數
- 選配 GDELT 國際新聞情緒，僅以 5% 低權重影響綜合分數
- Glassmorphism 介面與按鈕式左側導覽
- CSV 日線資料匯入與資料驗證備援
- K 線、MA、RSI、MACD、KD、ATR、布林通道
- 單一股票、單一持倉、只做多策略回測
- 收盤產生訊號、次日開盤成交，避免基本前視偏誤
- 停利、停損、均線出場、持有期限
- 手續費、交易稅、最低手續費與滑價
- 資產曲線、交易明細、報酬、回撤、Sharpe、勝率
- Wilson 勝率信賴區間、單尾二項檢定與 Bootstrap 模擬

## 執行

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

瀏覽器開啟 Streamlit 顯示的本機網址，輸入四位數股票代碼或公司名稱即可分析。

資料會快取在 `data/market_cache.sqlite3`。按下「重新抓取最新資料」可略過快取。

## CSV 格式

```csv
date,open,high,low,close,volume
2025-01-02,100,102,99,101,12000000
```

## 測試

```powershell
python -m pytest -q
```

## 免費公開部署（Streamlit Community Cloud）

1. 將本專案推送到 GitHub 儲存庫。
2. 前往 [share.streamlit.io](https://share.streamlit.io/) 並使用 GitHub 登入。
3. 選擇儲存庫與分支，入口檔案填入 `app.py`。
4. 在 Advanced settings：
   - Python version 選擇 `3.12`。
   - Secrets 填入：

```toml
PUBLIC_DEMO_MODE = true
```

5. 按下 Deploy，完成後會取得 `https://...streamlit.app` 公開網址。

公開版會自動使用工作階段隔離的「我的組合」，避免不同訪客共用持股資料。免費主機休眠、瀏覽器重新整理或工作階段結束後，公開版組合資料可能重置；本機執行仍使用 SQLite 保存。

請勿把 `.streamlit/secrets.toml`、API 金鑰、個人持股資料或 SQLite 資料庫提交到 GitHub。

> 本專案僅供研究與模擬，不構成投資建議。Yahoo 僅作最新行情與官方歷史不足時的補充來源。
