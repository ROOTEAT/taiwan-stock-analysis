from __future__ import annotations

from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Protocol
import warnings

import pandas as pd
import requests
import urllib3

from .cache import SQLiteCache
from .indicators import normalize_prices
from .models import DataMeta, DividendEvent, Quote, StockInfo

TAIPEI = timezone(timedelta(hours=8))
TWSE = "https://openapi.twse.com.tw/v1"
TPEX = "https://www.tpex.org.tw/openapi/v1"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart"
TWSE_MIS = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"

INDUSTRY_NAMES = {
    "01": "水泥工業", "02": "食品工業", "03": "塑膠工業", "04": "紡織纖維",
    "05": "電機機械", "06": "電器電纜", "08": "玻璃陶瓷", "09": "造紙工業",
    "10": "鋼鐵工業", "11": "橡膠工業", "12": "汽車工業", "14": "建材營造",
    "15": "航運業", "16": "觀光餐旅", "17": "金融保險", "18": "貿易百貨",
    "19": "綜合企業", "20": "其他業", "21": "化學工業", "22": "生技醫療",
    "23": "油電燃氣", "24": "半導體業", "25": "電腦及週邊", "26": "光電業",
    "27": "通信網路", "28": "電子零組件", "29": "電子通路", "30": "資訊服務",
    "31": "其他電子", "32": "文化創意", "33": "農業科技", "34": "電子商務",
    "35": "綠能環保", "36": "數位雲端", "37": "運動休閒", "38": "居家生活",
    "39": "數位中介",
}
AVIATION_CODES = {"2610", "2618", "2630", "2646"}


class MarketDataProvider(Protocol):
    def search_stocks(self, query: str = "") -> list[StockInfo]: ...
    def get_daily_prices(self, stock: StockInfo, refresh: bool = False) -> tuple[pd.DataFrame, DataMeta]: ...
    def get_latest_quote(self, stock: StockInfo, refresh: bool = False) -> Quote: ...
    def get_valuation(self, stock: StockInfo, refresh: bool = False) -> tuple[dict, DataMeta]: ...
    def get_monthly_revenue(self, stock: StockInfo, refresh: bool = False) -> tuple[dict, DataMeta]: ...
    def get_institutional_trading(self, stock: StockInfo, refresh: bool = False) -> tuple[dict, DataMeta]: ...
    def get_dividend_events(self, stock: StockInfo, refresh: bool = False) -> list[DividendEvent]: ...


def _number(value, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "").replace("+", "").strip())
    except (TypeError, ValueError):
        return default


def _roc_date(value: str) -> datetime | None:
    text = str(value).strip().replace("/", "")
    try:
        if len(text) == 7:
            return datetime(int(text[:3]) + 1911, int(text[3:5]), int(text[5:]), tzinfo=TAIPEI)
        if len(text) == 8:
            return datetime.strptime(text, "%Y%m%d").replace(tzinfo=TAIPEI)
    except ValueError:
        return None
    return None


class HybridTaiwanProvider:
    def __init__(self, cache: SQLiteCache | None = None, timeout: int = 15) -> None:
        self.cache = cache or SQLiteCache()
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0 TaiwanStockResearch/1.0"})

    def _json(self, url: str, *, tpex: bool = False):
        verify = not tpex
        if tpex:
            warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)
        response = self.session.get(url, timeout=self.timeout, verify=verify)
        response.raise_for_status()
        return response.json()

    def _cached_json(self, key: str, url: str, ttl: int, refresh: bool = False, tpex: bool = False):
        if not refresh:
            hit = self.cache.get(key)
            if hit:
                return hit[0], hit[1], False
        try:
            payload = self._json(url, tpex=tpex)
            fetched = self.cache.set(key, payload, ttl)
            return payload, fetched, False
        except Exception:
            stale = self.cache.get(key, allow_stale=True)
            if stale:
                return stale[0], stale[1], True
            raise

    def _daily_rows(self, market: str, refresh: bool = False):
        if market == "TWSE":
            return self._cached_json("daily:twse", f"{TWSE}/exchangeReport/STOCK_DAY_ALL", 1800, refresh)
        return self._cached_json("daily:tpex", f"{TPEX}/tpex_mainboard_quotes", 1800, refresh, True)

    def _industry_map(self) -> dict[str, str]:
        industries: dict[str, str] = {}
        sources = (
            ("industry:twse", f"{TWSE}/opendata/t187ap03_L", False, "公司代號", "產業別"),
            ("industry:tpex", f"{TPEX}/mopsfin_t187ap03_O", True, "SecuritiesCompanyCode", "SecuritiesIndustryCode"),
        )
        for key, url, tpex, code_key, industry_key in sources:
            try:
                rows, _, _ = self._cached_json(key, url, 86400, tpex=tpex)
            except Exception:
                continue
            for row in rows:
                code = str(row.get(code_key, "")).strip()
                industry_code = str(row.get(industry_key, "")).strip().zfill(2)
                industry = INDUSTRY_NAMES.get(industry_code, "其他業")
                if code in AVIATION_CODES:
                    industry = "航空業"
                industries[code] = industry
        return industries

    def search_stocks(self, query: str = "") -> list[StockInfo]:
        stocks: dict[str, StockInfo] = {}
        industries = self._industry_map()
        for market in ("TWSE", "TPEx"):
            try:
                rows, _, _ = self._daily_rows(market)
            except Exception:
                continue
            for row in rows:
                code = str(row.get("Code") or row.get("SecuritiesCompanyCode") or "").strip()
                name = str(row.get("Name") or row.get("CompanyName") or "").strip()
                is_stock = len(code) == 4 and code.isdigit() and not code.startswith("0")
                is_etf = 4 <= len(code) <= 6 and code.isdigit() and code.startswith("00")
                if is_stock or is_etf:
                    stocks[code] = StockInfo(
                        code, name, market,
                        industry="ETF" if is_etf else industries.get(code, "其他業"),
                        asset_type="ETF" if is_etf else "STOCK",
                    )
        text = query.strip().lower()
        result = [
            s for s in stocks.values()
            if not text or text in s.code.lower() or text in s.name.lower() or text in s.industry.lower()
        ]
        return sorted(result, key=lambda s: s.code)

    def get_stock(self, code: str) -> StockInfo:
        matches = [s for s in self.search_stocks(code) if s.code == code]
        if not matches:
            raise ValueError("找不到此上市／上櫃普通股代碼")
        return matches[0]

    def get_market_index(self, refresh: bool = False) -> tuple[pd.DataFrame, Quote]:
        now = datetime.now(TAIPEI)
        market_open = now.weekday() < 5 and 9 <= now.hour < 14
        ttl = 30 if market_open else 300
        key = "market-index:yahoo:^TWII"
        if not refresh:
            cached = self.cache.get(key)
            if cached:
                payload, fetched, stale = cached
                frame = normalize_prices(pd.DataFrame(payload["prices"]))
                q = payload["quote"]
                return frame, Quote(
                    "^TWII", q["price"], q["change"], q["change_pct"], q["volume"],
                    DataMeta("Yahoo Finance 台灣加權指數", datetime.fromisoformat(q["market_time"]), fetched, stale),
                )
        data = self._json(f"{YAHOO}/%5ETWII?interval=1d&range=1y")["chart"]["result"][0]
        raw = data["indicators"]["quote"][0]
        frame = normalize_prices(pd.DataFrame({
            "date": pd.to_datetime(data["timestamp"], unit="s", utc=True).tz_convert(TAIPEI).tz_localize(None),
            "open": raw["open"], "high": raw["high"], "low": raw["low"],
            "close": raw["close"], "volume": raw["volume"],
        }).dropna())
        meta = data["meta"]
        # For long chart ranges Yahoo's chartPreviousClose may refer to the
        # beginning of the range, not the immediately preceding session.
        price = float(frame.iloc[-1].close)
        previous = float(frame.iloc[-2].close) if len(frame) >= 2 else price
        market_time = datetime.fromtimestamp(meta["regularMarketTime"], TAIPEI)
        quote_payload = {
            "price": price, "change": price - previous,
            "change_pct": (price / previous - 1) * 100 if previous else 0,
            "volume": _number(meta.get("regularMarketVolume")),
            "market_time": market_time.isoformat(),
        }
        payload = {
            "prices": frame.assign(date=frame.date.dt.strftime("%Y-%m-%d")).to_dict("records"),
            "quote": quote_payload,
        }
        fetched = self.cache.set(key, payload, ttl)
        return frame, Quote(
            "^TWII", quote_payload["price"], quote_payload["change"], quote_payload["change_pct"],
            quote_payload["volume"], DataMeta("Yahoo Finance 台灣加權指數", market_time, fetched),
        )

    def get_daily_prices(self, stock: StockInfo, refresh: bool = False) -> tuple[pd.DataFrame, DataMeta]:
        suffix = "TW" if stock.market == "TWSE" else "TWO"
        key = f"history:yahoo:{stock.code}.{suffix}"
        if not refresh:
            cached = self.cache.get(key)
            if cached:
                payload, fetched, stale = cached
                return normalize_prices(pd.DataFrame(payload)), DataMeta("Yahoo Finance 歷史行情", None, fetched, stale)
        url = f"{YAHOO}/{stock.code}.{suffix}?interval=1d&range=3y&events=div%2Csplits"
        try:
            data = self._json(url)
            result = data["chart"]["result"][0]
            timestamps = result["timestamp"]
            quote = result["indicators"]["quote"][0]
            adjusted = result["indicators"].get("adjclose", [{}])[0].get("adjclose", quote["close"])
            frame = pd.DataFrame(
                {
                    "date": pd.to_datetime(timestamps, unit="s", utc=True).tz_convert(TAIPEI).tz_localize(None),
                    "open": quote["open"], "high": quote["high"], "low": quote["low"],
                    "close": adjusted, "volume": quote["volume"],
                }
            ).dropna()
            frame = normalize_prices(frame)
            fetched = self.cache.set(key, frame.assign(date=frame["date"].dt.strftime("%Y-%m-%d")).to_dict("records"), 21600)
            market_time = datetime.fromtimestamp(result["meta"]["regularMarketTime"], TAIPEI)
            return frame, DataMeta("Yahoo Finance 歷史行情（官方盤後資料不足時補充）", market_time, fetched)
        except Exception as exc:
            stale = self.cache.get(key, allow_stale=True)
            if stale:
                return normalize_prices(pd.DataFrame(stale[0])), DataMeta("Yahoo Finance 快取", None, stale[1], True, str(exc))
            raise ValueError(f"無法取得 {stock.code} 歷史行情：{exc}") from exc

    def _official_quote(self, stock: StockInfo, refresh: bool = False) -> Quote:
        rows, fetched, stale = self._daily_rows(stock.market, refresh)
        code_key = "Code" if stock.market == "TWSE" else "SecuritiesCompanyCode"
        row = next((x for x in rows if str(x.get(code_key)) == stock.code), None)
        if not row:
            raise ValueError("官方當日行情沒有此股票")
        price = _number(row.get("ClosingPrice") or row.get("Close"))
        change = _number(row.get("Change"))
        previous = price - change
        volume = _number(row.get("TradeVolume") or row.get("TradingShares"))
        date = _roc_date(row.get("Date", ""))
        return Quote(stock.code, price, change, change / previous * 100 if previous else 0, volume,
                     DataMeta(f"{stock.market} 官方盤後行情", date, fetched, stale))

    def get_latest_quote(self, stock: StockInfo, refresh: bool = False) -> Quote:
        suffix = "TW" if stock.market == "TWSE" else "TWO"
        now = datetime.now(TAIPEI)
        market_open = now.weekday() < 5 and (9 <= now.hour < 14)
        ttl = 30 if market_open else 300
        key = f"quote:yahoo:{stock.code}.{suffix}"
        if not refresh:
            cached = self.cache.get(key)
            if cached:
                p, fetched, stale = cached
                return Quote(stock.code, p["price"], p["change"], p["change_pct"], p["volume"],
                             DataMeta("Yahoo Finance 最新報價", datetime.fromisoformat(p["market_time"]), fetched, stale))
        try:
            result = self._json(f"{YAHOO}/{stock.code}.{suffix}?interval=1m&range=1d")["chart"]["result"][0]
            meta = result["meta"]
            price = _number(meta.get("regularMarketPrice"))
            previous = _number(meta.get("chartPreviousClose") or meta.get("previousClose"))
            payload = {
                "price": price, "change": price - previous,
                "change_pct": (price / previous - 1) * 100 if previous else 0,
                "volume": _number(meta.get("regularMarketVolume")),
                "market_time": datetime.fromtimestamp(meta["regularMarketTime"], TAIPEI).isoformat(),
            }
            fetched = self.cache.set(key, payload, ttl)
            return Quote(stock.code, payload["price"], payload["change"], payload["change_pct"], payload["volume"],
                         DataMeta("Yahoo Finance 最新報價", datetime.fromisoformat(payload["market_time"]), fetched))
        except Exception as exc:
            quote = self._official_quote(stock, refresh)
            return Quote(
                quote.code, quote.price, quote.change, quote.change_pct, quote.volume,
                DataMeta(quote.meta.source, quote.meta.market_time, quote.meta.fetched_at, True,
                         f"最新報價失敗，已改用官方盤後資料：{exc}"),
            )

    def get_valuation(self, stock: StockInfo, refresh: bool = False) -> tuple[dict, DataMeta]:
        if stock.market == "TWSE":
            rows, fetched, stale = self._cached_json("valuation:twse", f"{TWSE}/exchangeReport/BWIBBU_ALL", 21600, refresh)
            row = next((x for x in rows if x.get("Code") == stock.code), {})
            value = {"pe": _number(row.get("PEratio"), float("nan")), "pb": _number(row.get("PBratio"), float("nan")),
                     "yield": _number(row.get("DividendYield"), float("nan"))}
        else:
            rows, fetched, stale = self._cached_json("valuation:tpex", f"{TPEX}/tpex_mainboard_peratio_analysis", 21600, refresh, True)
            row = next((x for x in rows if x.get("SecuritiesCompanyCode") == stock.code), {})
            value = {"pe": _number(row.get("PriceEarningRatio"), float("nan")), "pb": _number(row.get("PriceBookRatio"), float("nan")),
                     "yield": _number(row.get("YieldRatio"), float("nan"))}
        return value, DataMeta(f"{stock.market} 官方估值", _roc_date(row.get("Date", "")), fetched, stale)

    def get_monthly_revenue(self, stock: StockInfo, refresh: bool = False) -> tuple[dict, DataMeta]:
        if getattr(stock, "asset_type", "ETF" if stock.code.startswith("00") else "STOCK") == "ETF":
            return {}, DataMeta("ETF 不適用公司月營收", None, datetime.now(timezone.utc))
        if stock.market == "TWSE":
            key, url, tpex = "revenue:twse", f"{TWSE}/opendata/t187ap05_L", False
        else:
            key, url, tpex = "revenue:tpex", f"{TPEX}/mopsfin_t187ap05_O", True
        rows, fetched, stale = self._cached_json(key, url, 21600, refresh, tpex)
        row = next((x for x in rows if str(x.get("公司代號")) == stock.code), {})
        value = {"month": row.get("資料年月", ""), "revenue": _number(row.get("營業收入-當月營收"), float("nan")),
                 "mom": _number(row.get("營業收入-上月比較增減(%)"), float("nan")),
                 "yoy": _number(row.get("營業收入-去年同月增減(%)"), float("nan"))}
        return value, DataMeta(f"{stock.market} 公開資訊觀測站月營收", None, fetched, stale)

    def get_institutional_trading(self, stock: StockInfo, refresh: bool = False) -> tuple[dict, DataMeta]:
        if getattr(stock, "asset_type", "ETF" if stock.code.startswith("00") else "STOCK") == "ETF":
            return {}, DataMeta("ETF 不適用個股法人籌碼評分", None, datetime.now(timezone.utc))
        if stock.market == "TPEx":
            rows, fetched, stale = self._cached_json("institution:tpex:trust", f"{TPEX}/tpex_3insti_trading", 21600, refresh, True)
            row = next((x for x in rows if str(x.get("SecuritiesCompanyCode")) == stock.code), {})
            value = {"investment_trust_net": _number(row.get("NetBuy"), 0), "foreign_net": None, "dealer_net": None}
            return value, DataMeta("TPEx 官方投信買賣超", _roc_date(row.get("Date", "")), fetched, stale)
        return {"investment_trust_net": None, "foreign_net": None, "dealer_net": None}, DataMeta(
            "TWSE 法人資料暫缺", None, datetime.now(timezone.utc), True, "本次官方端點未提供可穩定解析的個股法人資料"
        )

    def get_hot_lists(self, refresh: bool = False) -> dict[str, list[dict]]:
        rows: list[dict] = []
        industries = self._industry_map()
        for market in ("TWSE", "TPEx"):
            try:
                data, _, _ = self._daily_rows(market, refresh)
            except Exception:
                continue
            for r in data:
                code = str(r.get("Code") or r.get("SecuritiesCompanyCode") or "")
                is_stock = len(code) == 4 and code.isdigit() and not code.startswith("0")
                is_etf = 4 <= len(code) <= 6 and code.isdigit() and code.startswith("00")
                if not (is_stock or is_etf):
                    continue
                price = _number(r.get("ClosingPrice") or r.get("Close"))
                change = _number(r.get("Change"))
                previous = price - change
                market_time = _roc_date(r.get("Date", ""))
                rows.append({"code": code, "name": r.get("Name") or r.get("CompanyName"), "market": market,
                             "industry": "ETF" if is_etf else industries.get(code, "其他業"),
                             "price": price, "change_pct": change / previous * 100 if previous else 0,
                             "volume": _number(r.get("TradeVolume") or r.get("TradingShares")),
                             "market_time": market_time, "source": f"{market} 官方盤後行情"})
        if refresh and rows:
            # OpenAPI may still contain the previous close during market hours.
            # Build rankings from the complete TWSE/TPEx MIS snapshot.
            candidates = {item["code"]: item for item in rows}
            live_codes: set[str] = set()
            candidate_items = list(candidates.values())
            cached_snapshot = self.cache.get("hot:mis:full-market")
            if cached_snapshot:
                live_quotes = cached_snapshot[0]
            else:
                live_quotes = []
                # MIS returns an empty batch when the query becomes too long;
                # 120 channels stays below that limit for six-digit ETFs.
                for start in range(0, len(candidate_items), 120):
                    batch = candidate_items[start:start + 120]
                    channels = "|".join(
                        f"{'tse' if item['market'] == 'TWSE' else 'otc'}_{item['code']}.tw"
                        for item in batch
                    )
                    try:
                        payload = self._json(f"{TWSE_MIS}?ex_ch={channels}&json=1&delay=0")
                    except Exception:
                        continue
                    live_quotes.extend(payload.get("msgArray", []))
                if live_quotes:
                    now = datetime.now(TAIPEI)
                    market_open = (
                        now.weekday() < 5
                        and now.hour >= 9
                        and (now.hour < 13 or (now.hour == 13 and now.minute < 30))
                    )
                    self.cache.set("hot:mis:full-market", live_quotes, 10 if market_open else 300)
            for quote in live_quotes:
                code = str(quote.get("c", "")).strip()
                item = candidates.get(code)
                price = _number(quote.get("z"))
                previous = _number(quote.get("y"))
                if item is None or price <= 0 or previous <= 0:
                    continue
                item["price"] = price
                item["change_pct"] = (price / previous - 1) * 100
                item["volume"] = _number(quote.get("v")) * 1000
                try:
                    item["market_time"] = datetime.strptime(
                        f"{quote.get('d')} {quote.get('t')}", "%Y%m%d %H:%M:%S"
                    ).replace(tzinfo=TAIPEI)
                except (TypeError, ValueError):
                    item["market_time"] = datetime.now(TAIPEI)
                item["source"] = "TWSE MIS 盤中行情"
                live_codes.add(code)
            if live_codes:
                rows = [item for item in rows if item["code"] in live_codes]
            else:
                # Retry visible candidates in one compact MIS request.
                volume_candidates = sorted(rows, key=lambda x: x["volume"], reverse=True)[:10]
                gain_candidates = sorted(rows, key=lambda x: x["change_pct"], reverse=True)[:10]
                loss_candidates = sorted(rows, key=lambda x: x["change_pct"])[:10]
                fallback_items = {item["code"]: item for item in (*volume_candidates, *gain_candidates, *loss_candidates)}
                channels = "|".join(
                    f"{'tse' if item['market'] == 'TWSE' else 'otc'}_{item['code']}.tw"
                    for item in fallback_items.values()
                )
                compact_quotes = []
                try:
                    compact_quotes = self._json(f"{TWSE_MIS}?ex_ch={channels}&json=1&delay=0").get("msgArray", [])
                except Exception:
                    pass
                corrected: list[dict] = []
                for quote in compact_quotes:
                    item = fallback_items.get(str(quote.get("c", "")).strip())
                    price = _number(quote.get("z"))
                    previous = _number(quote.get("y"))
                    if item is None or price <= 0 or previous <= 0:
                        continue
                    item["price"] = price
                    item["change_pct"] = (price / previous - 1) * 100
                    item["volume"] = _number(quote.get("v")) * 1000
                    try:
                        item["market_time"] = datetime.strptime(
                            f"{quote.get('d')} {quote.get('t')}", "%Y%m%d %H:%M:%S"
                        ).replace(tzinfo=TAIPEI)
                    except (TypeError, ValueError):
                        item["market_time"] = datetime.now(TAIPEI)
                    item["source"] = "TWSE MIS 盤中行情"
                    corrected.append(item)

                now = datetime.now(TAIPEI)
                market_open = (now.weekday() < 5 and now.hour >= 9 and (now.hour < 13 or (now.hour == 13 and now.minute < 30)))

                def fetch_fallback(item):
                    stock = StockInfo(
                        item["code"], item["name"], item["market"],
                        industry=item["industry"],
                        asset_type="ETF" if item["code"].startswith("00") else "STOCK",
                    )
                    return item, self.get_latest_quote(stock, refresh=market_open)

                if not corrected:
                    with ThreadPoolExecutor(max_workers=8) as executor:
                        futures = [executor.submit(fetch_fallback, item) for item in fallback_items.values()]
                        for future in as_completed(futures):
                            try:
                                item, quote = future.result()
                            except Exception:
                                continue
                            item["price"] = quote.price
                            item["change_pct"] = quote.change_pct
                            item["volume"] = quote.volume
                            item["market_time"] = quote.meta.market_time
                            item["source"] = quote.meta.source
                            corrected.append(item)
                if corrected:
                    rows = corrected
        return {
            "volume": sorted(rows, key=lambda x: x["volume"], reverse=True)[:50],
            "gainers": sorted(rows, key=lambda x: x["change_pct"], reverse=True)[:50],
            "losers": sorted(rows, key=lambda x: x["change_pct"])[:50],
        }

    def get_dividend_events(self, stock: StockInfo, refresh: bool = False) -> list[DividendEvent]:
        events: list[DividendEvent] = []
        now = datetime.now(TAIPEI)
        if stock.market == "TWSE":
            rows, _, _ = self._cached_json(
                "dividend:ex:twse", f"{TWSE}/exchangeReport/TWT48U_ALL", 21600, refresh
            )
            for row in rows:
                if str(row.get("Code")) != stock.code:
                    continue
                ex_date = _roc_date(row.get("Date", ""))
                cash = _number(row.get("CashDividend"), 0)
                events.append(DividendEvent(
                    stock.code, cash, ex_date, None, "TWSE 除權除息預告",
                    "等待除息" if ex_date and ex_date > now else "已除息，發放日待公告",
                ))
            if getattr(stock, "asset_type", "ETF" if stock.code.startswith("00") else "STOCK") == "STOCK":
                rows, _, _ = self._cached_json(
                    "dividend:declared:twse", f"{TWSE}/opendata/t187ap45_L", 21600, refresh
                )
                company_rows = [r for r in rows if str(r.get("公司代號")) == stock.code]
                if company_rows:
                    row = max(company_rows, key=lambda r: str(r.get("董事會（擬議）股利分派日", "")))
                    cash = sum(_number(row.get(field), 0) for field in (
                        "股東配發-盈餘分配之現金股利(元/股)",
                        "股東配發-法定盈餘公積發放之現金(元/股)",
                        "股東配發-資本公積發放之現金(元/股)",
                    ))
                    if cash > 0 and not any(abs(e.cash_per_share - cash) < 1e-6 for e in events):
                        events.append(DividendEvent(
                            stock.code, cash, None, None, "公開資訊觀測站股利分派",
                            "已公告股利，除息與發放日待公告", str(row.get("股利年度", "")),
                        ))
        else:
            rows, _, _ = self._cached_json(
                "dividend:ex:tpex", f"{TPEX}/tpex_exright_prepost", 21600, refresh, True
            )
            for row in rows:
                if str(row.get("SecuritiesCompanyCode")) != stock.code:
                    continue
                ex_date = _roc_date(row.get("ExRrightsExDividendDate", ""))
                cash = _number(row.get("CashDividend"), 0)
                events.append(DividendEvent(
                    stock.code, cash, ex_date, None, "TPEx 除權除息預告",
                    "等待除息" if ex_date and ex_date > now else "已除息，發放日待公告",
                ))

        # Yahoo events provide recent historical ex-dividend records, useful for ETFs
        # and companies that are no longer present in the official upcoming schedule.
        suffix = "TW" if stock.market == "TWSE" else "TWO"
        try:
            data, _, _ = self._cached_json(
                f"dividend:yahoo:{stock.code}.{suffix}",
                f"{YAHOO}/{stock.code}.{suffix}?interval=1d&range=2y&events=div",
                21600, refresh,
            )
            result = data["chart"]["result"][0]
            for item in result.get("events", {}).get("dividends", {}).values():
                ex_date = datetime.fromtimestamp(int(item["date"]), TAIPEI)
                cash = _number(item.get("amount"), 0)
                if not any(
                    (e.ex_dividend_date and e.ex_dividend_date.date() == ex_date.date())
                    or (e.ex_dividend_date is None and abs(e.cash_per_share - cash) < 1e-5)
                    for e in events
                ):
                    events.append(DividendEvent(
                        stock.code, cash, ex_date, None, "Yahoo 歷史除息紀錄",
                        "已除息，發放日未提供",
                    ))
        except Exception:
            pass
        return sorted(
            events,
            key=lambda event: event.ex_dividend_date or datetime.max.replace(tzinfo=TAIPEI),
            reverse=True,
        )
