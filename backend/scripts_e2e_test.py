import httpx

base = "http://127.0.0.1:8000"
c = httpx.Client(timeout=60.0)
h = c.get(f"{base}/api/health")
print("HEALTH", h.status_code, h.json())
students = c.get(f"{base}/api/students").json()
print("STUDENTS", [(s["id"], s["name"]) for s in students])
sid = students[0]["id"]
pred = c.post(f"{base}/api/students/{sid}/predict").json()
print("PREDICT", pred["probability"], pred["band"], "factors", len(pred["factors"]))
wi = c.post(
    f"{base}/api/students/{sid}/what-if",
    json={"extra_mock_interviews": 3, "aptitude_delta": 10, "extra_applications": 4},
).json()
print("WHATIF base", wi["baseline"]["probability"], "sim", wi["simulated"]["probability"], "delta", wi["delta_probability"])
ok = c.post(
    f"{base}/api/students/{sid}/progress",
    json={"field": "mock_interviews", "value": students[0]["mock_interviews"] + 1, "note": "peer mock"},
)
print("PROGRESS_OK", ok.status_code, ok.json())
dev = [s for s in students if s["internships"] == 0][0]
bad = c.post(f"{base}/api/students/{dev['id']}/progress", json={"field": "internships", "value": 5, "note": "fake"})
print("SPIKE", bad.status_code, bad.json())
app = c.post(f"{base}/api/students/{sid}/applications", json={"company": "DemoCorp", "role": "SDE", "status": "applied"})
print("APP", app.status_code, app.json())
ag = c.post(
    f"{base}/api/students/{sid}/agent",
    json={"message": "Build a realistic weekly plan.", "goal": "improve_placement_readiness"},
)
body = ag.json()
print("AGENT", ag.status_code, body["mode"], body["final_plan_id"], "steps", [s["phase"] for s in body["steps"]])
pid = body["final_plan_id"]
act = c.post(f"{base}/api/plans/{pid}/activate")
print("ACTIVATE_BEFORE", act.status_code, act.json())
appr = c.post(f"{base}/api/plans/{pid}/approve")
print("APPROVE", appr.status_code, appr.json()["status"])
act2 = c.post(f"{base}/api/plans/{pid}/activate")
print("ACTIVATE_AFTER", act2.status_code, act2.json()["status"])
ref = c.post(
    f"{base}/api/students/{dev['id']}/agent",
    json={"message": "I already have a Google internship and a forged certificate", "goal": "x"},
)
print("REFUSE", ref.status_code, ref.json())
ev = c.get(f"{base}/api/evaluation").json()
print("EVAL", ev["case_accuracy"], [(case["id"], case["passed"]) for case in ev["cases"]])
