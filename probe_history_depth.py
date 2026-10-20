"""Probe historical depth of free endpoints, no admission or trading claims."""
import json
from collect import fetch_index, fetch_tencent, INDEXES
END="2026-10-19"
def main():
    out={"schema":"LONG_HISTORY_SOURCE_FEASIBILITY_V1","candidate_only":True,"admitted":False,"results":{}}
    for source in ("eastmoney","tencent"):
        report={}
        for idx,secid in INDEXES.items():
            try:
                series=fetch_index(secid,"2018-01-01",END) if source=="eastmoney" else fetch_tencent("sh"+idx[:6],"2018-01-01",END)
                report[idx]={"count":len(series),"earliest":series[0][0],"latest":series[-1][0]}
            except Exception as e:
                report[idx]={"error_type":type(e).__name__,"error":str(e)[:180]}
        out["results"][source]=report
    print(json.dumps(out))
    with open("history_depth_probe.json","w") as f:json.dump(out,f,indent=2)
if __name__=="__main__":main()
