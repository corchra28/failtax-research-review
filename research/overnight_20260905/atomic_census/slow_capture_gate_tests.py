"""Testul portii de integritate a rezervelor: trebuie sa ESUEZE (False) cand exista cel putin o incalcare."""
import json,re
src=open("research/overnight_20260905/atomic_census/slow_capture.py").read(); ns={}
exec(src.split("def reserve_gate_ok(viol):")[1].split("\nif g is not None")[0].join(["def reserve_gate_ok(viol):",""]),ns)
r=dict(no_violations=ns["reserve_gate_ok"]({}) is True,one_chain_break_fails=ns["reserve_gate_ok"]({"CHAIN_BREAK_DECISION_TO_LANDING":1}) is False,one_unprovable_fails=ns["reserve_gate_ok"]({"LANDING_STATE_NOT_PROVABLE":1}) is False,outage_fails=ns["reserve_gate_ok"]({"STATE_IN_OUTAGE_OR_TRUNCATION":3}) is False,no_or_true_in_source=("or True" not in src))
print(json.dumps(r,indent=1)); print("RESERVE_GATE_TESTS =","PASS" if all(r.values()) else "FAIL")
