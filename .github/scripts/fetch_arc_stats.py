#!/usr/bin/env python3
"""GA4 Data API から、裏事件簿の到達（arc_milestone）と回答（arc_answer）を集計し、arc-stats.json を作る。
case_stats（fetch_case_stats.py）とは別ファイル・別ステップ。失敗しても case-stats.json には影響しない。
環境変数: GA4_PROPERTY_ID, GA4_SERVICE_ACCOUNT_JSON（fetch_case_stats.py と同じ）
任意: START_DATE（既定 2020-01-01）, OUT（既定 arc-stats.json）
arc_id の意味：
  arc_milestone … board（捜査ボードに資料がある状態で開いた）／linked-Gx（グループの資料が1つの枠にそろった）／
                  lv2-Gx（追加推理を解決）／lv3-open（封印カードが開いた）／lv3-linked（CASE 000の5枚がつながった）／lv3-solved（CASE 000を解決）
  arc_answer    … L2-Gx（追加推理の最初の回答）／L3-000（CASE 000の最初の回答）。is_correct が正解(1)／不正解(0)
どちらも端末ごとに1回。選んだ選択肢は送られていません。"""
import json, os, sys, datetime

def compute(rows, now_iso):
    """rows: [{event, arc_id, path, n, users, correct}] → dict"""
    ms, ans = {}, {}
    for r in rows:
        lang = "en" if str(r["path"]).startswith("/en/") else "ja"
        aid = str(r["arc_id"]).strip()
        if not aid or len(aid) > 40:
            continue
        if r["event"] == "arc_milestone":
            d = ms.setdefault(aid, {"ja": 0, "en": 0, "total": 0})
            d[lang] += int(round(r["n"])); d["total"] += int(round(r["n"]))
        elif r["event"] == "arc_answer":
            d = ans.setdefault(aid, {"ja": {"n": 0, "correct": 0}, "en": {"n": 0, "correct": 0}, "n": 0, "correct": 0, "correct_rate": None})
            n, c = int(round(r["n"])), int(round(r["correct"]))
            d[lang]["n"] += n; d[lang]["correct"] += c; d["n"] += n; d["correct"] += c
    for d in ans.values():
        d["correct_rate"] = round(min(1.0, d["correct"] / d["n"]), 4) if d["n"] else None
    return {"version": 1, "updated": now_iso, "milestones": ms, "answers": ans}

def fetch_rows(prop, info, start):
    from google.oauth2 import service_account
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import (RunReportRequest, Dimension, Metric, DateRange,
                                                    FilterExpression, Filter)
    cred = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/analytics.readonly"])
    cli = BetaAnalyticsDataClient(credentials=cred)
    out, offset = [], 0
    while True:
        resp = cli.run_report(RunReportRequest(
            property=f"properties/{prop}",
            dimensions=[Dimension(name="eventName"), Dimension(name="customEvent:arc_id"), Dimension(name="pagePath")],
            metrics=[Metric(name="eventCount"), Metric(name="customEvent:is_correct")],
            date_ranges=[DateRange(start_date=start, end_date="today")],
            dimension_filter=FilterExpression(filter=Filter(
                field_name="eventName", in_list_filter=Filter.InListFilter(values=["arc_milestone", "arc_answer"]))),
            limit=10000, offset=offset))
        for row in resp.rows:
            d = [x.value for x in row.dimension_values]
            v = [float(x.value or 0) for x in row.metric_values]
            out.append({"event": d[0], "arc_id": d[1], "path": d[2], "n": v[0], "correct": v[1]})
        offset += len(resp.rows)
        if offset >= (resp.row_count or 0) or not resp.rows:
            break
    return out

def main():
    path = os.environ.get("OUT", "arc-stats.json")
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
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, path)
    print(f"到達 {len(data['milestones'])} 種、回答 {len(data['answers'])} 種を書き出しました。")
    return 0

if __name__ == "__main__":
    sys.exit(main())
