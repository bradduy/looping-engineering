# Loop Engineering and Harness Engineering: A Comparative Analysis of Two Disciplines for Operating Autonomous Coding Agents

**A Technical Report**

*OnLOOP Project*

---

## Abstract

The rapid capability gains of large language model (LLM) coding agents have shifted the locus of engineering effort away from the model and toward the *system that operates the model*. Two named disciplines emerged in 2026 to describe this shift: **loop engineering**, the design of the self-running cycle that prompts an agent toward a goal, and **harness engineering**, the design of the full scaffolding that surrounds a model to make it reliable. The two terms are frequently conflated. This report formalizes both, argues that they are not competitors but stand in a part-whole relation (the loop is one component of the harness), and characterizes the distinct failure modes each addresses. We give a six-tuple formal model of a loop, identify two safety invariants (mandatory verification, mandatory termination) that distinguish an engineered loop from the colloquial "Ralph loop," and ground the analysis in OnLOOP, a contracts-first reference implementation. We conclude that loop engineering is best understood as the *temporal/control-flow specialization* of harness engineering, and that the highest-leverage practical contribution of treating the loop as a first-class engineered object is the enforcement of verification and termination as type-level obligations rather than discretionary practices.

**Keywords:** agentic engineering, autonomous agents, LLM orchestration, control loops, verification, harness, software agents

---

## 1. Introduction

A coding agent is increasingly described by the decomposition

```
Agent = Model + Harness
```

where the *model* supplies intelligence and the *harness* is "everything in an AI agent except the model itself" [Böckeler 2026; Osmani 2026b]. As frontier models saturate single-prompt benchmarks, the marginal return on prompt-level optimization falls and the return on *system-level* design rises. Two disciplines name this system-level work.

**Loop engineering** is "building a system that prompts your agent on a schedule and against a goal, instead of typing each prompt yourself" [Osmani 2026a]. Its thesis: leverage has moved from the quality of a single prompt to the design of the system that *generates and verifies* prompts.

**Harness engineering** is "the discipline of designing, building, and iterating on the scaffolding that surrounds a language model" [Böckeler 2026]: context delivery, tool interfaces, guardrails, memory, sandboxes, and feedback loops.

Practitioners often use the terms interchangeably, or treat them as rival schools. This report argues that this is a category error. We make four contributions:

1. A formal six-tuple model of an engineered loop and its execution semantics (§4).
2. A characterization of harness engineering as a feedforward/feedback control structure, and a proof-sketch that the loop is a proper subcomponent of the harness (§5).
3. A multi-dimensional comparison establishing that the two disciplines optimize *orthogonal* axes: temporal/control-flow versus spatial/scaffolding (§6).
4. An empirical grounding in OnLOOP, a reference implementation whose type system enforces two invariants that the bare "Ralph loop" leaves optional (§7).

---

## 2. Background and Related Work

### 2.1 The agent loop

The cyclic structure of a rational agent (perceive, deliberate, act, observe) predates LLMs by decades. It is the basic control structure of the Belief-Desire-Intention model and is codified in standard AI textbooks [Russell and Norvig 1995]. LLMs did not invent the loop; they made a *general-purpose* actor cheap enough to place inside it, which is what unlocked open-ended agentic behavior [Oracle 2026].

### 2.2 Loop engineering

The phrase *loop engineering* was popularized by Osmani [2026a] in June 2026, crystallizing observations by Steinberger ("you should be designing loops that prompt your agents") and Cherny ("my role shifted to write loops rather than to prompt the model directly"). It is the deliberate framing of the agent's outer cycle as the primary engineering artifact.

### 2.3 The Ralph loop

The minimal instantiation of loop engineering is the **Ralph loop** [Huntley 2026], named after the Simpsons character. Its canonical form is one line:

```bash
while :; do cat PROMPT.md | agent ; done
```

Its key insight is that *progress lives in files and git history, not in the context window*. Each iteration starts a fresh agent with a fixed prompt, performs a small amount of work, writes results and learnings to disk, and exits; when context fills, the next agent reorients from those files. The convention separates a fixed task (`PROMPT.md`), accumulated learnings (`AGENTS.md`), and a progress log (`progress.md`) [Huntley 2026; Bharath 2026]. Critically, the bare Ralph loop has *no required verifier and no termination condition*: the `while :;` is literally infinite. We return to this in §7.3.

### 2.4 Harness engineering

*Harness engineering* was developed by Böckeler [2026] at Thoughtworks (memo February 2026, article April 2026) and elaborated by Osmani [2026b] and LangChain [2026]. It frames the harness as two classes of control: **feedforward** guides (conventions, documentation, templates, linters configured ahead of time) and **feedback** sensors (tests, static analysis, review agents that observe output and enable self-correction). These controls may be *computational* (deterministic, fast) or *inferential* (semantic, model-based, slower). LangChain's experiments report that an explicit four-stage structure (Plan, Build, Verify, Fix) outperforms unstructured loops [LangChain 2026], evidence that harness structure, not raw model capability, governs reliability.

### 2.5 Positioning

Prior writing treats the two terms separately and rarely formalizes either. This report supplies a formal model and an explicit reconciliation.

---

## 3. Definitions

We fix terminology used throughout.

- **Model** *(M)*: the LLM, treated as a black-box stochastic function from context to text/tool-calls.
- **Harness** *(H)*: the deterministic-and-inferential system around *M*; everything that is not *M*.
- **Loop** *(L)*: the control structure that repeatedly invokes the agent toward a goal; a component of *H*.
- **Sensor**: any procedure that observes an action's result and returns a verdict with evidence (feedback).
- **Guide**: any artifact that constrains generation before it occurs (feedforward).

---

## 4. A Formal Model of Loop Engineering

### 4.1 The loop as a six-tuple

We model an engineered loop as

```
L = (G, W, A, S, M_s, T)
```

| Symbol | Role | Signature (informal) |
|---|---|---|
| `G` | Goal | `is_satisfied : State → Bool` |
| `W` | WorkSource | `find : State → List[WorkItem]` |
| `A` | Actor | `act : WorkItem × Context → ActionResult` |
| `S` | Sensor(s) | `verify : WorkItem × ActionResult × Context → Verdict` |
| `M_s` | Memory / StateStore | `load/save/record` over a persistent `State` |
| `T` | StopCondition(s) | `should_stop : State → Decision` |

### 4.2 Inputs and outputs

Viewed as a function, a loop has the signature

```
run : (G, W, A, S, M_s, T) × (Workspace, M, Budget) → (r, D, σ*, H, Workspace')
       \________config________/ \______environment______/   \________outcome________/
```

- **Input** is *a goal plus the means to pursue and check it*: the objective `G` with its success predicate; the model `M` as the actor's oracle; the workspace to act on; any state `σ₀` restored from a prior run (so a loop resumes, not restarts); and the verification/termination policy (`S`, `T`, budget).
- **Output** is *a terminated, audited outcome*: a stop reason `r`; a done-set `D` containing only items that passed their sensors (by P1); the mutated work product `Workspace'`; a replayable per-iteration trace `H`; and a final state `σ*` that is itself a valid input to the next run.

The output is therefore **self-describing** (why it stopped), **verifiable** (what passed), and **resumable** (where to continue). This contrasts with harness engineering, whose I/O is per-*step*: it maps a model plus task context (guides, tools, memory) to one constrained, sensor-checked action. A loop's I/O is the closure of the harness's I/O over many steps until `T` fires.

### 4.3 Execution semantics

A run is the least fixed point of the transition rule applied from an initial state `σ₀` loaded from `M_s`:

```
repeat:
    if ∃ t ∈ T . should_stop(σ) then halt(reason)         # (R1) stop is checked first
    items ← { w ∈ W.find(σ) | id(w) ∉ done(σ) }
    if items = ∅ then σ ← bump_empty(σ); continue           # dryness accrues
    w ← head(items)
    r ← A.act(w, σ)
    v ← ⋀_{s ∈ S} s.verify(w, r, σ)                         # (R2) conjunction of sensors
    if passed(v) then σ ← σ[done ← done ∪ {id(w)}]          # (R3) progress iff verified
    σ ← M_s.record(σ, ⟨w, r, v, τ⟩); persist(σ)             # (R4) durable, restartable
```

The timestamp `τ` is supplied by the runtime, not read by any contract; this keeps a run *replayable* from its recorded trace.

### 4.4 Properties

Two properties follow directly from the rule and are the heart of the discipline.

- **P1 (Verified progress).** By (R2)–(R3), an item enters the done-set only if the conjunction of all sensors passes. No sensor, no progress. An action that the loop cannot check does not advance the goal.
- **P2 (Guaranteed termination).** If `T` contains at least one bound that is monotone in a quantity the runtime increments every pass (iteration count, accumulated cost, or consecutive empty rounds), the run halts. (R1) evaluates `T` before any work, so the bound cannot be skipped.

P1 and P2 are not automatic; they hold only if `S ≠ ∅` and `T` contains a real bound. An *engineered* loop is precisely one in which these are obligations rather than options (§7.2).

### 4.5 Loop patterns as instances of `L`

Common patterns are recovered by choosing components, not by writing new control flow:

- **Ralph loop:** `G` = a fixed PRD/spec, `M_s` = files + git, `S` often empty (its weakness), `T` absent.
- **Loop-until-dry:** `T` includes a condition firing after *k* consecutive empty `W.find` results.
- **Fan-out/verify:** `W` yields independent items processed under isolation; `S` runs per item.
- **Adversarial verify:** `S` is a panel of skeptics; `passed(v)` requires a majority to survive refutation.

---

## 5. A Formal View of Harness Engineering

### 5.1 The harness as a control structure

Following Böckeler [2026], the harness is a pair of control populations over the model:

```
H = (Guides, Sensors, Tools, Memory, L)
```

where **Guides** are feedforward controls applied before generation and **Sensors** are feedback controls applied after. Böckeler's central operating rule is a *meta-loop*: "whenever an issue happens multiple times, the feedforward and feedback controls should be improved." This is a second-order loop in which the *engineer* (or, prospectively, an automated guide-writer) updates `Guides` and `Sensors` in response to recurring failures.

### 5.2 Inputs and outputs

The harness has an I/O contract too, but a per-*step* one. Treating a single agent step as a function:

```
step : M × Ctx → (a, v, Δμ, tr)
```

where the harness both *assembles* the input context `Ctx` (feedforward) and *checks* the resulting action (feedback).

**Input: the model `M` and the context `Ctx`.** The model supplies capability; `Ctx` is everything the harness packs into the window for this step:

- **Task** — the current instruction or subtask.
- **Guides** (feedforward) — conventions, architectural rules, templates, linter configuration: constraints applied *before* generation.
- **Tools** — the action interface available this step (edits, shell, search, MCP servers).
- **Memory** — retrieved relevant state: prior decisions, accumulated learnings (`AGENTS.md`), code excerpts.
- **Sandbox** — the execution environment and its permissions.

Assembling this within the context window is itself the engineering work ("context engineering").

**Output: a checked step `(a, v, Δμ, tr)`.**

- `a` — a single action (edit, tool call, message), possibly blocked or rewritten by a guardrail before it takes effect.
- `v` — the sensor verdict on `a`, *with evidence*: a conjunction of **computational** sensors (deterministic, fast: linters, tests, type-checkers) and **inferential** sensors (semantic, slower: review agents, LLM judges).
- `Δμ` — side effects: the mutated workspace if `a` is applied, and any learnings written back to memory.
- `tr` — telemetry for observability (the step's cost, decision, and verdict).

Harness engineering is precisely the design of *what enters `Ctx`* (feedforward) and *which sensors produce `v`* (feedback); it turns raw model capability into a reliable, *checked* step. The relationship to the loop is exact: the loop's per-run signature (`run`, Sec. 4.2) is the closure of `step` iterated under the control flow of `T`, threading each `Δμ` into the next step's `Ctx` and aggregating each `v` into verified progress. Where harness I/O asks "is this one step good?", loop I/O asks "is the whole goal met, and when do we stop?".

### 5.3 The loop is a subcomponent of the harness

**Proposition.** `L` is a proper subset of `H`.

*Argument.* The harness is defined as everything that is not the model. The loop's components `W, A, S, M_s, T` are each non-model deterministic-or-inferential procedures, hence elements of `H`. The sensor population `S` of the loop is exactly the feedback-control population of the harness; the loop's memory `M_s` is the harness memory; the actor `A` is the harness's invocation of the model. The loop additionally contributes control flow (`T`, the transition rule) that the harness, viewed statically, does not. Conversely `H` contains `Guides` (feedforward) and `Tools` that are not part of the loop's defining tuple. Therefore `L ⊊ H`. ∎

This is the central structural claim: **loop engineering is the control-flow specialization of harness engineering.** The two are not rivals; one is a part of the other.

### 5.4 Two loops, often conflated

There are two distinct cycles in play, and confusing them is a common source of error:

1. The **inner agent loop** (perceive-act-verify), a harness component, formalized as `L`.
2. The **outer steering loop**, Böckeler's meta-loop, in which a human improves guides and sensors over time.

Loop engineering, in its strong form, is partly the project of *automating the outer loop* (e.g., the Ralph convention of appending learnings to `AGENTS.md`) so that supervision scales sublinearly with agent activity.

---

## 6. Comparative Analysis

We compare along ten dimensions. The summary:

| Dimension | Loop Engineering | Harness Engineering |
|---|---|---|
| **Primary object** | The self-running cycle that drives the agent | The full scaffolding around the model |
| **Axis** | Temporal / control-flow (when, how often, until when) | Spatial / structural (what surrounds the model) |
| **Unit of leverage** | The system that generates and verifies prompts | The constraints and feedback that shape output |
| **Input → output** | Goal + model oracle + workspace + prior state → stop reason + verified done-set + mutated workspace + replayable trace | Model + task context (guides, tools, memory) → one constrained, sensor-checked action |
| **Failure mode addressed** | Human is the bottleneck; cannot run unattended | Output is unreliable; agent does the wrong thing |
| **Control-theory analogue** | The closed-loop controller and its stopping rule | The full plant: actuators, sensors, setpoints |
| **Verification stance** | Verification is a stage of the cycle (`S`) | Verification is one of two control populations |
| **Termination** | First-class concern (`T`); core to the discipline | Implicit; not central |
| **Lifecycle / ownership** | Often automated, scheduled, recursive | Iteratively improved by a human meta-loop |
| **Canonical artifact** | A loop spec; the executor | Guides + sensors + tools + sandboxes |

### 6.1 Object and axis (orthogonality)

The cleanest distinction is *axis*. Harness engineering operates on a **spatial** axis: breadth of scaffolding around the model at a single instant. Loop engineering operates on a **temporal** axis: the cadence and control flow across many invocations. A practitioner can hold one fixed while varying the other. One may improve the harness (add a linter, a better template) without changing the loop, and one may change the loop (schedule it, add loop-until-dry) without changing the harness's guides. Orthogonality is the operational signature that two disciplines are distinct rather than synonymous.

### 6.2 Failure mode (the diagnostic test)

The disciplines are most easily told apart by the problem that motivates reaching for each:

- Reach for **harness** vocabulary when the symptom is *"the agent produces wrong or unconstrained output."* The fix is in `Guides` and `Sensors`.
- Reach for **loop** vocabulary when the symptom is *"the agent is capable, but I am stuck driving every iteration."* The fix is a scheduled, goal-driven, self-verifying cycle.

### 6.3 Verification: shared substrate, different framing

Both disciplines centre verification, which is why they are easy to conflate. In harness terms, sensors are one of two control populations. In loop terms, verification is the gate `(R2)–(R3)` without which `P1` fails. They refer to the *same* artifacts (tests, linters, review agents) under different framings: a static taxonomy of controls versus a stage in a dynamic cycle.

### 6.4 Termination: where loop engineering is irreducible

Termination is the one concern that loop engineering owns and harness engineering largely ignores. A static harness has no notion of "when to stop." The bare Ralph loop demonstrates the cost of this gap: an infinite `while` with no verifier can iterate confidently in the wrong direction. Property `P2` and the obligation `T ≠ ∅` are contributions that only make sense once the loop is treated as a first-class engineered object.

---

## 7. Case Study: OnLOOP

OnLOOP is a contracts-first reference implementation used here as an existence proof that the formal model is realizable and that the two safety invariants can be enforced mechanically.

### 7.1 Architecture

OnLOOP implements the six-tuple of §4.1 as six abstract interfaces (`Goal`, `WorkSource`, `Actor`, `Sensor`, `StateStore`, `StopCondition`). A concrete loop is one implementation of each, declared in a YAML spec that binds a contract to a class via a dotted path. A runtime (`LoopRunner`) executes the transition rule of §4.2: stop conditions are checked first (R1), progress requires all sensors to pass (R2–R3), and state is persisted every pass (R4) through a JSON `StateStore`, making runs restartable.

### 7.2 Invariants as type-level obligations

OnLOOP's spec schema enforces `P1` and `P2` *at load time* rather than leaving them to discipline:

- `sensors` requires at least one entry: a loop that cannot check itself will not load (enforces `S ≠ ∅`, the precondition of `P1`).
- `stop` requires at least one entry: a loop that cannot terminate will not load (enforces `T ≠ ∅`, the precondition of `P2`).

This is the report's main practical claim: *the value of treating the loop as a first-class object is the promotion of verification and termination from optional practices to non-negotiable, machine-checked obligations.*

### 7.3 The Ralph loop as a degenerate instance

In the model of §4, the bare Ralph loop is the instance with `S = ∅` and `T = ∅`. Both safety properties fail: progress is unverified (`P1` void) and the run never halts (`P2` void). OnLOOP rejects exactly this configuration. The relationship is summarized as a slogan:

> The Ralph loop is the loop with the brakes optional. OnLOOP is the same loop with the brakes required.

### 7.4 Empirical sanity check

A deterministic, model-free reference loop (clearing a punch list of work items on disk) exercises every component and each stop reason. Its end-to-end test suite confirms: convergence to `goal_met` with verified progress, correct bounding by `max_iters` before goal, `loop_until_dry` termination on an empty work source, that a permanently failing sensor blocks an item from the done-set (a direct test of `P1`), and that state round-trips across a simulated restart (a test of R4). All cases pass. Because the actor is deterministic, the suite isolates the *control structure* from model stochasticity, which is the property under test. We make no claim about model-in-the-loop performance; that is future work (§10).

---

## 8. Integrating a Loop into a Task

Loop engineering is applied by answering six questions about a task, one per contract, and binding each answer to an implementation.

### 8.1 Recipe: from a task to a loop

1. **State the goal `G` as a check, not a wish.** Name the command or predicate true exactly when the task is done (`pytest` exits 0; no `TODO` markers remain). If you cannot write the check, the task is not yet loop-ready.
2. **Define the work source `W`.** Decide how an iteration discovers the next unit (parse failing tests, scan open items, pull a queue), skipping anything already in the done-set.
3. **Implement the actor `A`.** The smallest step that advances one unit: usually a single model call with a focused prompt, or a deterministic edit. Keep it small so a bad step is cheap to discard.
4. **Wire the sensor(s) `S` *before* the actor.** At least one verifier with evidence; prefer a fast computational sensor (tests, linter), add an inferential one (a review agent) only where semantics matter.
5. **Choose the state store `M_s`.** The default JSON store suffices; pick a *stable* done-key per work item so resumption never redoes work.
6. **Set stop conditions `T`.** Always `GoalMet` plus a real bound (`MaxIterations`, a token budget, or `LoopUntilDry`); never ship a loop without one.

Steps 1, 4, and 6 are non-negotiable: they establish the preconditions of P1 and P2. Isolation and budget are optional policy layered on top.

### 8.2 Worked example: drive a test suite to green

The bindings become a declarative spec (abbreviated):

```yaml
name: make-tests-green
goal:        { uses: myloops.AllTestsPass, with: { cmd: "pytest -q" } }
work_source: { uses: myloops.FailingTests }
actor:       { uses: myloops.FixOneTest,   with: { model: <llm> } }
sensors:
  - { uses: myloops.PytestSensor }
  - { uses: myloops.RuffSensor }            # second check
stop:
  - { uses: onloop.stops.GoalMet }
  - { uses: onloop.stops.MaxIterations, with: { max_iters: 25 } }
budget:    { max_tokens: 400000 }
isolation: worktree
```

A runtime loads the spec and executes the transition rule of §4.3: each pass finds one failing test, the actor proposes a fix, *both* sensors must pass for it to count as done, and the run halts at `goal_met`, the iteration cap, or the token budget. Because state is persisted every pass, an interrupted run resumes where it stopped (`onloop resume`).

### 8.3 Where a loop plugs in

The same loop integrates into different surfaces by changing only *when* it runs and *what bounds* it: a **scheduled** job (run nightly until `dry`); a **pre-merge gate** (run once; fail the build unless `goal_met`); a **batch migration** (one work item per file, with `isolation: worktree` so parallel actors do not collide); or a **supervised** run (a human-on-the-loop checkpoint every `k` iterations). The contract bindings are unchanged; only `T` and the trigger differ.

### 8.4 Pitfalls

The recurring failures each violate a precondition of P1 or P2: an unverifiable goal (no check); the actor running before any sensor exists (fast, unchecked mistakes); unstable done-keys (work repeats on resume); and a missing real bound (an effectively infinite loop). The schema-level obligations of §7 catch the last two at load time.

---

## 9. Discussion

### 8.1 A unifying picture

```
Agent
└── Harness                         ← harness engineering designs all of this
     ├── Guides (feedforward)        conventions, docs, templates, linters
     ├── Sensors (feedback)          tests, static analysis, review agents
     ├── Tools / Memory / Sandbox
     └── Loop (L)                    ← loop engineering designs this part
          G → W.find → A.act → S.verify → M_s → T → repeat
```

Harness engineering draws the box; loop engineering animates one component of it over time.

### 8.2 Practical guidance

The disciplines are complementary and a mature agent system needs both. A reasonable order of operations: establish a harness with at least one feedback sensor and a useful guide; *then* engineer the loop that drives the agent through it, fixing termination and verification first because they are the cheap, high-consequence invariants.

### 8.3 Why the distinction matters

Conflating the two leads to two characteristic mistakes. Treating loop engineering as the whole story yields the Ralph failure: a slick autonomous cycle with no brakes. Treating harness engineering as the whole story yields a well-instrumented agent that still needs a human in the chair for every step. Naming the axes separately lets a team diagnose which one is actually deficient.

---

## 10. Limitations and Threats to Validity

- **Construct validity.** Both terms are recent (2026) and not yet standardized; our definitions follow the originating sources but the community usage is still in flux.
- **Single implementation.** Our empirical grounding is one reference framework (OnLOOP) with a deterministic actor. We demonstrate that the invariants are *enforceable* and that the control structure is *correct*, not that loops with real LLM actors converge efficiently on real software tasks.
- **No model-in-the-loop benchmark.** We deliberately exclude model stochasticity to isolate control flow; consequently we report no task-success or cost metrics against a baseline. The LangChain Plan/Build/Verify/Fix result [LangChain 2026] is cited as external, independent evidence that harness structure matters, but it is not our measurement.
- **Generality of the proposition.** The claim `L ⊊ H` rests on the "everything but the model" definition of the harness; under a narrower definition of harness the relation could change.

---

## 11. Conclusion and Future Work

Loop engineering and harness engineering are not competing schools; they are a part and a whole. The harness is the spatial scaffolding around a model; the loop is the temporal control structure that is one component of that scaffolding. Loop engineering's distinctive contribution is to make *verification* and *termination* first-class, and the most useful engineering consequence is to enforce them as type-level obligations, as OnLOOP does, rather than as discretionary good practice. The bare Ralph loop is precisely the degenerate case that omits both.

Future work: (1) a model-in-the-loop evaluation with LLM-backed actors and real sensors (pytest, static analysis) against a single-prompt and a bare-Ralph baseline; (2) formalization and implementation of the *outer* steering loop as an automated guide-writer (the `AGENTS.md` write-back), turning Böckeler's meta-loop into a `GuideStore` contract; (3) isolation and safety mechanisms (worktrees, human-on-the-loop checkpoints) as additional loop invariants.

---

## References

- Bharath, S. (2026). *Ralph Wiggum: The Dumbest Smart Way to Run Coding Agents.* https://sidbharath.com/blog/ralph-wiggum-claude-code/
- Böckeler, B. (2026). *Harness Engineering for Coding Agent Users.* martinfowler.com. https://martinfowler.com/articles/harness-engineering.html
- Huntley, G. (2026). The Ralph loop / Ralph Wiggum technique. See: Wiegold, T. *The Ralph Loop: How Recursive AI Agents Actually Work.* https://thomas-wiegold.com/blog/ralph-loop-how-recursive-ai-agents-work/ ; snarktank/ralph, https://github.com/snarktank/ralph
- LangChain (2026). *The Anatomy of an Agent Harness.* https://www.langchain.com/blog/the-anatomy-of-an-agent-harness
- Oracle (2026). *What Is the AI Agent Loop? The Core Architecture Behind Autonomous AI Systems.* https://blogs.oracle.com/developers/what-is-the-ai-agent-loop-the-core-architecture-behind-autonomous-ai-systems
- Osmani, A. (2026a). *Loop Engineering: Designing Systems That Prompt AI Agents.* (popularization, building on P. Steinberger and B. Cherny). https://lushbinary.com/blog/loop-engineering-ai-coding-agents-guide/
- Osmani, A. (2026b). *Agent Harness Engineering.* https://addyosmani.com/blog/agent-harness-engineering/
- Russell, S., and Norvig, P. (1995). *Artificial Intelligence: A Modern Approach.* (agent loop and the BDI model).
- Thoughtworks (2026). *Harness Engineering and Agent Feedback: Exploring AI Coding Sensors.* https://www.thoughtworks.com/en-us/insights/blog/generative-ai/harness-engineering-agent-feedback-exploring-ai-coding-sensors

---

*This report accompanies the OnLOOP reference implementation. See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the engineering design and [`PATTERNS.md`](PATTERNS.md) for the loop pattern catalogue.*
