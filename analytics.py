"""Pure, tested analytical functions for Retail Analytics Lab.

Definition: 'sales' is the sum of positive invoice-line quantity * unit price,
excluding cancellation-coded lines. It is NOT audited/net company revenue.
"""
from __future__ import annotations
import io
import sqlite3
import numpy as np
import pandas as pd

REQUIRED = ["InvoiceNo", "StockCode", "InvoiceDate", "Quantity", "UnitPrice"]
OPTIONAL = ["Description", "CustomerID", "Country"]
COLUMNS = REQUIRED + OPTIONAL


def harmonize(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize supported UCI-shaped CSV/XLSX headers and types; never invent a value."""
    df = df.copy()
    keys = {str(c).lower().replace(" ", "").replace("_", ""): str(c) for c in df.columns}
    names = {}
    for canonical in COLUMNS:
        k = canonical.lower()
        if k in keys:
            names[keys[k]] = canonical
    # UCI sometimes ships Customer ID with whitespace.
    df = df.rename(columns=names)
    absent = sorted(set(REQUIRED) - set(df.columns))
    if absent:
        raise ValueError("필수 열이 없습니다: " + ", ".join(absent))
    for name in OPTIONAL:
        if name not in df:
            df[name] = pd.NA
    df = df[COLUMNS].copy()
    for name in ["InvoiceNo", "StockCode", "Description", "Country"]:
        df[name] = df[name].astype("string").str.strip()
    # Excel may store customer identifiers as floats: 12345.0 -> 12345
    df["CustomerID"] = (df["CustomerID"].astype("string")
                        .str.strip().str.replace(r"\.0$", "", regex=True))
    for name in ["InvoiceNo", "StockCode", "CustomerID"]:
        df[name] = df[name].replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "<NA>": pd.NA})
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
    df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce")
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
    return df


def audit(df: pd.DataFrame) -> dict:
    df = harmonize(df)
    inv = df["InvoiceNo"].fillna("")
    bad_core = (df["InvoiceNo"].isna() | df["InvoiceDate"].isna() |
                df["Quantity"].isna() | df["UnitPrice"].isna())
    return {
        "행 수": len(df),
        "완전 중복행": int(df.duplicated().sum()),
        "취소코드(C) 행": int(inv.str.upper().str.startswith("C").sum()),
        "수량 0 이하": int((df["Quantity"] <= 0).sum()),
        "단가 0 이하": int((df["UnitPrice"] <= 0).sum()),
        "필수값·날짜·숫자 오류": int(bad_core.sum()),
        "고객번호 누락": int(df["CustomerID"].isna().sum()),
        "상품 설명 누락": int(df["Description"].isna().sum()),
    }


def clean_transactions(df: pd.DataFrame, drop_duplicates: bool = True):
    """Return positive sale lines and sequential rejection counts.

    Some exact duplicate lines can be legitimate; choice is exposed in UI.
    Returns (clean_df, quality_steps).
    """
    df = harmonize(df)
    original = len(df)
    rows = []
    if drop_duplicates:
        before = len(df)
        df = df.drop_duplicates().copy()
        rows.append(("동일한 모든 열의 중복행 제외", before - len(df)))
    else:
        rows.append(("완전 중복행 유지 (사용자 설정)", 0))
    invalid = (df["InvoiceNo"].isna() | df["InvoiceDate"].isna() |
               df["Quantity"].isna() | df["UnitPrice"].isna())
    rows.append(("필수값·날짜·숫자 오류 제외", int(invalid.sum())))
    df = df.loc[~invalid].copy()
    canceled = df["InvoiceNo"].str.upper().str.startswith("C") | (df["Quantity"] < 0)
    rows.append(("취소코드 또는 음수 수량 제외", int(canceled.sum())))
    df = df.loc[~canceled].copy()
    invalid_sales = (df["Quantity"] <= 0) | (df["UnitPrice"] <= 0)
    rows.append(("수량·단가 0 이하 제외", int(invalid_sales.sum())))
    df = df.loc[~invalid_sales].copy()
    df["Description"] = df["Description"].fillna("(상품명 미기재)").replace("", "(상품명 미기재)")
    df["Country"] = df["Country"].fillna("(국가 미기재)").replace("", "(국가 미기재)")
    df["Sales"] = df["Quantity"] * df["UnitPrice"]
    df["Month"] = df["InvoiceDate"].dt.strftime("%Y-%m")
    df["Day"] = df["InvoiceDate"].dt.strftime("%Y-%m-%d")
    steps = pd.DataFrame(rows, columns=["처리 기준", "제외 행 수"])
    assert len(df) + int(steps["제외 행 수"].sum()) == original
    return df.reset_index(drop=True), steps


def metrics(df: pd.DataFrame) -> dict:
    total = float(df["Sales"].sum())
    orders = int(df["InvoiceNo"].nunique())
    customers = int(df["CustomerID"].nunique())
    return {
        "매출액_양수거래": total,
        "주문수": orders,
        "주문당평균금액": total / orders if orders else 0,
        "식별가능고객수": customers,
        "판매라인수": int(len(df)),
        "고객식별가능매출비율": (float(df.loc[df["CustomerID"].notna(), "Sales"].sum()) / total if total else 0),
    }


def monthly(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby("Month", as_index=False).agg(매출=("Sales", "sum"), 주문수=("InvoiceNo", "nunique")).sort_values("Month")


def country(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby("Country", as_index=False).agg(매출=("Sales", "sum"), 주문수=("InvoiceNo", "nunique")).sort_values("매출", ascending=False)


def products(df: pd.DataFrame) -> pd.DataFrame:
    # StockCode is the durable product key; Description may vary within same product.
    tmp = df[["StockCode", "Description", "Sales", "Quantity"]].copy()
    names = tmp.groupby("StockCode")["Description"].agg(lambda x: x.mode().iloc[0] if len(x.mode()) else x.iloc[0])
    out = tmp.groupby("StockCode", as_index=False).agg(매출=("Sales", "sum"), 판매수량=("Quantity", "sum"))
    out["상품명"] = out["StockCode"].map(names)
    return out[["StockCode", "상품명", "매출", "판매수량"]].sort_values("매출", ascending=False)


def rfm(df: pd.DataFrame) -> pd.DataFrame:
    cust = df.loc[df["CustomerID"].notna()].copy()
    if cust.empty:
        return pd.DataFrame(columns=["CustomerID", "Recency", "Frequency", "Monetary", "R", "F", "M", "Segment"])
    anchor = cust["InvoiceDate"].max().normalize() + pd.Timedelta(days=1)
    out = cust.groupby("CustomerID", as_index=False).agg(
        last_date=("InvoiceDate", "max"), Frequency=("InvoiceNo", "nunique"), Monetary=("Sales", "sum"))
    out["Recency"] = (anchor - out["last_date"].dt.normalize()).dt.days
    out["R"] = (6 - np.ceil(out["Recency"].rank(pct=True, method="average") * 5)).clip(1, 5).astype(int)
    out["F"] = np.ceil(out["Frequency"].rank(pct=True, method="average") * 5).clip(1, 5).astype(int)
    out["M"] = np.ceil(out["Monetary"].rank(pct=True, method="average") * 5).clip(1, 5).astype(int)
    conditions = [
        (out.R >= 4) & (out.F >= 4) & (out.M >= 4),
        (out.R <= 2) & (out.F >= 3),
        (out.R >= 4) & (out.F <= 2),
        (out.F >= 4),
    ]
    out["Segment"] = np.select(conditions, ["핵심 고객", "이탈 위험 후보", "최근 유입 고객", "충성 고객"], default="일반 고객")
    return out.drop(columns="last_date").sort_values("Monetary", ascending=False).reset_index(drop=True)


SQL_QUERIES = {
    "월별 매출": "SELECT substr(InvoiceDate,1,7) AS Month, ROUND(SUM(Sales),2) AS Sales FROM sales GROUP BY 1 ORDER BY 1",
    "매출 상위 국가": "SELECT Country, ROUND(SUM(Sales),2) AS Sales, COUNT(DISTINCT InvoiceNo) AS Orders FROM sales GROUP BY Country ORDER BY Sales DESC LIMIT 10",
    "매출 상위 상품": "SELECT StockCode, MAX(Description) AS Description, ROUND(SUM(Sales),2) AS Sales FROM sales GROUP BY StockCode ORDER BY Sales DESC LIMIT 10",
}


def run_example_sql(df: pd.DataFrame, label: str) -> tuple[str, pd.DataFrame]:
    query = SQL_QUERIES[label]
    fields = ["InvoiceNo", "InvoiceDate", "Country", "StockCode", "Description", "Sales"]
    tmp = df[fields].copy()
    tmp["InvoiceDate"] = tmp["InvoiceDate"].dt.strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(":memory:") as db:
        tmp.to_sql("sales", db, index=False)
        result = pd.read_sql_query(query, db)
    return query, result


def build_suggestions(df: pd.DataFrame) -> list[tuple[str, str, str]]:
    """Transparent heuristic suggestions, not validated causal recommendations."""
    k = metrics(df)
    suggestions = []
    c = country(df)
    if not c.empty:
        share = float(c.iloc[0]["매출"]) / max(k["매출액_양수거래"], 1)
        suggestions.append(("시장 집중도 확인", f"매출 상위 국가 비중이 {share:.1%}입니다.", "국가별 물류·마케팅 효율을 확인하세요. 시장 집중도가 높아도 반드시 위험을 뜻하지는 않습니다."))
    r = rfm(df)
    if not r.empty:
        n = int((r.Segment == "이탈 위험 후보").sum())
        suggestions.append(("재구매 고객 검토", f"RFM 규칙에 따른 이탈 위험 후보는 {n:,}명입니다.", "구매 주기와 연락 동의 여부를 추가 확인한 후 유지 캠페인을 시험하세요. 이탈을 예측한 결과는 아닙니다."))
    m = monthly(df)
    if len(m) >= 3:
        i = m["매출"].idxmax()
        suggestions.append(("시즌별 수요 검토", f"집계 기간 중 매출이 가장 높은 달은 {m.loc[i, 'Month']}입니다.", "프로모션, 휴일, 부분 월 포함 여부를 확인해야 원인을 판단할 수 있습니다."))
    return suggestions


def make_demo_data(seed: int = 42, n: int = 900) -> pd.DataFrame:
    """SYNTHETIC; a reproducible classroom example, NOT a real retailer dataset."""
    rng = np.random.default_rng(seed)
    dates = pd.Timestamp("2025-01-01") + pd.to_timedelta(rng.integers(0, 365, n), unit="D")
    codes = rng.choice(["D-01", "D-02", "D-03", "D-04", "D-05"], n, p=[.34,.23,.18,.15,.10])
    info = {"D-01": ("가상 텀블러", 12.0), "D-02": ("가상 노트", 6.5), "D-03": ("가상 수첩", 8.0),
            "D-04": ("가상 머그컵", 15.5), "D-05": ("가상 펜 세트", 4.5)}
    quantity = rng.integers(1, 8, n).astype(float)
    invoice = [f"T{30000+i//3:06d}" for i in range(n)]
    # Mix in negative cancellations, free lines, missing IDs and duplicate rows.
    quantity[:24] *= -1
    for i in range(min(24, n)): invoice[i] = "C" + invoice[i]
    prices = [info[x][1] for x in codes]
    for i in range(27, min(34, n)): prices[i] = 0.0
    customers = [f"DEMO-{x:03d}" for x in rng.integers(1, 160, n)]
    for i in range(40, min(65, n)): customers[i] = None
    df = pd.DataFrame({"InvoiceNo": invoice, "StockCode": codes, "Description": [info[x][0] for x in codes],
        "InvoiceDate": dates, "Quantity": quantity, "UnitPrice": prices,
        "CustomerID": customers, "Country": rng.choice(["United Kingdom","France","Germany","Korea"], n, p=[.7,.12,.12,.06])})
    if n > 70: df.loc[70:min(78, n-1), "Description"] = None
    if n > 91: df = pd.concat([df, df.iloc[[90,91]]], ignore_index=True)
    return df


def load_uci_zip(path) -> pd.DataFrame:
    """Read UCI's official zip without extracting untrusted file paths."""
    from zipfile import ZipFile
    with ZipFile(path) as z:
        books = [name for name in z.namelist() if name.lower().endswith(".xlsx") and not name.startswith("__MACOSX")]
        if not books:
            raise ValueError("공식 ZIP에 XLSX 파일이 없습니다.")
        with z.open(books[0]) as f:
            content = f.read()
    return pd.read_excel(io.BytesIO(content), engine="openpyxl", dtype={"InvoiceNo":"string", "StockCode":"string", "CustomerID":"string"})
