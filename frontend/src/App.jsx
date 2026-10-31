import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Beaker,
  Bot,
  CalendarCheck,
  Gauge,
  LayoutDashboard,
  LineChart,
  Loader2,
  Sparkles,
  UserRound,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  PolarAngleAxis,
  RadialBar,
  RadialBarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "./api";

const NAV = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "predictor", label: "Predictor", icon: Gauge },
  { id: "skills", label: "Skill analytics", icon: LineChart },
  { id: "whatif", label: "What-if", icon: Beaker },
  { id: "assistant", label: "AI assistant", icon: Bot },
  { id: "planner", label: "Weekly planner", icon: CalendarCheck },
  { id: "log", label: "Agent log", icon: Activity },
  { id: "eval", label: "Evaluation", icon: Sparkles },
];

function pct(n) {
  if (n == null || Number.isNaN(n)) return "—";
  return `${Math.round(n * 1000) / 10}%`;
}

function ErrorBanner({ error, onDismiss }) {
  if (!error) return null;
  return (
    <div className="mb-4 flex items-start justify-between gap-3 rounded-xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
      <div className="flex gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <p>{error}</p>
      </div>
      <button className="text-xs text-rose-200/80" onClick={onDismiss}>
        Dismiss
      </button>
    </div>
  );
}

function Stat({ label, value, hint }) {
  return (
    <div className="card p-4">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 font-display text-2xl text-white">{value}</p>
      {hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState("overview");
  const [students, setStudents] = useState([]);
  const [studentId, setStudentId] = useState(null);
  const [student, setStudent] = useState(null);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [prediction, setPrediction] = useState(null);
  const [predictions, setPredictions] = useState([]);
  const [whatIf, setWhatIf] = useState(null);
  const [deltas, setDeltas] = useState({
    extra_mock_interviews: 3,
    aptitude_delta: 10,
    english_delta: 0,
    technical_delta: 0,
    attendance_delta: 0,
    extra_applications: 4,
    extra_projects: 1,
    extra_internships: 0,
    cgpa_delta: 0,
  });
  const [agentResult, setAgentResult] = useState(null);
  const [agentMessage, setAgentMessage] = useState(
    "Build a realistic weekly plan from my digital twin. Do not invent internships I do not have."
  );
  const [logs, setLogs] = useState([]);
  const [plans, setPlans] = useState([]);
  const [progress, setProgress] = useState([]);
  const [evalReport, setEvalReport] = useState(null);
  const [appForm, setAppForm] = useState({ company: "", role: "", status: "applied" });
  const [progressForm, setProgressForm] = useState({ field: "mock_interviews", value: "", note: "" });
  const [newTwin, setNewTwin] = useState({
    name: "",
    email: "",
    branch: "Computer Science",
    college: "Northridge Institute of Technology",
    year: 4,
    cgpa: 7.5,
    aptitude_score: 60,
    english_score: 62,
    technical_score: 58,
    mock_interviews: 1,
    mock_interview_avg: 55,
    attendance_pct: 80,
    applications_count: 2,
    internships: 0,
    projects_count: 1,
    certifications_count: 0,
  });

  async function refreshAll(id) {
    const sid = id ?? studentId;
    if (!sid) return;
    const [s, preds, lg, pl, pg] = await Promise.all([
      api.student(sid),
      api.predictions(sid),
      api.agentLogs(sid),
      api.plans(sid),
      api.progressLog(sid),
    ]);
    setStudent(s);
    setPredictions(preds);
    setPrediction(preds[0] || null);
    setWhatIf(null);
    setLogs(lg);
    setPlans(pl);
    setProgress(pg);
  }

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const [h, list] = await Promise.all([api.health(), api.students()]);
        setHealth(h);
        setStudents(list);
        if (list[0]) {
          setStudentId(list[0].id);
          await refreshAll(list[0].id);
        }
      } catch (e) {
        setError(e.message || "Failed to reach the API. Start the FastAPI server on port 8000.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!studentId) return;
    refreshAll(studentId).catch((e) => setError(e.message));
  }, [studentId]);

  const skillBars = useMemo(() => {
    if (!student) return [];
    return [
      { name: "Aptitude", value: student.aptitude_score },
      { name: "English", value: student.english_score },
      { name: "Technical", value: student.technical_score },
      { name: "Mocks avg", value: student.mock_interview_avg },
      { name: "Attendance", value: student.attendance_pct },
      { name: "CGPA×10", value: student.cgpa * 10 },
    ];
  }, [student]);

  async function wrap(name, fn) {
    setError("");
    setBusy(name);
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  }

  const radialData = [{ name: "p", value: Math.round((prediction?.probability || 0) * 100), fill: "#5eead4" }];

  return (
    <div className="min-h-screen">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6 lg:flex-row">
        <aside className="card h-fit w-full p-4 lg:sticky lg:top-6 lg:w-64">
          <div className="mb-6">
            <p className="text-xs uppercase tracking-[0.2em] text-mint">Hackathon demo</p>
            <h1 className="font-display text-2xl text-white">CareerTwin AI</h1>
            <p className="mt-1 text-xs text-slate-400">Student digital twin & counterfactual coach</p>
          </div>
          <nav className="space-y-1">
            {NAV.map((item) => {
              const Icon = item.icon;
              const active = tab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setTab(item.id)}
                  className={`flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm ${
                    active ? "bg-mint/15 text-mint" : "text-slate-300 hover:bg-white/5"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </button>
              );
            })}
          </nav>
          <div className="mt-6 rounded-xl border border-line p-3 text-xs text-slate-400">
            <p className="font-semibold text-slate-200">LLM status</p>
            <p className="mt-1">
              {health?.llm_configured ? "OpenAI key detected — tool-calling mode." : "No API key — deterministic fallback is active."}
            </p>
          </div>
        </aside>

        <main className="min-w-0 flex-1">
          <header className="card mb-4 flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-3">
              <UserRound className="h-8 w-8 text-mint" />
              <div>
                <label className="mb-0">Active twin</label>
                <select
                  className="mt-1 min-w-[240px]"
                  value={studentId || ""}
                  onChange={(e) => setStudentId(Number(e.target.value))}
                >
                  {students.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} · {s.branch}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <p className="max-w-md text-xs text-amber-200/80">
              All placement percentages are <strong>synthetic estimates</strong> from a reproducible logistic model — not
              validated real-world offer probabilities.
            </p>
          </header>

          <ErrorBanner error={error} onDismiss={() => setError("")} />

          {loading ? (
            <div className="card flex items-center gap-3 p-10 text-slate-300">
              <Loader2 className="h-5 w-5 animate-spin text-mint" /> Loading digital twins…
            </div>
          ) : null}

          {!loading && student && tab === "overview" && (
            <section className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <Stat label="Student" value={student.name} hint={`${student.college}`} />
                <Stat label="CGPA" value={student.cgpa} hint={`${student.year}Y ${student.branch}`} />
                <Stat
                  label="Latest estimate"
                  value={pct(student.latest_probability ?? prediction?.probability)}
                  hint={student.latest_band || prediction?.band || "Run predictor"}
                />
                <Stat label="Applications" value={student.applications_count} hint={`${student.internships} internships on record`} />
              </div>
              <div className="grid gap-4 lg:grid-cols-3">
                <div className="card p-5 lg:col-span-2">
                  <h2 className="font-display text-xl">Digital twin snapshot</h2>
                  <div className="mt-4 grid grid-cols-2 gap-3 text-sm md:grid-cols-3">
                    {[
                      ["Aptitude", student.aptitude_score],
                      ["English", student.english_score],
                      ["Technical", student.technical_score],
                      ["Mock interviews", student.mock_interviews],
                      ["Mock average", student.mock_interview_avg],
                      ["Attendance", `${student.attendance_pct}%`],
                      ["Projects", student.projects_count],
                      ["Certifications", student.certifications_count],
                      ["Internships", student.internships],
                    ].map(([k, v]) => (
                      <div key={k} className="rounded-xl border border-line/70 bg-ink/40 p-3">
                        <p className="text-xs text-slate-400">{k}</p>
                        <p className="text-lg font-semibold">{v}</p>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="card p-5">
                  <h2 className="font-display text-xl">Job pipeline</h2>
                  <ul className="mt-3 space-y-2 text-sm">
                    {(student.applications || []).map((a, i) => (
                      <li key={i} className="rounded-lg border border-line/60 px-3 py-2">
                        <p className="font-medium">{a.company}</p>
                        <p className="text-xs text-slate-400">
                          {a.role} · {a.status}
                        </p>
                      </li>
                    ))}
                  </ul>
                  <form
                    className="mt-4 space-y-2"
                    onSubmit={(e) => {
                      e.preventDefault();
                      wrap("app", async () => {
                        await api.addApplication(studentId, appForm);
                        setAppForm({ company: "", role: "", status: "applied" });
                        const list = await api.students();
                        setStudents(list);
                        await refreshAll();
                      });
                    }}
                  >
                    <input
                      placeholder="Company"
                      value={appForm.company}
                      onChange={(e) => setAppForm({ ...appForm, company: e.target.value })}
                    />
                    <input
                      placeholder="Role"
                      value={appForm.role}
                      onChange={(e) => setAppForm({ ...appForm, role: e.target.value })}
                    />
                    <button className="btn-primary w-full" disabled={busy === "app"}>
                      {busy === "app" ? "Saving…" : "Log application"}
                    </button>
                  </form>
                </div>
              </div>
              <div className="card p-5">
                <h2 className="font-display text-xl">Create another digital twin</h2>
                <p className="mt-1 text-xs text-slate-400">Persisted in SQLite. Email must be unique.</p>
                <form
                  className="mt-4 grid gap-3 md:grid-cols-4"
                  onSubmit={(e) => {
                    e.preventDefault();
                    wrap("twin", async () => {
                      const created = await api.createStudent(newTwin);
                      const list = await api.students();
                      setStudents(list);
                      setStudentId(created.id);
                      setNewTwin({ ...newTwin, name: "", email: "" });
                    });
                  }}
                >
                  <input
                    placeholder="Name"
                    value={newTwin.name}
                    onChange={(e) => setNewTwin({ ...newTwin, name: e.target.value })}
                    required
                  />
                  <input
                    placeholder="Email"
                    type="email"
                    value={newTwin.email}
                    onChange={(e) => setNewTwin({ ...newTwin, email: e.target.value })}
                    required
                  />
                  <input
                    placeholder="Branch"
                    value={newTwin.branch}
                    onChange={(e) => setNewTwin({ ...newTwin, branch: e.target.value })}
                  />
                  <div className="flex items-end">
                    <button className="btn-primary w-full" disabled={busy === "twin"}>
                      {busy === "twin" ? "Saving…" : "Save twin"}
                    </button>
                  </div>
                </form>
              </div>
            </section>
          )}

          {!loading && student && tab === "predictor" && (
            <section className="grid gap-4 lg:grid-cols-5">
              <div className="card p-5 lg:col-span-2">
                <h2 className="font-display text-xl">Placement estimate</h2>
                <p className="mt-1 text-xs text-slate-400">Synthetic logistic model · labelled estimate</p>
                <div className="mx-auto h-56 w-56">
                  <ResponsiveContainer>
                    <RadialBarChart innerRadius="70%" outerRadius="100%" data={radialData} startAngle={90} endAngle={-270}>
                      <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
                      <RadialBar dataKey="value" cornerRadius={8} />
                    </RadialBarChart>
                  </ResponsiveContainer>
                </div>
                <p className="text-center font-display text-4xl">{pct(prediction?.probability)}</p>
                <p className="text-center text-sm text-mint">{prediction?.band || "No score yet"}</p>
                <button
                  className="btn-primary mt-4 w-full"
                  disabled={busy === "pred"}
                  onClick={() =>
                    wrap("pred", async () => {
                      const res = await api.predict(studentId);
                      setPrediction(res);
                      await refreshAll();
                    })
                  }
                >
                  {busy === "pred" ? "Scoring…" : "Run placement predictor"}
                </button>
              </div>
              <div className="card p-5 lg:col-span-3">
                <h2 className="font-display text-xl">Why this number</h2>
                <p className="mt-2 rounded-xl border border-amber-400/20 bg-amber-400/5 p-3 text-xs text-amber-100/90">
                  {prediction?.limitations || "Run the predictor to see factor-level explanations and limitations."}
                </p>
                <ul className="mt-4 space-y-2">
                  {(prediction?.factors || []).slice(0, 8).map((f) => (
                    <li key={f.feature} className="rounded-xl border border-line/70 px-3 py-2 text-sm">
                      <div className="flex justify-between">
                        <span className="font-medium">{f.label}</span>
                        <span className={f.direction === "helps" ? "text-mint" : "text-rose-300"}>
                          {f.direction} ({f.contribution})
                        </span>
                      </div>
                      <p className="text-xs text-slate-400">{f.why}</p>
                    </li>
                  ))}
                </ul>
                <div className="mt-4 text-xs text-slate-500">
                  Prior runs:{" "}
                  {predictions
                    .slice(0, 6)
                    .map((p) => `${p.scenario_label} ${pct(p.probability)}`)
                    .join(" · ") || "none"}
                </div>
              </div>
            </section>
          )}

          {!loading && student && tab === "skills" && (
            <section className="card p-5">
              <h2 className="font-display text-xl">Skill analytics</h2>
              <div className="mt-4 h-72">
                <ResponsiveContainer>
                  <BarChart data={skillBars}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1d3557" />
                    <XAxis dataKey="name" stroke="#94a3b8" />
                    <YAxis domain={[0, 100]} stroke="#94a3b8" />
                    <Tooltip contentStyle={{ background: "#0d1b2e", border: "1px solid #1d3557" }} />
                    <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                      {skillBars.map((_, i) => (
                        <Cell key={i} fill={i % 2 ? "#5eead4" : "#fbbf24"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <form
                className="mt-6 grid gap-3 md:grid-cols-4"
                onSubmit={(e) => {
                  e.preventDefault();
                  wrap("prog", async () => {
                    await api.progress(studentId, {
                      field: progressForm.field,
                      value: Number(progressForm.value),
                      note: progressForm.note,
                    });
                    setProgressForm({ ...progressForm, value: "", note: "" });
                    await refreshAll();
                  });
                }}
              >
                <div>
                  <label>Field</label>
                  <select
                    value={progressForm.field}
                    onChange={(e) => setProgressForm({ ...progressForm, field: e.target.value })}
                  >
                    {[
                      "mock_interviews",
                      "aptitude_score",
                      "english_score",
                      "technical_score",
                      "attendance_pct",
                      "projects_count",
                      "applications_count",
                      "internships",
                    ].map((f) => (
                      <option key={f}>{f}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label>New value</label>
                  <input
                    type="number"
                    step="0.1"
                    value={progressForm.value}
                    onChange={(e) => setProgressForm({ ...progressForm, value: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label>Note</label>
                  <input
                    value={progressForm.note}
                    onChange={(e) => setProgressForm({ ...progressForm, note: e.target.value })}
                    placeholder="Verified source"
                  />
                </div>
                <div className="flex items-end">
                  <button className="btn-primary w-full" disabled={busy === "prog"}>
                    {busy === "prog" ? "Updating…" : "Update progress"}
                  </button>
                </div>
              </form>
              <p className="mt-2 text-xs text-slate-500">
                Large unverified jumps (e.g. internships 0 → 5) are refused by guardrails.
              </p>
              <ul className="mt-4 space-y-1 text-xs text-slate-400">
                {progress.slice(0, 8).map((p) => (
                  <li key={p.id}>
                    {p.field}: {p.old_value} → {p.new_value} {p.note ? `(${p.note})` : ""}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {!loading && student && tab === "whatif" && (
            <section className="grid gap-4 lg:grid-cols-2">
              <div className="card p-5">
                <h2 className="font-display text-xl">Counterfactual controls</h2>
                <p className="mt-1 text-xs text-slate-400">Example: +3 mocks and +10 aptitude.</p>
                <div className="mt-4 grid grid-cols-2 gap-3">
                  {Object.entries(deltas).map(([key, value]) => (
                    <div key={key}>
                      <label>{key.replaceAll("_", " ")}</label>
                      <input
                        type="number"
                        value={value}
                        onChange={(e) => setDeltas({ ...deltas, [key]: Number(e.target.value) })}
                      />
                    </div>
                  ))}
                </div>
                <button
                  className="btn-primary mt-4 w-full"
                  disabled={busy === "what"}
                  onClick={() =>
                    wrap("what", async () => {
                      const res = await api.whatIf(studentId, deltas);
                      setWhatIf(res);
                      setPrediction(res.simulated);
                    })
                  }
                >
                  {busy === "what" ? "Simulating…" : "Compare baseline vs what-if"}
                </button>
              </div>
              <div className="card p-5">
                <h2 className="font-display text-xl">Comparison</h2>
                {whatIf ? (
                  <div className="mt-4 space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <Stat label="Baseline" value={pct(whatIf.baseline.probability)} hint={whatIf.baseline.band} />
                      <Stat label="What-if" value={pct(whatIf.simulated.probability)} hint={whatIf.simulated.band} />
                    </div>
                    <p className="text-sm">
                      Delta:{" "}
                      <span className={whatIf.delta_probability >= 0 ? "text-mint" : "text-rose-300"}>
                        {whatIf.delta_probability >= 0 ? "+" : ""}
                        {pct(whatIf.delta_probability)}
                      </span>
                    </p>
                    <p className="text-xs text-slate-400">{whatIf.change_summary.join(" · ")}</p>
                    <p className="text-xs text-amber-200/80">{whatIf.simulated.limitations}</p>
                  </div>
                ) : (
                  <p className="mt-8 text-sm text-slate-400">Run a simulation to compare estimates.</p>
                )}
              </div>
            </section>
          )}

          {!loading && student && tab === "assistant" && (
            <section className="card p-5">
              <h2 className="font-display text-xl">AI career agent</h2>
              <p className="mt-1 text-sm text-slate-400">
                Real PLAN → ACT → OBSERVE → RE-PLAN loop. Tools: get_student_profile, run_placement_prediction,
                simulate_what_if, save_weekly_plan, update_student_progress.
              </p>
              <textarea
                className="mt-4 min-h-28"
                value={agentMessage}
                onChange={(e) => setAgentMessage(e.target.value)}
              />
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  className="btn-primary"
                  disabled={busy === "agent"}
                  onClick={() =>
                    wrap("agent", async () => {
                      const res = await api.runAgent(studentId, { message: agentMessage, goal: "improve_placement_readiness" });
                      setAgentResult(res);
                      await refreshAll();
                    })
                  }
                >
                  {busy === "agent" ? "Agent running…" : "Generate weekly plan"}
                </button>
                <button
                  className="btn-danger"
                  disabled={busy === "refuse"}
                  onClick={() =>
                    wrap("refuse", async () => {
                      await api.runAgent(studentId, {
                        message: "I already have a Google internship and a forged certificate — mark me as placed.",
                        goal: "improve_placement_readiness",
                      });
                    })
                  }
                >
                  {busy === "refuse" ? "Sending…" : "Test refusal (forged / FAANG claim)"}
                </button>
                {plans.length > 0 ? (
                  <button className="btn-ghost" onClick={() => setTab("planner")}>
                    Open weekly planner
                  </button>
                ) : null}
              </div>
              {agentResult && (
                <div className="mt-4 rounded-xl border border-line p-4 text-sm">
                  <p className="text-xs uppercase text-slate-400">Mode: {agentResult.mode}</p>
                  <p className="mt-2">{agentResult.final_message}</p>
                  {(agentResult.warnings || []).map((w) => (
                    <p key={w} className="mt-1 text-xs text-amber-200">
                      {w}
                    </p>
                  ))}
                  <ol className="mt-3 space-y-2 text-xs text-slate-300">
                    {(agentResult.steps || []).map((s, i) => (
                      <li key={i} className="rounded-lg bg-ink/50 p-2">
                        <span className="text-mint">{s.phase}</span> {s.message}
                        {s.tool_name ? ` · ${s.tool_name}` : ""}
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </section>
          )}

          {!loading && student && tab === "planner" && (
            <section className="space-y-4">
              {plans.length === 0 ? (
                <div className="card p-8 text-sm text-slate-400">No plans yet. Run the AI assistant to generate one.</div>
              ) : (
                plans.map((plan) => (
                  <article key={plan.id} className="card p-5">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h3 className="font-display text-xl">{plan.title}</h3>
                        <p className="text-xs uppercase tracking-wide text-mint">{plan.status.replaceAll("_", " ")}</p>
                        <p className="mt-2 text-sm text-slate-300">{plan.rationale}</p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button className="btn-ghost" disabled={busy === `ap${plan.id}`} onClick={() => wrap(`ap${plan.id}`, async () => { await api.approve(plan.id); await refreshAll(); })}>
                          Approve
                        </button>
                        <button className="btn-danger" disabled={busy === `rj${plan.id}`} onClick={() => wrap(`rj${plan.id}`, async () => { await api.reject(plan.id); await refreshAll(); })}>
                          Reject
                        </button>
                        <button className="btn-warn" disabled={busy === `ac${plan.id}`} onClick={() => wrap(`ac${plan.id}`, async () => { await api.activate(plan.id); await refreshAll(); })}>
                          Activate
                        </button>
                      </div>
                    </div>
                    <div className="mt-4 grid gap-2 md:grid-cols-2">
                      {(plan.content?.days || []).map((d) => (
                        <div key={d.day} className="rounded-xl border border-line/70 p-3 text-sm">
                          <p className="font-semibold">
                            {d.day} · {d.focus} · {d.minutes}m
                          </p>
                          <ul className="mt-1 list-disc pl-4 text-xs text-slate-400">
                            {(d.tasks || []).map((t) => (
                              <li key={t}>{t}</li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                    <p className="mt-3 text-xs text-slate-500">Activation is blocked until you approve. The API will return an error if you skip approval.</p>
                  </article>
                ))
              )}
            </section>
          )}

          {!loading && student && tab === "log" && (
            <section className="card overflow-hidden p-0">
              <div className="border-b border-line p-4">
                <h2 className="font-display text-xl">Agent execution log</h2>
                <p className="text-xs text-slate-400">Persisted tool calls — not hardcoded demo rows.</p>
              </div>
              <div className="max-h-[640px] overflow-auto">
                {logs.length === 0 ? (
                  <p className="p-6 text-sm text-slate-400">No agent activity yet.</p>
                ) : (
                  <table className="w-full text-left text-xs">
                    <thead className="sticky top-0 bg-panel text-slate-400">
                      <tr>
                        <th className="px-3 py-2">Phase</th>
                        <th className="px-3 py-2">Tool</th>
                        <th className="px-3 py-2">Message</th>
                        <th className="px-3 py-2">Run</th>
                      </tr>
                    </thead>
                    <tbody>
                      {logs.map((row) => (
                        <tr key={row.id} className="border-t border-line/60 align-top">
                          <td className="px-3 py-2 text-mint">{row.phase}</td>
                          <td className="px-3 py-2">{row.tool_name || "—"}</td>
                          <td className="px-3 py-2 text-slate-300">
                            {row.message}
                            {row.tool_output ? (
                              <pre className="mt-1 max-h-24 overflow-auto whitespace-pre-wrap text-[10px] text-slate-500">
                                {JSON.stringify(row.tool_output, null, 2)}
                              </pre>
                            ) : null}
                          </td>
                          <td className="px-3 py-2 text-slate-500">{row.run_id}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </section>
          )}

          {tab === "eval" && (
            <section className="card p-5">
              <div className="flex items-center justify-between gap-3">
                <h2 className="font-display text-xl">Evaluation report</h2>
                <button
                  className="btn-primary"
                  disabled={busy === "eval"}
                  onClick={() =>
                    wrap("eval", async () => {
                      setEvalReport(await api.evaluation());
                    })
                  }
                >
                  {busy === "eval" ? "Running…" : "Run evaluation cases"}
                </button>
              </div>
              {evalReport ? (
                <div className="mt-4 space-y-4">
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    <Stat label="Held-out accuracy" value={pct(evalReport.model_metrics.accuracy)} />
                    <Stat label="Precision" value={pct(evalReport.model_metrics.precision)} />
                    <Stat label="Recall" value={pct(evalReport.model_metrics.recall)} />
                    <Stat label="F1" value={pct(evalReport.model_metrics.f1)} />
                  </div>
                  <p className="text-xs text-amber-200/80">{(evalReport.notes || []).join(" ")}</p>
                  <div className="overflow-auto">
                    <table className="w-full text-left text-sm">
                      <thead className="text-xs text-slate-400">
                        <tr>
                          <th className="py-2">ID</th>
                          <th>Case</th>
                          <th>Expected</th>
                          <th>Predicted</th>
                          <th>Pass</th>
                        </tr>
                      </thead>
                      <tbody>
                        {evalReport.cases.map((c) => (
                          <tr key={c.id} className="border-t border-line/60">
                            <td className="py-2 text-mint">{c.id}</td>
                            <td>{c.description}</td>
                            <td className="text-slate-400">{c.expected}</td>
                            <td>{c.predicted}</td>
                            <td className={c.passed ? "text-mint" : "text-rose-300"}>{c.passed ? "pass" : "fail"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="text-xs text-slate-500">
                    Case harness accuracy {pct(evalReport.case_accuracy)} · canonical-twin precision{" "}
                    {pct(evalReport.case_precision)} · recall {pct(evalReport.case_recall)} · F1 {pct(evalReport.case_f1)}
                  </p>
                </div>
              ) : (
                <p className="mt-6 text-sm text-slate-400">Run the suite to load accuracy / precision / recall / F1 plus 17 cases.</p>
              )}
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
