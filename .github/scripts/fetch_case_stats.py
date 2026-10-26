#!/usr/bin/env python3
"""GA4 Data API から case_answer イベントを問題別に集計し、case-stats.json を作る。
環境変数: GA4_PROPERTY_ID（数字）, GA4_SERVICE_ACCOUNT_JSON（サービスアカウント鍵のJSON全文）
任意: START_DATE（既定 2020-01-01。過去分の再集計に使う）, OUT（既定 case-stats.json）
失敗時は何も書かず exit 1（前回の正常なJSONが残る）。"""
import json, os, sys, datetime

MIN_N = 30
EVENT = "case_answer"

def compute(rows, now_iso):
    """rows: [{case_id, n, correct, hint, clean, secs}]  → 公開用 dict"""
    cases = {}
    for r in rows:
        cid = str(r["case_id"]).strip()
        if cid.isdigit():
            cid = cid.zfill(3)
        elif not (cid and len(cid) <= 20):
            continue
        n = int(round(r["n"]))
        if n < 1:
            continue
        e = {"n": n}
        if n >= MIN_N:
            e["correct_rate"] = round(min(1.0, r["correct"] / n), 4)
            nh = n - int(round(r["hint"]))          # ヒントなしで回答した件数
            e["nohint_n"] = max(nh, 0)
            if nh >= MIN_N:
                e["nohint_rate"] = round(min(1.0, r["clean"] / nh), 4)
            e["avg_seconds"] = round(r["secs"] / n, 1)
        cases[cid] = e
    return {"version": 1, "updated": now_iso, "min_n": MIN_N, "cases": cases}

def fetch_rows(prop, info, start):
    from google.oauth2 import service_account
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import (RunReportRequest, Dimension, Metric, DateRange,
                                                    FilterExpression, Filter)
    cred = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/analytics.readonly"])
    cli = BetaAnalyticsDataClient(credentials=cred)
    ms = ["eventCount", "customEvent:is_correct", "customEvent:hint_used",
          "customEvent:clean_correct", "customEvent:answer_seconds"]
    out, offset = [], 0
    while True:
        resp = cli.run_report(RunReportRequest(
            property=f"properties/{prop}",
            dimensions=[Dimension(name="customEvent:case_id")],
            metrics=[Metric(name=m) for m in ms],
            date_ranges=[DateRange(start_date=start, end_date="today")],
            dimension_filter=FilterExpression(filter=Filter(
                field_name="eventName", string_filter=Filter.StringFilter(value=EVENT))),
            limit=10000, offset=offset))
        for row in resp.rows:
            v = [float(x.value or 0) for x in row.metric_values]
            out.append({"case_id": row.dimension_values[0].value, "n": v[0], "correct": v[1],
                        "hint": v[2], "clean": v[3], "secs": v[4]})
        offset += len(resp.rows)
        if offset >= (resp.row_count or 0) or not resp.rows:
            break
    return out

def main():
    path = os.environ.get("OUT", "case-stats.json")
    try:
        prop = os.environ["GA4_PROPERTY_ID"].strip()
        info = json.loads(os.environ["GA4_SERVICE_ACCOUNT_JSON"])
        start = os.environ.get("START_DATE", "").strip() or "2020-01-01"
        rows = fetch_rows(prop, info, start)
    except Exception as e:
        print("GA4 取得に失敗しました。前回のJSONを維持します：", type(e).__name__, str(e)[:300], file=sys.stderr)
        return 1
    jst = datetime.timezone(datetime.timedelta(hours=9))
    data = compute(rows, datetime.datetime.now(jst).replace(microsecond=0).isoformat())
    if not data["cases"] and os.path.exists(path):
        try:
            if json.load(open(path, encoding="utf-8")).get("cases"):
                print("集計結果が空のため、前回のJSONを維持します。", file=sys.stderr)
                return 1
        except Exception:
            pass
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    os.replace(tmp, path)
    print(f"{len(data['cases'])} 件の問題を書き出しました。")
    return 0

if __name__ == "__main__":
    sys.exit(main())
