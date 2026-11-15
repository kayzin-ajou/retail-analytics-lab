"""Retail Analytics Lab — 8-step local business data analysis walkthrough."""
from pathlib import Path
import io
from html import escape
import json
import pandas as pd
import plotly.express as px
import streamlit as st
from analytics import (COLUMNS, REQUIRED, SQL_QUERIES, harmonize, audit, clean_transactions,
    make_demo_data, load_uci_zip, metrics, monthly, country, products, rfm,
    run_example_sql, build_suggestions)
from reporting import export_html
from scripts.download_uci import download

ROOT = Path(__file__).resolve().parent
RAW_ZIP = ROOT / "data" / "online_retail_original.zip"
DOC_URL = "https://archive.ics.uci.edu/dataset/352/online+retail"
STEPS = ["01 · 문제 정의", "02 · 데이터 수집/이해", "03 · 품질 검사", "04 · 정제 및 가공",
         "05 · SQL로 분석", "06 · 시각화·KPI", "07 · 고객 분석 RFM", "08 · 결론·보고서"]

st.set_page_config(page_title="Retail Analytics Lab", page_icon="📈", layout="wide", initial_sidebar_state="expanded")
st.markdown('''<style>
:root{--lab:#5fe0c8} .block-container{padding-top:2rem;max-width:1450px}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#102235,#152a3b)}
[data-testid="stSidebar"] *{color:#ecf5f7!important}
.hero{background:linear-gradient(114deg,#102a40,#124558);border:1px solid #2f6073;border-radius:17px;padding:28px 32px;color:white;margin-bottom:18px}
.hero h1{font-size:2.15rem;margin:4px 0;color:white}.hero p{color:#c5e4e5;margin:0}
.label{color:#75e1cf;font-weight:800;letter-spacing:1.4px;font-size:11px}
.explain{background:rgba(110,166,188,.09);border-left:3px solid #38bfae;padding:14px 17px;border-radius:5px;margin:10px 0 22px}
.source-line{background:rgba(45,161,137,.12);border-radius:7px;padding:9px 12px;margin:13px 0;font-size:14px}
.limitation{background:rgba(235,169,80,.09);border-left:3px solid #d59f47;padding:12px 14px;border-radius:5px}
[data-testid="stMetric"]{border:1px solid rgba(128,157,177,.22);border-radius:12px;padding:13px;background:rgba(124,157,177,.05)}
</style>''', unsafe_allow_html=True)

@st.cache_data(show_spinner="공식 UCI 엑셀 파일을 읽는 중입니다. 첫 실행은 다소 느릴 수 있어요…")
def uci_data(path: str, mtime: float) -> pd.DataFrame:
    return load_uci_zip(path)

@st.cache_data(show_spinner=False)
def demo_data() -> pd.DataFrame:
    return make_demo_data()

@st.cache_data(show_spinner=False)
def clean_data(data, drop_duplicates):
    return clean_transactions(data, drop_duplicates)

st.sidebar.markdown("## 📊 Retail Analytics Lab")
st.sidebar.caption("기업 거래 데이터를 분석하는 실무 체험")
st.sidebar.divider()
st.sidebar.markdown("**1. 데이터 소스 선택**")
source_options = ["학습용 가상 데이터", "공개된 실제 기업 거래 데이터"]
if RAW_ZIP.exists():
    default_source = 1
else:
    default_source = 0
selected_source = st.sidebar.radio("분석할 데이터", source_options + ["내 파일 업로드 (CSV/XLSX)"], index=default_source)
uploaded = None
real_data_failed = False
if selected_source == "공개된 실제 기업 거래 데이터":
    if not RAW_ZIP.exists():
        st.sidebar.info("최초 1회 공식 데이터 다운로드가 필요합니다. 약 22.6MB")
        if st.sidebar.button("⬇ UCI 원본 다운로드", use_container_width=True):
            with st.spinner("UCI에서 실제 거래 데이터를 받는 중…"):
                try:
                    download()
                    st.rerun()
                except Exception as exc:
                    st.sidebar.error(f"공식 사이트 다운로드 실패: {exc}")
                    real_data_failed = True
        st.sidebar.markdown(f"[공식 자료 페이지]({DOC_URL})")
    else:
        st.sidebar.success("UCI 원본 저장됨 · 실제 데이터")
        if st.sidebar.button("원본 파일 갱신", use_container_width=True):
            try:
                download(force=True)
                st.cache_data.clear()
                st.rerun()
            except Exception as exc:
                st.sidebar.error(f"갱신 실패: {exc}")
if selected_source.startswith("내 파일"):
    uploaded = st.sidebar.file_uploader("UCI 구조의 CSV/XLSX 선택", type=["csv","xlsx"])
    st.sidebar.caption("업로드 파일은 앱 실행 서버에서 처리됩니다. 공개 웹사이트에는 회사 비공개 데이터나 개인정보를 올리지 마세요. 스키마: InvoiceNo, StockCode, InvoiceDate, Quantity, UnitPrice (나머지 선택)")

st.sidebar.divider()
st.sidebar.markdown("**2. 분석 순서**")
step = st.sidebar.radio("진행 단계", STEPS, label_visibility="collapsed")
st.sidebar.divider()
drop_duplicates = st.sidebar.checkbox("완전히 같은 행은 중복으로 제외", value=True,
    help="실제 동일 거래 라인이 두 번 정당하게 기록된 경우도 있으므로 회사의 거래 규칙을 확인해야 합니다.")
st.sidebar.caption("© UCI dataset authors · CC BY 4.0 | Python · pandas · SQL · Plotly")

source_label = ""
raw = None
try:
    if selected_source == "학습용 가상 데이터":
        raw = demo_data()
        source_label = "가상 학습용 데이터 (실제 회사 데이터 아님)"
    elif selected_source == "공개된 실제 기업 거래 데이터" and RAW_ZIP.exists():
        raw = uci_data(str(RAW_ZIP), RAW_ZIP.stat().st_mtime)
        source_label = "실제 영국 온라인 소매기업 거래 (UCI, 2010–2011)"
    elif uploaded is not None:
        payload = uploaded.getvalue()
        if uploaded.name.lower().endswith(".csv"):
            try:
                raw = pd.read_csv(io.BytesIO(payload), dtype={"InvoiceNo":"string", "StockCode":"string", "CustomerID":"string"}, low_memory=False)
            except UnicodeDecodeError:
                raw = pd.read_csv(io.BytesIO(payload), encoding="cp949", dtype={"InvoiceNo":"string", "StockCode":"string", "CustomerID":"string"}, low_memory=False)
        else:
            raw = pd.read_excel(io.BytesIO(payload), engine="openpyxl")
        source_label = f"사용자가 선택한 로컬 파일: {uploaded.name} (출처 사용자 책임)"
    if raw is not None:
        raw = harmonize(raw)
except Exception as exc:
    st.error(f"데이터를 불러오지 못했습니다: {exc}")
    st.info("공식 자료를 다시 내려받거나 CSV 열 이름과 파일 형식을 확인해주세요.")
    st.stop()

st.markdown('''<div class="hero"><div class="label">END-TO-END DATA ANALYST WORKFLOW</div>
<h1>Retail Analytics Lab</h1><p>실제 기업 거래 데이터로 배우는 데이터 분석 · 문제 정의부터 보고서까지</p></div>''', unsafe_allow_html=True)
if source_label:
    st.markdown(f'<div class="source-line">📍 <b>현재 데이터:</b> {escape(source_label)}</div>', unsafe_allow_html=True)
else:
    st.warning("데이터가 준비되지 않았습니다. 왼쪽에서 실제 데이터 다운로드를 누르거나 파일을 올리세요.")

st.caption("현재 제공하는 실제 데이터는 2010–2011년의 과거 거래 기록입니다. 실시간 매출이나 해당 회사의 최신 경영 현황이 아닙니다.")

if step == STEPS[0]:
    st.subheader("01 · 문제 정의 — 무엇을 알고 싶은가?")
    st.markdown('<div class="explain"><b>분석가의 실제 업무</b><br>그래프를 만들기 전에 회사가 내리고 싶은 결정을 질문으로 바꿉니다. 데이터가 대답할 수 있는 질문과 답할 수 없는 질문을 구분해야 해요.</div>', unsafe_allow_html=True)
    question = st.selectbox("회사에서 받은 질문을 골라보세요", ["어느 달에 매출이 가장 높았을까?", "어느 국가와 상품의 판매액이 높을까?", "고객이 다시 구매하는 패턴이 있을까?"])
    maps = {
        "어느 달에 매출이 가장 높았을까?": ("InvoiceDate, Quantity, UnitPrice", "월별 양수 거래액 합계", "월별 수요를 비교하고 프로모션 시기를 검토"),
        "어느 국가와 상품의 판매액이 높을까?": ("Country, StockCode, Quantity, UnitPrice", "국가별·상품별 매출 순위", "재고·영업 우선순위의 추가 검토"),
        "고객이 다시 구매하는 패턴이 있을까?": ("CustomerID, InvoiceNo, InvoiceDate, Quantity, UnitPrice", "구매 횟수와 RFM 분포", "재구매 대상 가설을 세우고 후속 실험 설계"),
    }
    c1,c2,c3 = st.columns(3)
    for c, title, val in zip([c1,c2,c3],["필요한 원천 데이터","측정 지표 (Metric)","의사결정 (Decision)"],maps[question]):
        c.markdown(f"**{title}**")
        c.info(val)
    st.markdown("#### 전체 분석 절차")
    st.code("문제 정의 → 데이터 수집 → 품질 진단 → 데이터 정제 → SQL 조회 → KPI·시각화 → 고객 분석 → 비즈니스 보고서", language="text")
    st.info("여기서는 취소·반품·비용이 완전히 반영된 '회계상 순매출'을 구하지 않습니다. 먼저 양수 판매 거래액을 분석합니다.")
    st.markdown("**최종 산출물:** 대시보드 + 정제 CSV + 고객 세그먼트 CSV + HTML 분석 보고서")

if raw is None:
    st.stop()

info = audit(raw)
clean, log = clean_data(raw, drop_duplicates)
if clean.empty:
    st.error("선택한 정제 규칙에 따라 유효 판매 데이터가 0행입니다.")
    st.stop()
kpis = metrics(clean)

if step == STEPS[1]:
    st.subheader("02 · 데이터 수집 및 이해 — 이 데이터는 어디서 왔을까?")
    st.markdown('<div class="explain"><b>실무에서 하는 일</b><br>데이터 소유자·출처·수집 시점·스키마(열의 의미)를 확인하고, 분석에 사용해도 되는 자료인지 검토합니다. 실제 회사에서는 DB, 로그, CRM, API를 사용하기도 해요.</div>', unsafe_allow_html=True)
    a,b,c = st.columns(3)
    a.metric("원본 거래 라인", f"{len(raw):,}")
    b.metric("열 수", len(raw.columns))
    c.metric("관찰 시작~종료", f"{raw.InvoiceDate.min():%Y-%m} ~ {raw.InvoiceDate.max():%Y-%m}")
    st.markdown("**데이터 미리보기 (처음 12행)**")
    st.dataframe(raw.head(12), use_container_width=True, hide_index=True)
    descriptions = [
        ("InvoiceNo", "주문/송장 식별번호 · C로 시작하면 취소"),
        ("StockCode", "상품 ID"), ("Description", "상품 이름"),
        ("InvoiceDate", "판매 기록 시각"), ("Quantity", "상품 수량 · 음수는 취소/조정 가능"),
        ("UnitPrice", "개당 가격 (원본 영국 자료는 GBP)"),
        ("CustomerID", "고객 식별 ID · 누락될 수 있음"), ("Country", "고객의 국가")]
    st.dataframe(pd.DataFrame(descriptions, columns=["Column", "실무 의미"]), hide_index=True, use_container_width=True)
    st.markdown(f"**원본 출처:** [UCI Online Retail]({DOC_URL}) · Chen (2015) · DOI: 10.24432/C5BW33 · CC BY 4.0")
    st.warning("UCI 기업명은 공개되어 있지 않습니다. '실제 익명 기업 데이터'이지 특정 유명 회사의 영업정보는 아니에요.")

elif step == STEPS[2]:
    st.subheader("03 · 데이터 품질 검사 — 믿고 분석해도 될까?")
    st.markdown('<div class="explain"><b>실무에서 하는 일</b><br>결측치(Missing Values), 중복(Duplicates), 취소 거래, 이상 수치 등을 찾아서 정제 정책을 작성합니다. 데이터를 무조건 삭제하기 전에 사업적 의미를 확인해야 해요.</div>', unsafe_allow_html=True)
    c1,c2,c3,c4 = st.columns(4)
    for col, (name,key) in zip([c1,c2,c3,c4],[("원본 행 수","행 수"),("완전 중복","완전 중복행"),("취소코드 행","취소코드(C) 행"),("고객 ID 누락","고객번호 누락")]):
        col.metric(name, f"{info[key]:,}")
    st.dataframe(pd.DataFrame([{"검사 항목":k,"건수":v} for k,v in info.items()]), hide_index=True, use_container_width=True)
    miss = raw.isna().sum().rename("누락 수").reset_index().rename(columns={"index":"열 이름"})
    miss["누락 비율"] = miss["누락 수"] / len(raw) * 100
    st.plotly_chart(px.bar(miss.sort_values("누락 비율", ascending=False), x="열 이름", y="누락 비율", title="열별 결측률 (%)", text_auto=".1f"), use_container_width=True)
    st.markdown('<div class="limitation">⚠️ <b>분석가의 판단</b><br>고객번호가 없더라도 판매액은 계산할 수 있습니다. 하지만 고객별 구매 패턴(RFM)에는 사용할 수 없어요. 취소코드 수를 곧바로 반품률로 해석해서도 안 됩니다.</div>', unsafe_allow_html=True)

elif step == STEPS[3]:
    st.subheader("04 · 데이터 정제 및 가공 — 분석 가능한 테이블 만들기")
    st.markdown('<div class="explain"><b>실무에서 하는 일</b><br>분석 기준을 명확히 정한 뒤 데이터를 정리하고 새 계산열(Feature)을 만듭니다. 이 앱은 양수 판매행만 유지하고 <code>Sales = Quantity × UnitPrice</code> 를 계산합니다.</div>', unsafe_allow_html=True)
    a,b,c = st.columns(3)
    a.metric("원본", f"{len(raw):,}행")
    b.metric("정제 후", f"{len(clean):,}행")
    c.metric("제외", f"{len(raw) - len(clean):,}행")
    st.dataframe(log, hide_index=True, use_container_width=True)
    st.markdown("**가공 후 컬럼 확인 (예시 12행)**")
    st.dataframe(clean[["InvoiceNo","StockCode","Description","Quantity","UnitPrice","Sales","Month","CustomerID"]].head(12), use_container_width=True, hide_index=True)
    st.code("Sales = Quantity * UnitPrice\nMonth = InvoiceDate의 연-월\nDay = InvoiceDate의 날짜", language="python")
    st.warning("중복행이 실제 유효 거래일 수도 있습니다. 좌측 '중복 제외' 체크박스를 바꿔 결과 차이를 비교해 보세요.")

elif step == STEPS[4]:
    st.subheader("05 · SQL로 분석 — 회사에서는 데이터를 어떻게 조회할까?")
    st.markdown('<div class="explain"><b>실무에서 하는 일</b><br>데이터 분석가는 SQL의 GROUP BY, SUM, COUNT, ORDER BY 등을 활용해 DB에서 필요한 지표를 만듭니다. 이 앱은 정제 데이터를 로컬 SQLite에 임시 저장해 예시 SQL을 실행합니다.</div>', unsafe_allow_html=True)
    option = st.selectbox("실행할 비즈니스 쿼리", list(SQL_QUERIES))
    st.markdown("**SQL 예제**")
    st.code(SQL_QUERIES[option], language="sql")
    if st.button("▶ SQL 실행", type="primary"):
        with st.spinner("로컬 SQLite로 집계 중…"):
            q, result = run_example_sql(clean, option)
        st.dataframe(result, hide_index=True, use_container_width=True)
        st.download_button("쿼리 결과 CSV", result.to_csv(index=False).encode("utf-8-sig"), file_name="sql_results.csv", mime="text/csv")
    st.caption("읽기 전용 고정 쿼리를 제공합니다. 서버 DB나 외부 회사의 데이터베이스에는 접속하지 않습니다.")

elif step == STEPS[5]:
    st.subheader("06 · KPI와 데이터 시각화 — 지금 무슨 일이 일어났을까?")
    st.markdown('<div class="explain"><b>실무에서 하는 일</b><br>KPI를 정의하고 월별 추세, 상품별·지역별 차이를 비교합니다. 매출이 올랐다는 관찰과 광고 때문에 올랐다는 원인 주장을 구분해야 합니다.</div>', unsafe_allow_html=True)
    a,b,c,d = st.columns(4)
    a.metric("판매액 (양수 거래)", f"£{kpis['매출액_양수거래']:,.0f}")
    b.metric("주문 수", f"{kpis['주문수']:,}")
    c.metric("주문당 평균", f"£{kpis['주문당평균금액']:,.2f}")
    d.metric("식별된 고객", f"{kpis['식별가능고객수']:,}")
    mo, co, pr = monthly(clean), country(clean), products(clean)
    st.plotly_chart(px.line(mo, x="Month", y="매출", markers=True, title="월별 판매액 (GBP, 양수 판매라인)"), use_container_width=True)
    l,r = st.columns(2)
    with l:
        st.plotly_chart(px.bar(co.head(10), x="Country", y="매출", title="상위 10개 국가 (거래액)"), use_container_width=True)
    with r:
        st.plotly_chart(px.bar(pr.head(10), x="StockCode", y="매출", hover_data=["상품명"], title="상위 10개 상품 (거래액)"), use_container_width=True)
    st.markdown('<div class="limitation">월별 첫 달·마지막 달은 부분 월일 수 있습니다. 양수 판매라인의 합계는 반품 정산 후 순매출 또는 이익이 아닙니다.</div>', unsafe_allow_html=True)

elif step == STEPS[6]:
    st.subheader("07 · 고객 분석 (RFM) — 누구에게 어떤 서비스를 제공할까?")
    st.markdown('<div class="explain"><b>실무에서 하는 일</b><br>고객이 얼마나 최근에(Recency), 자주(Frequency), 많이(Monetary) 구매했는지 요약합니다. RFM은 규칙 기반 세분화로, AI의 실제 이탈 예측과는 다릅니다.</div>', unsafe_allow_html=True)
    rf = rfm(clean)
    st.info(f"전체 판매 매출 중 고객번호가 기록된 매출 비율: {kpis['고객식별가능매출비율']:.1%} · 고객번호가 없는 행은 고객 분석에서 제외")
    if rf.empty:
        st.warning("고객 ID가 없어 RFM 분석이 불가능합니다.")
    else:
        summary = rf.groupby("Segment", as_index=False).agg(고객수=("CustomerID","count"), 평균구매액=("Monetary","mean"))
        l,r = st.columns([1,1])
        with l:
            st.plotly_chart(px.pie(summary, names="Segment", values="고객수", hole=0.5, title="RFM 세그먼트 분포"), use_container_width=True)
        with r:
            st.dataframe(summary.round(2), hide_index=True, use_container_width=True)
            st.markdown("**RFM 지표 해석**")
            st.markdown("- **R**: 마지막 구매까지 지난 일수 (낮을수록 최근 구매)\n- **F**: 서로 다른 주문의 횟수\n- **M**: 양수 판매라인 구매액 합계")
        st.dataframe(rf.head(25), hide_index=True, use_container_width=True)
        st.caption("R/F/M 점수는 해당 데이터 안의 상대적 순위로 만든 1~5점입니다. 세그먼트 기준은 분석 연습용이고 회사의 실제 CRM 분류 규칙이 아닙니다.")

elif step == STEPS[7]:
    st.subheader("08 · 비즈니스 결론과 보고서 — 분석으로 무엇을 바꿀까?")
    st.markdown('<div class="explain"><b>실무에서 하는 일</b><br>차트를 보여주는 데서 끝나지 않고, 관찰한 사실 → 가능한 해석 → 검증 방법 → 실행 제안을 연결합니다. 증명하지 못한 원인이나 예측을 확정적으로 말하지 않는 것이 중요합니다.</div>', unsafe_allow_html=True)
    for i,(title, evidence, next_action) in enumerate(build_suggestions(clean),1):
        with st.container(border=True):
            st.markdown(f"**{i}. {title}**")
            st.write("📌 관찰: " + evidence)
            st.write("🧪 다음 확인: " + next_action)
    st.divider()
    st.markdown("#### 내보내기 — 분석 결과 파일")
    l,r,c = st.columns(3)
    with l:
        report = export_html(clean, info, log, source_label, drop_duplicates)
        st.download_button("📄 분석 보고서 HTML", report.encode("utf-8"), file_name="retail_analysis_report.html", mime="text/html", use_container_width=True)
    with r:
        st.download_button("📦 정제 거래 CSV", clean.to_csv(index=False).encode("utf-8-sig"), file_name="retail_cleaned.csv", mime="text/csv", use_container_width=True)
    with c:
        rf = rfm(clean)
        st.download_button("👥 고객 RFM CSV", rf.to_csv(index=False).encode("utf-8-sig"), file_name="retail_customers_rfm.csv", mime="text/csv", use_container_width=True)
    st.markdown("**회사에 보고한다면 마지막에 반드시 답할 질문**")
    st.markdown("1. 회사가 결정해야 할 문제는 무엇인가?  \n2. 이 지표와 정제 기준이 그 문제에 맞는가?  \n3. 비교 대상·데이터 편향·누락 정보는 무엇인가?  \n4. 어떤 작은 실험으로 효과를 검증할 것인가?")
    st.warning("이 프로그램은 교육용 MVP입니다. 실제 고객 개인정보, 회계 결산, 자동화된 비즈니스 의사결정 시스템으로 사용하기 전에 회사 정책과 보안·검증 절차가 필요합니다.")
