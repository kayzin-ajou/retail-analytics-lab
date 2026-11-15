"""Self-contained export, uses only derived summary rows. No external CSS/JS."""
from datetime import datetime, timezone
from html import escape
from analytics import metrics, monthly, country, products, rfm, build_suggestions


def fmt(v):
    return f"£{v:,.2f}"


def export_html(df, audit_info, steps, source_label, duplicate_option=True):
    m = metrics(df)
    mo, co, pr, customers = monthly(df), country(df), products(df), rfm(df)
    tables = [
        ("정제 작업 기록", steps), ("월별 매출", mo), ("상위 국가", co.head(10)),
        ("상위 상품", pr.head(10)), ("고객 세그먼트별 인원", customers.groupby("Segment").size().rename("고객 수").reset_index() if not customers.empty else customers)
    ]
    panels = "".join(f'<section><h2>{escape(name)}</h2>{table.to_html(index=False, escape=True, border=0, classes="tbl")}</section>' for name,table in tables)
    notes = "".join(f"<li><strong>{escape(a)}</strong>: {escape(b)} {escape(c)}</li>" for a,b,c in build_suggestions(df))
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    return f'''<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><title>Retail Analytics Lab | 분석 보고서</title>
<style>body{{font-family:-apple-system,BlinkMacSystemFont,'Malgun Gothic',sans-serif;max-width:940px;margin:45px auto;padding:0 24px;color:#1b2634;line-height:1.65}}h1{{font-size:31px}}h2{{font-size:20px;color:#214c77;margin-top:36px}}header{{border-bottom:3px solid #1d647c;padding-bottom:20px}}.small{{color:#617384;font-size:13px}}.kpis{{display:flex;gap:14px;flex-wrap:wrap;margin:25px 0}}.kpi{{background:#edf4f8;padding:14px;border-radius:10px;min-width:150px}}.kpi b{{font-size:22px}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{border-bottom:1px solid #dbe4ea;text-align:left;padding:9px}}th{{background:#eef3f8}}section{{page-break-inside:avoid}}li{{margin-bottom:11px}}@media print{{body{{margin:0}}}}</style></head><body>
<header><p class="small">RETAIL ANALYTICS LAB · EDUCATIONAL ANALYSIS</p><h1>실무형 온라인 판매 데이터 분석 보고서</h1><p>자료 구분: <b>{escape(source_label)}</b> / 생성: {timestamp}</p></header>
<div class="kpis"><div class="kpi">양수 판매라인 매출<br><b>{fmt(m['매출액_양수거래'])}</b></div><div class="kpi">주문 건수<br><b>{m['주문수']:,}</b></div><div class="kpi">주문당 평균<br><b>{fmt(m['주문당평균금액'])}</b></div><div class="kpi">식별 가능 고객<br><b>{m['식별가능고객수']:,}</b></div></div>
<section><h2>1. 질문과 방법</h2><p>거래 데이터로 월별·국가별·상품별 매출과 고객 구매 특성을 이해합니다. InvoiceNo에 C가 붙은 취소행, 음수 수량, 0 이하 단가를 양수 판매액에서 제외했습니다. 동일 전체행의 중복 제거: {'예' if duplicate_option else '아니오'}.</p><p>원본 {audit_info['행 수']:,}행 → 분석용 {len(df):,}행</p></section>
{panels}
<section><h2>2. 데이터 기반 확인 과제</h2><ul>{notes}</ul></section>
<section><h2>3. 해석 한계 및 출처</h2><p>표시된 매출은 양수 거래라인 합계이며 환불 정산 후 순매출, 이익, 부가세, 실제 현금흐름이 아닙니다. 배송비나 비용성 StockCode가 포함될 수 있습니다. 고객번호가 없는 매출은 RFM 분석에서 제외됩니다. RFM 세그먼트는 규칙 기반 분류일 뿐 실제 이탈 예측이 아닙니다. 상관관계로 마케팅 효과의 인과성을 판단할 수 없습니다.</p>
<p>UCI Online Retail (Chen, D., 2015), https://doi.org/10.24432/C5BW33, CC BY 4.0. 실제 자료를 다운로드한 경우: 2010-12-01~2011-12-09 영국 익명 소매기업의 역사적 거래 데이터. 자료 구분이 학습용 또는 사용자 파일인 경우 원본과 다를 수 있습니다.</p></section>
</body></html>'''
