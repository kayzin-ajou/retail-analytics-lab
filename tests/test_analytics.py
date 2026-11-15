import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analytics import (make_demo_data, harmonize, clean_transactions, metrics,
    audit, rfm, monthly, products, run_example_sql, build_suggestions)
from reporting import export_html


def test_demo_is_reproducible():
    x, y = make_demo_data(), make_demo_data()
    assert x.equals(y) and len(x) > 500


def test_cancellation_and_nonpositive_removed():
    x = make_demo_data()
    clean, stages = clean_transactions(x, True)
    assert len(clean) + stages['제외 행 수'].sum() == len(x)
    assert clean.Quantity.gt(0).all() and clean.UnitPrice.gt(0).all()
    assert not clean.InvoiceNo.str.startswith('C').any()
    assert clean.Sales.gt(0).all()
    assert clean['InvoiceNo'].notna().all()


def test_manual_metric():
    import pandas as pd
    x = pd.DataFrame({'InvoiceNo':['1','1','2','C3'], 'StockCode':['A','B','B','B'],
        'InvoiceDate':['2020-01-02']*4, 'Quantity':[2,3,4,-1],
        'UnitPrice':[10,5,3,3], 'CustomerID':['10',None,'20','20'], 'Description':['A','B','B','B'], 'Country':['UK']*4})
    cleaned, _ = clean_transactions(x)
    k = metrics(cleaned)
    assert k['매출액_양수거래'] == 47
    assert k['주문수'] == 2 and k['주문당평균금액'] == 23.5
    assert k['식별가능고객수'] == 2
    assert audit(x)['취소코드(C) 행'] == 1


def test_sql_matches_pandas_monthly():
    x,_ = clean_transactions(make_demo_data())
    query, table = run_example_sql(x, '월별 매출')
    assert 'GROUP BY' in query
    assert round(table.Sales.sum(), 2) == round(metrics(x)['매출액_양수거래'], 2)
    assert len(rfm(x)) > 0
    assert len(monthly(x)) >= 10
    assert len(products(x)) == 5
    assert len(build_suggestions(x)) >= 2


def test_export():
    x = make_demo_data()
    cleaned, log = clean_transactions(x)
    html = export_html(cleaned, audit(x), log, '가상 학습용 데이터')
    assert '실무형 온라인 판매 데이터 분석 보고서' in html
    assert '가상 학습용 데이터' in html
    assert '<html lang="ko">' in html


def test_load_uci_zip_from_excel(tmp_path):
    import zipfile
    from analytics import load_uci_zip
    source = make_demo_data(n=20)
    buf = tmp_path / 'online_retail.xlsx'
    source.to_excel(buf, index=False)
    archive = tmp_path / 'real_source_shape.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.write(buf, 'Online Retail.xlsx')
    result = load_uci_zip(archive)
    assert len(result) == 20  # twenty synthetic rows, no duplicated append in small fixture
    assert {'InvoiceNo','StockCode','Quantity','UnitPrice'}.issubset(result.columns)
