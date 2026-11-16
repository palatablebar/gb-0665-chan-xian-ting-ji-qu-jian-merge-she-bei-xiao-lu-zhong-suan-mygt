import json
from decimal import Decimal
from app.modules.m2_contract.service import parse_instant as instant
from app.errors import reject

PRIORITY={"safety":3,"fault":2,"setup":1}
CAUSES=tuple(PRIORITY)

def clip(pair,start,end):
    if not isinstance(pair,(list,tuple)) or len(pair)!=2:reject("INTERVAL","区间应为起止时间")
    left,right=instant(pair[0]),instant(pair[1])
    if right<=left:reject("INTERVAL","区间终点须晚于起点")
    return max(left,start),min(right,end)

def minutes(left,right):return Decimal(str((right-left).total_seconds()))/60

def rank(cause):return (-PRIORITY[cause],cause)

def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,default=str)

def merge(spans):
    merged=[]
    for left,right in sorted(spans):
        if merged and left<=merged[-1][1]:merged[-1]=(merged[-1][0],max(merged[-1][1],right))
        else:merged.append((left,right))
    return merged

def uncovered(span,cover):
    left,right=span;kept=[]
    for a,b in cover:
        if b<=left or a>=right:continue
        if a>left:kept.append((left,min(a,right)))
        left=max(left,b)
        if left>=right:break
    if left<right:kept.append((left,right))
    return sum((minutes(a,b) for a,b in kept),Decimal(0))

def partition(row):
    start,end=instant(row["start"]),instant(row["end"]);breaks=[];spans=[];records=[]
    for pair in row["breaks"]:
        a,b=clip(pair,start,end)
        if a<b:breaks.append((a,b))
    rest_union=merge(breaks)
    for stop in row["downtime"]:
        if not isinstance(stop,dict) or stop.get("cause") not in PRIORITY:reject("CAUSE","停机原因未知")
        a,b=clip(stop.get("interval"),start,end)
        records.append({"cause":stop["cause"],"interval":stop.get("interval"),"clipped":[a.isoformat(),b.isoformat()] if a<b else [],"span_minutes":str(minutes(a,b)) if a<b else "0","minutes":str(uncovered((a,b),rest_union)) if a<b else "0"})
        if a<b:spans.append((a,b,stop["cause"]))
    records.sort(key=lambda item:(canonical(item["interval"]),item["cause"]))
    bounds=sorted({start,end}|{x for pair in breaks for x in pair}|{x for a,b,_ in spans for x in (a,b)})
    planned=Decimal(0);down=Decimal(0);rest=Decimal(0)
    causes={k:Decimal(0) for k in CAUSES};impact={k:Decimal(0) for k in CAUSES};segments=[]
    for a,b in zip(bounds,bounds[1:]):
        duration=minutes(a,b);active=sorted({cause for l,r,cause in spans if l<=a and b<=r},key=rank)
        if any(l<=a and b<=r for l,r in breaks):rest+=duration;state="break";active=[]
        else:
            planned+=duration
            if active:
                cause=active[0];causes[cause]+=duration;down+=duration;state=cause
                for item in active:impact[item]+=duration
            else:state="running"
        segments.append({"start":a.isoformat(),"end":b.isoformat(),"minutes":str(duration),"state":state,"active":active})
    overlap=sum(impact.values(),Decimal(0))-down
    primary_cause=min((cause for cause in CAUSES if causes[cause]),key=rank,default=None)
    return {"record_id":row["record_id"],"line_id":row["line_id"],"line":row["line"],"scheduled":str(minutes(start,end)),"break_minutes":str(rest),"planned":str(planned),"downtime_minutes":str(down),"runtime":str(planned-down),"causes":{k:str(v) for k,v in causes.items()},"cause_impact":{k:str(v) for k,v in impact.items()},"cause_overlap":{k:str(impact[k]-causes[k]) for k in CAUSES},"primary_cause":primary_cause,"overlap_minutes":str(overlap),"segments":segments,"stops":records,"total":row["total"],"good":row["good"],"ideal_seconds":row["ideal_seconds"]}

def summarize(partitions):
    primary={k:Decimal(0) for k in CAUSES};impact={k:Decimal(0) for k in CAUSES}
    rows=[];down=Decimal(0)
    for item in partitions:
        down+=Decimal(item["downtime_minutes"])
        for cause in sorted({stop["cause"] for stop in item["stops"]},key=rank):
            rows.append({"record_id":item["record_id"],"line_id":item["line_id"],"cause":cause,"primary":item["causes"][cause],"impact":item["cause_impact"][cause],"overlap":item["cause_overlap"][cause]})
        for cause in CAUSES:
            primary[cause]+=Decimal(item["causes"][cause]);impact[cause]+=Decimal(item["cause_impact"][cause])
    totals=[{"cause":cause,"priority":PRIORITY[cause],"primary":str(primary[cause]),"impact":str(impact[cause]),"overlap":str(impact[cause]-primary[cause])} for cause in CAUSES]
    total_primary=sum(primary.values(),Decimal(0));total_impact=sum(impact.values(),Decimal(0))
    attribution={"basis":{"primary":"priority-exclusive","impact":"per-cause-union"},"downtime_minutes":str(down),"primary_minutes":str(total_primary),"impact_minutes":str(total_impact),"overlap_minutes":str(total_impact-down),"primary_ok":total_primary==down,"impact_ok":all(impact[cause]>=primary[cause] for cause in CAUSES)}
    return rows,totals,attribution
