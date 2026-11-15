# Retail Analytics Lab — 실무형 데이터 분석 학습 MVP

**목표:** 로컬에서 하나의 웹 대시보드로 문제 정의 → 실제 기업 데이터 수집 → EDA/품질 → 정제 → SQL → KPI·시각화 → 고객 세분화 → 보고서를 따라 하기.

## 데이터의 실제성 / 출처

- **실제 데이터:** Daqing Chen (2015), **Online Retail**, UCI Machine Learning Repository, https://archive.ics.uci.edu/dataset/352/online+retail
- DOI: https://doi.org/10.24432/C5BW33
- 데이터 사용조건: **CC BY 4.0** (출처 표시 필수)
- 원본: 541,909 거래 라인, 2010-12-01~2011-12-09, 영국 익명 온라인 선물 소매기업
- 회사명은 익명. *거래라인*은 영수증/주문 건수와 다릅니다.
- 데이터 자체는 이 ZIP에 넣지 않았습니다. UCI 원본을 사용자 Mac에서 직접 내려받습니다.
- 인터넷 연결이 없으면 **실제 회사와 무관한 합성 학습용 샘플**을 선택해 사용하세요.
- 최신 매출 데이터나 실시간 정보가 아닙니다.

## Mac 실행 방법

1. ZIP을 다운로드하고 Terminal을 엽니다.
2. 아래 명령어를 입력합니다.

```bash
mkdir -p ~/Projects
unzip -o ~/Downloads/Retail_Analytics_Lab_MVP.zip -d ~/Projects
cd ~/Projects/Retail_Analytics_Lab
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run app.py
```

3. 브라우저에서 **http://localhost:8501** 접속.
4. 처음 화면 왼쪽에서 **공개된 실제 기업 거래 데이터** 선택 → **UCI 원본 다운로드** 클릭. (약 22.6MB, 첫 분석은 Excel 로딩 시간 소요.)
5. `01`~`08` 단계를 따라가며 실습.
6. 마지막에 HTML 보고서·정제 CSV·RFM CSV 다운로드.

### 터미널로 실제 데이터만 미리 받기

```bash
cd ~/Projects/Retail_Analytics_Lab
source .venv/bin/activate
python scripts/download_uci.py
streamlit run app.py
```

## 학습할 내용

| 단계 | 질문 | 산출물 |
|---|---|---|
| 01 문제 정의 | 어떤 사업 문제를 분석할까? | 질문·지표·의사결정 |
| 02 수집/이해 | 데이터의 출처와 스키마는? | 원본 행·컬럼·데이터 사전 |
| 03 품질 검사 | 결측·중복·취소·오류는? | 데이터 품질 진단 |
| 04 정제 | 어떤 행을 제외할까? | 재현 가능한 정제 로그 + Sales 열 |
| 05 SQL | DB에서 어떻게 집계할까? | SQLite 예시 쿼리와 결과 |
| 06 KPI·EDA | 언제/어디서/무엇이 팔렸나? | 월별·국가별·상품별 차트 |
| 07 RFM | 고객 구매 경향은? | 상대 점수·규칙기반 고객 그룹 |
| 08 보고서 | 분석으로 무엇을 할까? | HTML 보고서·CSV 파일 |

## 매출 정의 / 해석 주의

- `Sales = Quantity × UnitPrice` (통화: 영국 원본은 GBP)
- `InvoiceNo`가 `C`로 시작하면 취소 기록. 음수 수량·0 이하 수량/단가도 *양수 판매액 분석*에서 제외.
- 따라서 총합은 **양수 거래라인 합계**이지 **순매출·이익·환불 처리 후 정산 금액이 아닙니다**. 배송/수수료 등 비상품 SKU가 있을 수 있어요.
- 완전 동일 행 중복 제거 여부는 왼쪽 체크박스에서 바꿀 수 있습니다. **동일한 행을 자동으로 잘못된 중복이라 단정하지 않습니다.**
- 고객번호 없는 행도 양수 판매액 계산에는 포함. 고객별 RFM에서는 제외.
- 월별 첫·마지막 달은 기간이 덜 차 있는 부분 월일 수 있습니다.
- RFM은 최근성/구매빈도/금액을 상대 순위로 그룹화한 것으로, 이탈 예측 AI가 아닙니다.
- 단지 연관성이 보인다고 광고가 매출 증가의 원인이었다고 주장하면 안 됩니다.

## 회사 CSV와 분석해보고 싶다면

왼쪽 **내 파일 업로드**에 CSV 또는 XLSX를 넣으세요. 앱은 **UCI와 같은 거래 라인 형식**을 기대합니다.

필수 열: `InvoiceNo`, `StockCode`, `InvoiceDate`, `Quantity`, `UnitPrice`

선택 열: `Description`, `CustomerID`, `Country`

- 단위/통화는 입력 파일에 맞게 사용자가 확인해야 합니다. 이 UI는 영국 데이터 사례에 맞춰 GBP(£)로 표시합니다.
- API 키 불필요. 로컬 웹 서버에서만 계산하며 회사 파일을 자체적으로 외부에 전송하지 않습니다.
- **실제 회사의 비공개 데이터/고객 개인정보는 절대 무단 업로드하지 마세요.**
- UCI와 다른 기업 스키마를 그대로 업로드하면 정상 작동하지 않습니다. 그때는 변환/매핑 처리가 추가로 필요합니다.

## 검증 방법

```bash
python -m pytest -q
python -m py_compile app.py analytics.py reporting.py scripts/download_uci.py
```

## 기술 구조

```text
Browser Streamlit UI (app.py)
    ├── data/raw: UCI 원본 ZIP (다운로드 후 로컬만 저장)
    ├── analytics.py: 정제·품질·KPI·SQL·RFM
    ├── reporting.py: HTML 보고서
    └── CSV 다운로드: 정제 거래·고객 분석
```

- **실제 데이터 다운로드 첫 실행은 인터넷이 필요합니다.** 다운로드가 불가능하면 공식 UCI 사이트에서 ZIP을 수동으로 내려받아 `data/online_retail_original.zip`으로 넣으세요.
- 원본 저장 시 SHA-256, 다운로드 시간, 원본 URL을 `data/provenance.json`에 기록합니다.
- 작업을 끝낼 때 Terminal에서 `Control + C`를 누르세요.

## 데이터 분석가 면접에서 설명할 포인트

"영국 소매기업의 실제 54만여 건 거래 라인으로 원본 데이터 품질을 확인하고, 취소/수량/단가 기준을 명시해 양수 판매액을 산출했습니다. pandas/SQLite로 월별·상품별 KPI를 분석하고 규칙기반 RFM 고객 그룹을 만들었으며, 결론과 한계를 HTML 보고서로 정리했습니다."

**단, 실제 데이터 다운로드와 분석을 직접 수행한 다음 위와 같이 설명하세요.**

### 대안: 빠른 실행 스크립트

압축 해제 후 아래와 같이 한 번에 실행할 수도 있습니다.

```bash
cd ~/Projects/Retail_Analytics_Lab
bash start_mac.command
```

`EXAMPLE_REPORT_SYNTHETIC.html`은 설치 전 결과 형식을 미리 볼 수 있는 **가상 데이터 예시 보고서**입니다. 실제 기업 분석 결과가 아니므로 포트폴리오의 실적처럼 제출하지 마세요.
