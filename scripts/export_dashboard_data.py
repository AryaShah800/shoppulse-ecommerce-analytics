"""Read existing BigQuery marts into local, git-ignored Power BI CSVs.

No source tables or analysis results are changed. Uses Application Default
Credentials, the same connection as load_raw.py. DataFolder in the generated
Power BI model must point to dashboard/data/ on the machine opening it.
"""
import argparse, csv, datetime, json
from pathlib import Path
from google.cloud import bigquery


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--tables', nargs='+', default=['fct_orders', 'mart_cohort_retention', 'mart_rfm', 'mart_delivery_reviews', 'mart_delivery_repeat', 'mart_funnel_monthly'])
    parser.add_argument('--resume', action='store_true', help='Resume an interrupted export of an unchanged source table')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = root / 'dashboard' / 'data'
    out.mkdir(parents=True, exist_ok=True)
    client = bigquery.Client(project=args.project)
    manifest = {}
    for name in args.tables:
        table = client.get_table(f'{args.project}.shoppulse.{name}')
        fields = [f.name for f in table.schema]
        count = 0
        path = out / f'{name}.csv'
        existing = []
        if args.resume and path.exists():
            with path.open(encoding='utf-8', newline='') as previous:
                existing = list(csv.DictReader(previous))
            while existing and (None in existing[-1] or any(v is None for v in existing[-1].values()) or (name == 'fct_orders' and len(existing[-1]['order_id']) != 32)):
                existing.pop()
            count = len(existing)
            print(f'{name}: resuming at row {count}', flush=True)
        with path.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(fields)
            writer.writerows([[r[f] for f in fields] for r in existing])
            for row in client.list_rows(table, start_index=count, page_size=1000, timeout=30, retry=None):
                values = []
                for value in row:
                    if value is None:
                        values.append('')
                    elif isinstance(value, (datetime.datetime, datetime.date)):
                        values.append(value.isoformat())
                    elif isinstance(value, bool):
                        values.append(str(value).lower())
                    else:
                        values.append(str(value))
                writer.writerow(values)
                count += 1
                if count % 10000 == 0:
                    print(f'{name}: {count} rows downloaded', flush=True)
        if count != table.num_rows:
            raise ValueError(f'{name}: expected {table.num_rows}, exported {count}')
        manifest[name] = {'rows': count, 'source': table.full_table_id, 'schema': [{'name': f.name, 'type': f.field_type} for f in table.schema]}
        (out / 'export_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        print(f'{name}: {count} rows; {fields}', flush=True)
    (out / 'export_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
