from decimal import Decimal
import pytest
from app.modules.m3_model.service import run
from app.modules.m3_model.rules import partition
from app.modules.m2_contract.service import run as contract
from app.errors import DomainError

def test_overlap_union(clean):assert run(clean)["partitions"][0]["downtime_minutes"]=="90.0"
def test_planned(clean):assert Decimal(run(clean)["partitions"][0]["planned"])==450
def test_priority(clean): # TRAP-19
    assert Decimal(run(clean)["partitions"][0]["causes"]["fault"])==60
    assert Decimal(run(clean)["partitions"][0]["causes"]["setup"])==30
def test_primary_sum_equals_downtime(clean): # TRAP-19
    item=run(clean)["partitions"][0]
    assert sum((Decimal(x) for x in item["causes"].values()),Decimal(0))==Decimal(item["downtime_minutes"])
def test_impact_keeps_each_cause(clean): # TRAP-19
    item=run(clean)["partitions"][0]
    assert Decimal(item["cause_impact"]["fault"])==60
    assert Decimal(item["cause_impact"]["setup"])==60
    assert Decimal(item["cause_overlap"]["setup"])==30
    assert Decimal(item["overlap_minutes"])==30
def test_impact_not_deducted_twice(clean): # TRAP-19
    result=run(clean);totals={x["cause"]:x for x in result["cause_totals"]};count=len(result["partitions"])
    assert result["attribution"]["primary_ok"] is True
    deducted=sum((Decimal(x["downtime_minutes"]) for x in result["partitions"]),Decimal(0))
    assert Decimal(result["attribution"]["primary_minutes"])==deducted
    assert Decimal(result["attribution"]["impact_minutes"])>Decimal(result["attribution"]["downtime_minutes"])
    assert Decimal(totals["fault"]["impact"])==Decimal(totals["fault"]["primary"])==60*count
    assert Decimal(totals["setup"]["impact"])==60*count and Decimal(totals["setup"]["primary"])==30*count
def test_record_order_keeps_original_causes(clean):
    row=contract(clean)["rows"][0];item=partition(row)
    assert sorted((x["cause"],x["minutes"]) for x in item["stops"])==[("fault","60.0"),("setup","60.0")]
    assert sorted(x["interval"] for x in item["stops"])==sorted(x["interval"] for x in row["downtime"])
def test_rerun_same_attribution(clean):
    first=run(clean);second=run(clean)
    assert first["attribution"]==second["attribution"]
    assert first["cause_rows"]==second["cause_rows"]
def test_reverse_keeps_every_record(clean):
    row=contract(clean)["rows"][0];a=partition(row)
    row["downtime"]=[row["downtime"][1],row["downtime"][0]];b=partition(row)
    assert len(a["stops"])==len(b["stops"])==2
    assert a["causes"]==b["causes"] and a["cause_impact"]==b["cause_impact"]
    assert a["primary_cause"]==b["primary_cause"]=="fault"
def test_saved_record_keeps_attribution(dirty):
    from app.modules.m7_batches.service import run as batches
    first=batches(dirty);saved=__import__("app.store",fromlist=["fetch"]).fetch(first["manifest"]["run_id"])
    assert saved["cause_totals"]==first["cause_totals"]
    assert saved["cause_rows"]==first["cause_rows"]
def test_stop_excludes_rest_minutes(clean):
    row=contract(clean)["rows"][0]
    row["downtime"]=[{"interval":["2026-11-01T11:45:00+08:00","2026-11-01T12:15:00+08:00"],"cause":"fault"}]
    row["breaks"]=[["2026-11-01T12:00:00+08:00","2026-11-01T12:30:00+08:00"]]
    item=partition(row)
    assert Decimal(item["downtime_minutes"])==15
    assert item["stops"][0]["span_minutes"]=="30.0" and item["stops"][0]["minutes"]=="15.0"
def test_out_of_shift_stop_kept_with_zero(clean):
    row=contract(clean)["rows"][0]
    row["downtime"]=[{"interval":["2026-11-01T07:00:00+08:00","2026-11-01T08:30:00+08:00"],"cause":"safety"},{"interval":["2026-11-01T20:00:00+08:00","2026-11-01T21:00:00+08:00"],"cause":"fault"}]
    item=partition(row)
    assert len(item["stops"])==2
    assert sorted((x["cause"],x["minutes"]) for x in item["stops"])==[("fault","0"),("safety","30.0")]
    assert Decimal(item["downtime_minutes"])==30
def test_duplicate_same_cause_not_double_counted(clean):
    row=contract(clean)["rows"][0]
    row["downtime"]=[{"interval":["2026-11-01T09:00:00+08:00","2026-11-01T10:00:00+08:00"],"cause":"fault"}]*2
    item=partition(row)
    assert len(item["stops"])==2
    assert Decimal(item["causes"]["fault"])==60 and Decimal(item["cause_impact"]["fault"])==60
    assert Decimal(item["overlap_minutes"])==0
def test_same_cause_overlap_union(clean):
    row=contract(clean)["rows"][0]
    row["downtime"]=[{"interval":["2026-11-01T09:00:00+08:00","2026-11-01T10:00:00+08:00"],"cause":"fault"},{"interval":["2026-11-01T09:30:00+08:00","2026-11-01T10:30:00+08:00"],"cause":"fault"}]
    item=partition(row)
    assert Decimal(item["downtime_minutes"])==90
    assert Decimal(item["causes"]["fault"])==90 and Decimal(item["cause_impact"]["fault"])==90
    assert Decimal(item["overlap_minutes"])==0
def test_full_overlap_not_double_deducted(clean):
    row=contract(clean)["rows"][0]
    row["downtime"]=[{"interval":["2026-11-01T09:00:00+08:00","2026-11-01T10:00:00+08:00"],"cause":"safety"},{"interval":["2026-11-01T09:00:00+08:00","2026-11-01T10:00:00+08:00"],"cause":"fault"}]
    item=partition(row)
    assert Decimal(item["downtime_minutes"])==60
    assert Decimal(item["causes"]["safety"])==60 and Decimal(item["causes"]["fault"])==0
    assert Decimal(item["cause_impact"]["fault"])==60
    assert Decimal(item["overlap_minutes"])==60
def test_order_invariant(clean):
    row=contract(clean)["rows"][0];a=partition(row);row["downtime"].reverse();assert partition(row)==a
def test_invalid_cause(dirty):assert "CAUSE" in [x["code"] for x in run(dirty)["quarantine"]]
def test_half_open(clean): # TRAP-23
    segments=run(clean)["partitions"][0]["segments"];assert sum((Decimal(x["minutes"]) for x in segments),Decimal(0))==480
def test_break_overlap_once(clean):
    row=contract(clean)["rows"][0];row["breaks"]*=2;assert Decimal(partition(row)["break_minutes"])==30

def test_cross_midnight(clean):
    row=contract(clean)["rows"][0]
    row.update(start="2026-11-01T22:00:00+08:00",end="2026-11-02T06:00:00+08:00",breaks=[["2026-11-02T02:00:00+08:00","2026-11-02T02:30:00+08:00"]],downtime=[{"interval":["2026-11-01T23:00:00+08:00","2026-11-02T01:00:00+08:00"],"cause":"fault"}])
    result=partition(row)
    assert Decimal(result["planned"])==450
    assert Decimal(result["downtime_minutes"])==120
    assert Decimal(result["runtime"])==330
