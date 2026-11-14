"""Generate the local ShopPulse PBIP from verified BigQuery exports and results.

Run export_dashboard_data.py first. Open dashboard/ShopPulse.pbip in Desktop,
refresh, then save a PBIX and export PDF. Generated files are not proof of a
successful Desktop render; see dashboard/BUILD_STATUS.md.
"""
import csv, datetime, json, shutil, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / 'dashboard'
DATA = DASH / 'data'
REPORT = DASH / 'ShopPulse.Report'
MODEL = DASH / 'ShopPulse.SemanticModel'
MEASURE_TABLE = 'Orders'


def uid():
    return str(uuid.uuid4())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def csvfile(name, rows):
    with (DATA / name).open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def field(table, column, measure=False, aggregate=None):
    expr = {'Measure' if measure else 'Column': {'Expression': {'SourceRef': {'Entity': table}}, 'Property': column}}
    ref = f'{table}.{column}'
    if aggregate is not None:
        expr = {'Aggregation': {'Expression': expr, 'Function': aggregate}}
        ref = f'Sum({ref})'
    return {'field': expr, 'queryRef': ref, 'nativeQueryRef': column}


def lit(value):
    return {'expr': {'Literal': {'Value': value}}}


def visual(page, name, kind, title, x, y, w, h, roles, objects=None):
    value = {'$schema': 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json',
             'name': name, 'position': {'x': x, 'y': y, 'z': 0, 'width': w, 'height': h, 'tabOrder': x + y},
             'visual': {'visualType': kind, 'query': {'queryState': {k: {'projections': v} for k, v in roles.items()}},
                        'drillFilterOtherVisuals': True,
                        'visualContainerObjects': {'title': [{'properties': {'show': lit('true'), 'text': lit("'" + title.replace("'", "''") + "'"), 'fontSize': lit('12D'), 'fontColor': {'solid': {'color': lit("'#19324F'")}}}}],
                                                   'background': [{'properties': {'show': lit('true'), 'color': {'solid': {'color': lit("'#FFFFFF'")}}, 'transparency': lit('0D')}}]}}}
    if objects:
        value['visual']['objects'] = objects
    save(REPORT / 'definition' / 'pages' / page / 'visuals' / name / 'visual.json', value)


def textbox(page, name, text, x, y, w, h, size='12pt'):
    value = {'$schema': 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json', 'name': name,
             'position': {'x': x, 'y': y, 'z': 0, 'width': w, 'height': h, 'tabOrder': x + y},
             'visual': {'visualType': 'textbox', 'objects': {'general': [{'properties': {'paragraphs': [{'textRuns': [{'value': text, 'textStyle': {'fontSize': size, 'color': '#19324F'}}]}]}}]}}}
    save(REPORT / 'definition' / 'pages' / page / 'visuals' / name / 'visual.json', value)


def card(page, name, title, measure, x, y, w=270, h=125):
    visual(page, name, 'card', title, x, y, w, h, {'Values': [field(MEASURE_TABLE, measure, True)]},
           {'labels': [{'properties': {'labelDisplayUnits': lit('1D'), 'fontSize': lit('25D')}}],
            'categoryLabels': [{'properties': {'show': lit('false')}}]})


def chart(page, name, title, table, category, measure, x, y, w, h, kind='clusteredBarChart'):
    visual(page, name, kind, title, x, y, w, h, {'Category': [field(table, category)], 'Y': [field(MEASURE_TABLE, measure, True)]})


def table(name, filename, schema, filter_window=False):
    mtypes = {'STRING': ('string', 'type text'), 'INTEGER': ('int64', 'Int64.Type'), 'INT64': ('int64', 'Int64.Type'),
              'FLOAT': ('double', 'type number'), 'FLOAT64': ('double', 'type number'), 'NUMERIC': ('decimal', 'type number'),
              'BOOLEAN': ('boolean', 'type logical'), 'BOOL': ('boolean', 'type logical'), 'DATE': ('dateTime', 'type date'),
              'DATETIME': ('dateTime', 'type datetime'), 'TIMESTAMP': ('dateTime', 'type datetime')}
    columns, transforms = [], []
    for item in schema:
        col, typ = item['name'], item['type']
        datatype, mtype = mtypes[typ]
        value = {'name': col, 'dataType': datatype, 'sourceColumn': col, 'summarizeBy': 'none', 'lineageTag': uid()}
        if datatype == 'dateTime':
            value['formatString'] = 'yyyy-MM-dd'
        columns.append(value)
        transforms.append('{"' + col + '", ' + mtype + '}')
    expr = ['let', f'    Source = Csv.Document(File.Contents(DataFolder & "{filename}"),[Delimiter=",",Encoding=65001,QuoteStyle=QuoteStyle.Csv]),',
            '    Headers = Table.PromoteHeaders(Source,[PromoteAllScalars=true]),', '    Typed = Table.TransformColumnTypes(Headers,{' + ','.join(transforms) + '},"en-US")']
    last = 'Typed'
    if name in ('Orders', 'Reviews'):
        expr[-1] += ','
        expr.append('    WithDate = Table.AddColumn(Typed,"purchase_date",each Date.From([purchased_at]),type date)')
        columns.append({'name': 'purchase_date', 'dataType': 'dateTime', 'sourceColumn': 'purchase_date', 'formatString': 'yyyy-MM-dd', 'summarizeBy': 'none', 'lineageTag': uid()})
        last = 'WithDate'
    if filter_window:
        expr[-1] += ','
        expr.append('    Window = Table.SelectRows(WithDate, each [purchase_date] >= #date(2017,1,1) and [purchase_date] <= #date(2018,8,31))')
        last = 'Window'
    expr.extend(['in', '    ' + last])
    return {'name': name, 'lineageTag': uid(), 'columns': columns, 'partitions': [{'name': name, 'mode': 'import', 'source': {'type': 'm', 'expression': expr}}]}


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((DATA / 'export_manifest.json').read_text())
    checks = {'fct_orders': 99441}
    for name, expected in checks.items():
        if manifest[name]['rows'] != expected:
            raise ValueError(f'{name} export count changed')
    with (DATA / 'fct_orders.csv').open(encoding='utf-8') as stream:
        orders = list(csv.DictReader(stream))
    if len(orders) != 99441 or len({r['order_id'] for r in orders}) != 99441 or any(len(r['order_id']) != 32 for r in orders):
        raise ValueError('Order export is incomplete or has duplicate ids')
    window = [r for r in orders if '2017-01-01' <= r['purchased_at'][:10] <= '2018-08-31']
    if len(window) != 99092 or sum(r['reached_delivered'] == 'true' for r in window) != 96211:
        raise ValueError('Order-window or delivered-count reconciliation failed')
    review_schema = [{'name': c, 'type': t} for c, t in [('order_id', 'STRING'), ('customer_state', 'STRING'), ('purchased_at', 'DATETIME'), ('is_late', 'BOOLEAN'), ('days_vs_estimate', 'INTEGER'), ('review_score', 'INTEGER'), ('is_low_review', 'BOOLEAN'), ('item_value', 'NUMERIC')]]
    reviews = []
    for r in window:
        if r['reached_delivered'] == 'true' and r['is_late'] and r['review_score']:
            reviews.append({f['name']: ('true' if int(r['review_score']) <= 2 else 'false') if f['name'] == 'is_low_review' else r[f['name']] for f in review_schema})
    if len(reviews) != 95560:
        raise ValueError('Review-population reconciliation failed')
    for flag, expected_n, expected_rate in [('true', 6378, 0.6240200689871434), ('false', 89182, 0.09248503061155838)]:
        group = [r for r in reviews if r['is_late'] == flag]
        rate = sum(r['is_low_review'] == 'true' for r in group) / len(group)
        if len(group) != expected_n or abs(rate - expected_rate) > 1e-12:
            raise ValueError('Review-group reconciliation failed')
    csvfile('mart_delivery_reviews.csv', reviews)
    manifest['mart_delivery_reviews'] = {'schema': review_schema, 'rows': len(reviews)}
    shutil.copyfile(ROOT / 'results' / '03b_cohort_retention.csv', DATA / 'mart_cohort_retention.csv')
    manifest['mart_cohort_retention'] = {'rows': 210, 'schema': [{'name': c, 'type': t} for c, t in [('cohort_month', 'DATE'), ('cohort_size', 'INTEGER'), ('month_offset', 'INTEGER'), ('retained_customers', 'INTEGER'), ('retention_pct', 'FLOAT')]]}
    shutil.copyfile(ROOT / 'results' / '03c_rfm_segments.csv', DATA / 'rfm_segments.csv')
    for filename in ['02b_stage_durations.csv', '03a_repeat_rate.csv', '04_dose_response.csv']:
        shutil.copyfile(ROOT / 'results' / filename, DATA / filename)
    summary = json.loads((ROOT / 'results' / '04_summary.json').read_text())
    rows = list(csv.DictReader((DATA / '02b_stage_durations.csv').open(encoding='utf-8')))
    for r in rows:
        r['median_days'] = float(r['median']) / (24 if r['step'] == '1' else 1)
        r['p90_days'] = float(r['p90']) / (24 if r['step'] == '1' else 1)
    csvfile('durations.csv', rows)
    csvfile('stages.csv', [{'step': i, 'stage': s} for i, s in enumerate(['Placed', 'Approved', 'Handed to carrier', 'Delivered'], 1)])
    csvfile('repeat_rates.csv', [{'group': 'On-time', 'rate': summary['repeat_test']['repeat_rate_ontime']}, {'group': 'Late', 'rate': summary['repeat_test']['repeat_rate_late']}])
    csvfile('late_status.csv', [{'label': 'On-time', 'is_late': 'false'}, {'label': 'Late', 'is_late': 'true'}])
    csvfile('gap_assumption.csv', [{'gap_pp': x / 20} for x in range(41)])
    csvfile('customers_assumption.csv', [{'customers': x} for x in sorted(set(range(0, 5001, 100)) | {2668})])
    csvfile('dates.csv', [{'Date': (datetime.date(2017, 1, 1) + datetime.timedelta(days=i)).isoformat(), 'Month': (datetime.date(2017, 1, 1) + datetime.timedelta(days=i)).replace(day=1).isoformat()} for i in range(608)])
    csvfile('states.csv', [{'state': s} for s in sorted({r['customer_state'] for r in window})])
    specs = [('Orders', 'fct_orders'), ('Reviews', 'mart_delivery_reviews'), ('Cohorts', 'mart_cohort_retention')]
    tables = [table(n, s + '.csv', manifest[s]['schema'], n == 'Orders') for n, s in specs]
    small = [
        ('RFM', 'rfm_segments.csv', [('segment', 'STRING'), ('customers', 'INTEGER'), ('pct_customers', 'FLOAT'), ('revenue_brl', 'FLOAT'), ('pct_revenue', 'FLOAT'), ('avg_spend_brl', 'FLOAT'), ('avg_recency_days', 'FLOAT')]),
        ('Stages', 'stages.csv', [('step', 'INTEGER'), ('stage', 'STRING')]),
        ('Durations', 'durations.csv', [('step', 'INTEGER'), ('stage', 'STRING'), ('median', 'FLOAT'), ('p90', 'FLOAT'), ('median_days', 'FLOAT'), ('p90_days', 'FLOAT')]),
        ('RepeatSnapshot', '03a_repeat_rate.csv', [('customers', 'INTEGER'), ('repeat_customers', 'INTEGER'), ('repeat_customer_pct', 'FLOAT'), ('avg_orders_per_customer', 'FLOAT'), ('max_orders', 'INTEGER')]),
        ('Dose', '04_dose_response.csv', [('bucket', 'STRING'), ('people', 'INTEGER'), ('repeat_rate', 'FLOAT'), ('orders', 'INTEGER'), ('low_review_rate', 'FLOAT')]),
        ('RepeatRates', 'repeat_rates.csv', [('group', 'STRING'), ('rate', 'FLOAT')]),
        ('LateStatus', 'late_status.csv', [('label', 'STRING'), ('is_late', 'BOOLEAN')]),
        ('GapAssumption', 'gap_assumption.csv', [('gap_pp', 'FLOAT')]),
        ('CustomersAssumption', 'customers_assumption.csv', [('customers', 'INTEGER')]),
        ('Dates', 'dates.csv', [('Date', 'DATE'), ('Month', 'DATE')]), ('States', 'states.csv', [('state', 'STRING')])]
    tables += [table(n, filename, [{'name': c, 'type': t} for c, t in schema]) for n, filename, schema in small]
    measures = {
        'Orders': ('COUNTROWS(Orders)', '#,##0'),
        'Delivered Orders': ('CALCULATE([Orders],Orders[reached_delivered]=TRUE())', '#,##0'),
        'Delivered %': ('DIVIDE([Delivered Orders],[Orders])', '0.00%'),
        'Revenue R$': ('CALCULATE(SUM(Orders[item_value]),Orders[reached_delivered]=TRUE())', '"R$ "#,##0.00'),
        'AOV R$': ('DIVIDE([Revenue R$],[Delivered Orders])', '"R$ "#,##0.00'),
        'On-time %': ('DIVIDE(CALCULATE([Orders],Orders[is_late]=FALSE(),NOT ISBLANK(Orders[is_late])),CALCULATE([Orders],NOT ISBLANK(Orders[is_late])))', '0.00%'),
        'Average Review': ('AVERAGE(Orders[review_score])', '0.00'),
        'Funnel Orders': ('SWITCH(SELECTEDVALUE(Stages[step]),1,[Orders],2,CALCULATE([Orders],Orders[reached_approved]=TRUE()),3,CALCULATE([Orders],Orders[reached_carrier]=TRUE()),4,[Delivered Orders])', '#,##0'),
        'Median Days': ('MAX(Durations[median_days])', '0.00'), 'P90 Days': ('MAX(Durations[p90_days])', '0.00'),
        'Repeat Customers % snapshot': ('MAX(RepeatSnapshot[repeat_customer_pct])/100', '0.00%'),
        'RFM Customers': ('SUM(RFM[customers])', '#,##0'), 'RFM Revenue R$': ('SUM(RFM[revenue_brl])', '"R$ "#,##0'),
        'Cohort Retention %': ('MAX(Cohorts[retention_pct])/100', '0.00%'),
        'Low Review %': ('VAR lateFlag=SELECTEDVALUE(LateStatus[is_late]) RETURN DIVIDE(CALCULATE(COUNTROWS(Reviews),Reviews[is_low_review]=TRUE(),Reviews[is_late]=lateFlag),CALCULATE(COUNTROWS(Reviews),Reviews[is_late]=lateFlag))', '0.0%'),
        'Repeat Rate fixed cohort': ('MAX(RepeatRates[rate])', '0.00%'),
        'Dose Low Review % fixed': ('MAX(Dose[low_review_rate])', '0.0%'),
        'Dose Repeat % fixed': ('MAX(Dose[repeat_rate])', '0.00%'),
        'Gap pp fixed cohort': (str(summary['repeat_test']['gap_pp']), '0.00" pp"'),
        'Illustrative Scenario R$': (f'VAR people=IF(ISFILTERED(CustomersAssumption[customers]),MAX(CustomersAssumption[customers]),2668) VAR gap=IF(ISFILTERED(GapAssumption[gap_pp]),MAX(GapAssumption[gap_pp]),{summary["repeat_test"]["gap_pp"]}) RETURN people*gap/100*{summary["revenue_at_stake_brl"]["avg_repeat_order_value"]}', '"R$ "#,##0.00')}
    tables[0]['measures'] = [{'name': name, 'expression': expr, 'formatString': fmt, 'lineageTag': uid()} for name, (expr, fmt) in measures.items()]
    rels = []
    for fact in ['Orders', 'Reviews']:
        for col, dim, dimcol in [('purchase_date', 'Dates', 'Date'), ('customer_state', 'States', 'state')]:
            rels.append({'name': uid(), 'fromTable': fact, 'fromColumn': col, 'toTable': dim, 'toColumn': dimcol})
    model = {'compatibilityLevel': 1601, 'model': {'culture': 'en-US', 'sourceQueryCulture': 'en-US', 'defaultPowerBIDataSourceVersion': 'powerBI_V3',
             'annotations': [{'name': '__PBI_TimeIntelligenceEnabled', 'value': '0'}, {'name': 'PBI_QueryOrder', 'value': json.dumps(['DataFolder'] + [t['name'] for t in tables])}],
             'dataAccessOptions': {'legacyRedirects': True, 'returnErrorValuesAsNull': True},
             'expressions': [{'name': 'DataFolder', 'kind': 'm', 'expression': json.dumps(DATA.as_posix() + '/') + ' meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'}],
             'tables': tables, 'relationships': rels}}
    save(MODEL / 'model.bim', model)
    save(MODEL / 'definition.pbism', {'version': '1.0', 'settings': {}})
    save(DASH / 'ShopPulse.pbip', {'version': '1.0', 'artifacts': [{'report': {'path': 'ShopPulse.Report'}}], 'settings': {'enableAutoRecovery': True}})
    save(REPORT / 'definition.pbir', {'version': '4.0', 'datasetReference': {'byPath': {'path': '../ShopPulse.SemanticModel'}}})
    save(REPORT / 'definition' / 'version.json', {'$schema': 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json', 'version': '2.0.0'})
    save(REPORT / 'definition' / 'report.json', {'$schema': 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.0.0/schema.json', 'themeCollection': {}, 'settings': {'useEnhancedTooltips': False}})
    pages = [('overview', 'Overview'), ('fulfilment', 'Fulfilment funnel'), ('retention', 'Retention and segments'), ('impact', 'Late delivery impact')]
    save(REPORT / 'definition' / 'pages' / 'pages.json', {'$schema': 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json', 'pageOrder': [p for p, _ in pages], 'activePageName': 'overview'})
    for page, title in pages:
        save(REPORT / 'definition' / 'pages' / page / 'page.json', {'$schema': 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json', 'name': page, 'displayName': title, 'displayOption': 'FitToPage', 'width': 1440, 'height': 1000})
        textbox(page, 'heading', 'ShopPulse | ' + title + ' | Real Olist data', 25, 12, 1380, 42, '20pt')
    for page in ['overview', 'fulfilment', 'impact']:
        visual(page, 'month', 'slicer', 'Purchase month (descriptive visuals)', 25, 65, 650, 90, {'Values': [field('Dates', 'Month')]})
        visual(page, 'state', 'slicer', 'Customer state (descriptive visuals)', 720, 65, 690, 90, {'Values': [field('States', 'state')]})
        for name in ['month', 'state']:
            p = REPORT / 'definition' / 'pages' / page / 'visuals' / name / 'visual.json'
            j = json.loads(p.read_text(encoding='utf-8'))
            j['visual']['syncGroup'] = {'groupName': 'ShopPulse_' + name, 'fieldChanges': True, 'filterChanges': True}
            save(p, j)
    for i, (title, measure) in enumerate([('Placed orders', 'Orders'), ('Delivered revenue R$', 'Revenue R$'), ('Delivered AOV R$', 'AOV R$'), ('On-time delivered', 'On-time %'), ('Average review', 'Average Review')]):
        card('overview', 'kpi' + str(i), title, measure, 20 + i * 284, 170, 276)
    chart('overview', 'revenue_trend', 'Delivered item revenue by purchase month (R$; freight excluded)', 'Dates', 'Month', 'Revenue R$', 25, 320, 1380, 310, 'lineChart')
    chart('overview', 'states', 'Orders by customer state', 'States', 'state', 'Orders', 25, 650, 1380, 285)
    textbox('overview', 'scope', 'Window: purchases Jan 2017-Aug 2018. Revenue = delivered item prices, excluding freight. Late = delivery on a later calendar day than the estimate. Descriptive associations, not causal effects.', 25, 947, 1380, 48)
    card('fulfilment', 'delivered', 'Delivered share of placed orders', 'Delivered %', 25, 170, 400)
    chart('fulfilment', 'funnel', 'Fulfilment funnel (orders, not web sessions)', 'Stages', 'stage', 'Funnel Orders', 25, 320, 650, 330, 'funnel')
    visual('fulfilment', 'durations', 'clusteredBarChart', 'Saved global stage durations (days; not filtered)', 720, 320, 690, 330,
           {'Category': [field('Durations', 'stage')], 'Y': [field(MEASURE_TABLE, 'Median Days', True), field(MEASURE_TABLE, 'P90 Days', True)]})
    chart('fulfilment', 'delivered_trend', 'Delivered share by purchase month', 'Dates', 'Month', 'Delivered %', 25, 680, 1380, 250, 'lineChart')
    textbox('fulfilment', 'scope', 'Stage flags are cumulative. Durations use the saved BigQuery approximate median/p90 results for delivered orders; they are fixed global benchmarks. Purchase-to-approval hours are converted to days.', 25, 947, 1380, 48)
    card('retention', 'repeat', 'Ever reordered: fixed snapshot through Aug 2018', 'Repeat Customers % snapshot', 25, 65, 650)
    textbox('retention', 'scope', 'Snapshot: 94,990 people with a valid purchase through Aug 2018, including prior 2016 purchases. Valid excludes canceled/unavailable. This page is intentionally independent of purchase-month/state filters.', 720, 75, 680, 100)
    visual('retention', 'cohort', 'pivotTable', 'Monthly cohort retention (unobserved future months stay blank)', 25, 220, 1380, 360,
           {'Rows': [field('Cohorts', 'cohort_month')], 'Columns': [field('Cohorts', 'month_offset')], 'Values': [field(MEASURE_TABLE, 'Cohort Retention %', True)]})
    chart('retention', 'rfm_customers', 'Customer count by RFM segment (fixed snapshot)', 'RFM', 'segment', 'RFM Customers', 25, 620, 650, 315)
    chart('retention', 'rfm_revenue', 'Historical valid-order item value by RFM segment (R$)', 'RFM', 'segment', 'RFM Revenue R$', 720, 620, 690, 315)
    textbox('retention', 'note', 'Customer identity uses customer_unique_id. R/M quintiles split ties deterministically by that id; frequency groups are 1, 2, 3+. Cohort retention is rounded to two percentage decimals in the SQL mart.', 25, 947, 1380, 48)
    chart('impact', 'reviews', '1-2 star reviews (order-level; follows month/state filters)', 'LateStatus', 'label', 'Low Review %', 25, 170, 650, 245, 'clusteredColumnChart')
    chart('impact', 'repeat', '180-day repeat rate: FIXED eligible people (n=52,310)', 'RepeatRates', 'group', 'Repeat Rate fixed cohort', 720, 170, 690, 245, 'clusteredColumnChart')
    textbox('impact', 'inference', 'Fixed repeat-purchase analysis: on-time 1.87% vs late 1.35%; on-time minus late = 0.52 pp; 95% CI -0.01 to 0.91 pp; p=0.053, NOT significant at 5%. One first delivered order per person, full 180-day follow-up measured after delivery. Observational, not causal.', 25, 430, 1380, 80)
    chart('impact', 'dose_reviews', 'Fixed global dose-response: low reviews (orders)', 'Dose', 'bucket', 'Dose Low Review % fixed', 25, 530, 650, 230, 'clusteredColumnChart')
    chart('impact', 'dose_repeat', 'Fixed global dose-response: repeat purchase (people)', 'Dose', 'bucket', 'Dose Repeat % fixed', 720, 530, 690, 230, 'clusteredColumnChart')
    visual('impact', 'scenario_gap', 'slicer', 'Scenario gap pp (upper selected value)', 25, 785, 400, 100, {'Values': [field('GapAssumption', 'gap_pp')]})
    visual('impact', 'scenario_people', 'slicer', 'Scenario late customers (upper selected value)', 450, 785, 450, 100, {'Values': [field('CustomersAssumption', 'customers')]})
    card('impact', 'scenario', 'Illustrative revenue scenario R$ (not a forecast)', 'Illustrative Scenario R$', 930, 785, 480, 105)
    textbox('impact', 'scope', 'Scenario only: causal assumption is unsupported. Defaults: 2,668 people x 0.516 pp x R$120.40 = R$1,658 (CI-derived range R$0-2,919). When a control is filtered, its highest selected value is used. This is not validated revenue loss. Scenario controls and fixed tests ignore descriptive slicers.', 25, 910, 1380, 80)
    print('Generated ShopPulse.pbip: 4 pages,', len(tables), 'tables,', len(measures), 'measures. Orders reconciled: 99,092 placed / 96,211 delivered.')


if __name__ == '__main__':
    main()
