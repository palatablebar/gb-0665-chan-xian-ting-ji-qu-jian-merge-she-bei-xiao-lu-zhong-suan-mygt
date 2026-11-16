from decimal import Decimal
from app.modules.m4_calculate.service import run
from app.modules.m4_calculate.rules import efficiency

def test_availability(clean):assert Decimal(run(clean)["results"][0]["availability"])==Decimal("0.8")
def test_performance(clean):assert Decimal(run(clean)["results"][0]["performance"])==Decimal(5)/6
def test_quality(clean):assert Decimal(run(clean)["results"][0]["quality"])==Decimal("0.95")
def test_oee(clean): # TRAP-10
    assert Decimal(run(clean)["results"][0]["oee"])==Decimal(285)/450
def test_no_schedule(clean):
    item=run(clean)["partitions"][0];item.update(planned="0",runtime="0",total="0",good="0");assert efficiency(item)["status"]=="无计划"
def test_overproduction(clean):
    item=run(clean)["partitions"][0];item.update(ideal_seconds="120");assert efficiency(item)["status"]=="超产"
def test_zero_production(clean):
    item=run(clean)["partitions"][0];item.update(total="0",good="0");assert efficiency(item)["oee"]=="0"
def test_same_attribution_as_model(clean):
    from app.modules.m3_model.service import run as model
    a,b=model(clean),run(clean)
    assert a["cause_totals"]==b["cause_totals"] and a["attribution"]==b["attribution"]
    assert [x["cause_impact"] for x in a["partitions"]]==[x["cause_impact"] for x in b["partitions"]]
def test_availability_deducts_overlap_once(clean):
    item=run(clean)["results"][0]
    assert Decimal(item["downtime_minutes"])==Decimal("90.0")
    assert Decimal(item["availability"])==Decimal("0.8")
    assert Decimal(item["overlap_minutes"])==Decimal("30.0")
def test_impact_does_not_enter_oee(clean):
    result=run(clean);item=result["results"][0]
    assert Decimal(item["oee"])==Decimal(285)/450
    assert Decimal(result["attribution"]["impact_minutes"])>Decimal(result["attribution"]["downtime_minutes"])
