"use strict";

// Static DOM behavior checks. This does not launch a browser or render pixels.
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const vm = require("node:vm");
const crypto = require("node:crypto");

const root = path.resolve(__dirname, "..");
const htmlPath = path.join(root, "runs", "demo.html");
const reportPath = path.join(root, "runs", "experiment.json");
const outputPath = path.join(root, "runs", "verification", "dom-check.json");
const jsdomPath = process.env.MEMORY_POLICY_JSDOM || path.join(os.tmpdir(), "memory-policy-dom-qa", "node_modules", "jsdom");
const { JSDOM, VirtualConsole } = require(jsdomPath);
const jsdomVersion = JSON.parse(fs.readFileSync(path.join(jsdomPath, "package.json"), "utf8")).version;
const html = fs.readFileSync(htmlPath, "utf8");
const reportBytes = fs.readFileSync(reportPath);
const source = JSON.parse(reportBytes.toString("utf8").replace(/^\uFEFF/, ""));
const errors = [];
const failures = [];
const counters = { assertions: 0, selector_combinations: 0, table_row_clicks: 0, write_transitions: 0, model_trials: 0 };
let networkAttempts = 0;

function verify(condition, message, evidence) {
  counters.assertions += 1;
  if (!condition) failures.push({ message, evidence });
}

function equal(actual, expected, message) {
  verify(JSON.stringify(actual) === JSON.stringify(expected), message, { actual, expected });
}

const virtualConsole = new VirtualConsole();
virtualConsole.on("jsdomError", error => errors.push({ type: error.type, message: error.message }));
virtualConsole.on("error", (...args) => errors.push({ type: "console_error", message: args.map(String).join(" ") }));
const dom = new JSDOM(html, {
  runScripts: "outside-only",
  virtualConsole,
  beforeParse(window) {
    const blocked = () => { networkAttempts += 1; throw new Error("Networking is disabled in this static DOM check."); };
    for (const name of ["fetch", "XMLHttpRequest", "WebSocket", "EventSource"]) {
      Object.defineProperty(window, name, { value: blocked, writable: false, configurable: false });
    }
    Object.defineProperty(window.navigator, "sendBeacon", { value: blocked, writable: false });
  },
});
const { window } = dom;
const document = window.document;
const byId = id => document.getElementById(id);
const normalize = value => String(value ?? "").replace(/\s+/g, " ").trim();
const human = value => String(value ?? "unknown").replace(/[_-]/g, " ");
const number = node => Number((node?.textContent ?? "").replace(/[^0-9.-]/g, ""));

function detailsValue(container, label) {
  const details = [...container.querySelectorAll("details")].find(element => element.querySelector("summary")?.textContent === label);
  verify(Boolean(details), "Required inspection control exists", { label });
  const text = details?.querySelector("pre")?.textContent;
  return text;
}

function checkArm(panelId, arm, label) {
  const panel = byId(panelId);
  verify(Boolean(arm), "Expected report arm exists", { label });
  if (!arm) return;
  equal(number(panel.querySelector(".token-number")), arm.tokens, "Displayed input count matches report: " + label);
  equal(JSON.parse(detailsValue(panel, "Inspect every selected record and its metadata")), arm.selected, "All selected record metadata matches: " + label);
  equal(detailsValue(panel, "Inspect the exact serialized prompt"), arm.prompt, "Exact serialized prompt matches: " + label);
  equal(JSON.parse(detailsValue(panel, "Inspect exclusion reasons")), arm.excluded || [], "Exclusion reasons match: " + label);
  equal(JSON.parse(detailsValue(panel, "Inspect the complete agent state")), arm.state_after || {}, "Agent state matches: " + label);
  const metrics = panel.querySelectorAll(".metric strong");
  equal(number(metrics[0]), Math.round(arm.required_recall * 100), "Required fact recall matches: " + label);
  equal(number(metrics[1]), arm.selected.length, "Supplied record count matches: " + label);
  equal(number(metrics[2]), arm.scope_leaks, "Scope leak count matches: " + label);
  const cards = [...panel.querySelectorAll(".memory-list .memory")];
  equal(cards.length, Math.min(16, arm.selected.length), "Visible memory card count matches: " + label);
  cards.forEach((card, index) => {
    const record = arm.selected[index];
    equal(card.querySelector("p").textContent, String(record.value ?? record.content ?? JSON.stringify(record, null, 2)), "Memory card content matches: " + label);
    verify(card.querySelector(".meta").textContent.includes(record.id), "Memory card ID matches", { label, index, id: record.id });
    verify(card.querySelector(".type").textContent.includes(human(record.key || "record")), "Memory key is visible", { label, index });
  });
  const output = arm.state_after?.output ?? arm.state_after?.result;
  if (output) {
    const outputNodes = [...panel.querySelectorAll(".outcome .field-grid > div")];
    for (const [key, value] of Object.entries(output)) {
      const element = outputNodes.find(node => node.querySelector("b")?.textContent === human(key));
      verify(Boolean(element), "Task output field is visible", { label, key });
      const text = element ? element.textContent.slice(element.querySelector("b").textContent.length) : "";
      const expected = typeof value === "object" ? JSON.stringify(value, null, 2) : String(value ?? "");
      equal(text, expected, "Task output value matches: " + label + ":" + key);
    }
  }
}

function change(id, value) {
  byId(id).value = String(value);
  byId(id).dispatchEvent(new window.Event("change", { bubbles: true }));
}

function checkSelectedRow(row, baselineName) {
  const baseline = row.arms.find(arm => arm.name === baselineName);
  const policy = row.arms.find(arm => arm.name === "policy");
  const label = `${row.workflow}/${row.run}/${baselineName}`;
  checkArm("before", baseline, label);
  checkArm("after", policy, label + "/policy");
  const expectedCounts = [row.store_counts.total, row.store_counts.active,
    row.store_counts.superseded + row.store_counts.quarantined, policy.selected.length];
  equal([...byId("saved").querySelectorAll("strong")].map(number), expectedCounts, "Saved-versus-supplied counts match: " + label);
  verify(byId("taskContext").textContent.includes(human(row.workflow)) && byId("taskContext").textContent.includes("run " + row.run),
    "Workflow and run labels update", { label, actual: byId("taskContext").textContent });
  verify(!/\b(?:NaN|undefined)\b/.test(document.querySelector("main").textContent), "No missing-value artifacts in the rendered DOM", { label });
}

let embedded;
try {
  embedded = JSON.parse(byId("experiment-data").textContent);
  equal(embedded, source, "Embedded report matches the current source report");
  verify(document.querySelectorAll("script[src],iframe,img[src],link[rel=stylesheet]").length === 0,
    "No external resource elements are present");
  const scripts = [...document.querySelectorAll("script")].filter(script => script.type !== "application/json");
  equal(scripts.length, 1, "Only one authored script is executed");
  new vm.Script(scripts[0].textContent, { filename: "memory-policy-demo-inline.js" }).runInContext(dom.getInternalVMContext(), { timeout: 30000 });

  equal(byId("workflow").value, source.comparisons[0].workflow, "Default workflow is the first workflow");
  equal(byId("run").value, "200", "Default run is 200");
  equal(byId("baseline").value, "budgeted_recency", "Default baseline is budgeted recency");
  const workflows = [...new Set(source.comparisons.map(row => row.workflow))];
  equal(byId("workflow").options.length, workflows.length, "Every recorded workflow has a selector option");

  for (const row of source.comparisons) {
    for (const baseline of row.arms.filter(arm => arm.name !== "policy")) {
      change("workflow", row.workflow);
      change("run", row.run);
      change("baseline", baseline.name);
      checkSelectedRow(row, baseline.name);
      counters.selector_combinations += 1;
    }
    for (const baseline of row.arms.filter(arm => arm.name !== "policy")) {
      const tableRow = byId("comparisonTable").querySelector(`tr[data-arm="${baseline.name}"]`);
      verify(Boolean(tableRow), "Baseline table row exists", { workflow: row.workflow, run: row.run, arm: baseline.name });
      tableRow.click();
      equal(byId("baseline").value, baseline.name, "Clicking a table row changes the baseline selector");
      equal(detailsValue(byId("before"), "Inspect the exact serialized prompt"), baseline.prompt, "Table-row click updates the prompt");
      counters.table_row_clicks += 1;
    }
  }

  for (const workflow of workflows) {
    change("workflow", workflow);
    change("run", 200);
    const transitions = source.write_transitions.filter(event => event.workflow === workflow && event.run <= 200);
    equal(byId("writeEvent").options.length, transitions.length, "Every eligible write transition is selectable: " + workflow);
    const indices = [...new Set([0, transitions.length - 1,
      transitions.findIndex(event => event.before?.length && event.decision?.status === "accepted"),
      transitions.findIndex(event => event.decision?.status === "quarantined")])].filter(index => index >= 0);
    for (const index of indices) {
      change("writeEvent", index);
      const actual = JSON.parse(detailsValue(byId("writeDetail"), "Inspect this complete write transition"));
      equal(actual, transitions[index], "Write event changes to the correct saved transition");
      verify(byId("writeDetail").textContent.includes(human(transitions[index].decision.reason)), "Write reason is visible", { workflow, index });
      counters.write_transitions += 1;
    }
  }

  const compaction = source.learning?.compaction;
  const evolution = source.learning?.evolution;
  verify(Boolean(compaction && evolution), "Both learning demonstrations are present in the source report");
  if (compaction) {
    equal([...byId("compaction").querySelectorAll(".saved strong")].map(number),
      [compaction.before.message_count, compaction.before.token_count, compaction.after.message_count, compaction.after.token_count],
      "Compaction before-and-after counts match");
    equal(JSON.parse(detailsValue(byId("compaction"), "Inspect complete compaction evidence")), compaction,
      "Complete compaction evidence is inspectable");
    if (compaction.repeated_cycles?.length) {
      const cycleRows = [...byId("compactionCycles").querySelectorAll("tbody tr")];
      equal(cycleRows.length, compaction.repeated_cycles.length, "Every repeated compaction cycle is visible");
      cycleRows.forEach((row, index) => {
        const cycle = compaction.repeated_cycles[index];
        const cells = row.querySelectorAll("td");
        equal(number(cells[0]), cycle.cycle, "Compaction cycle identity matches");
        equal(number(cells[1]), cycle.new_message_count, "New message count matches");
        equal(number(cells[2]), cycle.retained_source_count, "Retained source count matches");
        equal(cells[3].textContent, `${cycle.state_before_tokens.toLocaleString("en-US")} → ${cycle.state_after_tokens.toLocaleString("en-US")}`,
          "Repeated compaction input counts match");
        equal(number(cells[4]), cycle.state_token_limit, "Repeated compaction limit matches");
      });
    }
  }
  if (evolution) {
    equal(JSON.parse(detailsValue(byId("evolution"), "Inspect complete learning evidence")), evolution,
      "Complete evolution evidence is inspectable");
    verify(byId("evolution").textContent.includes(human(evolution.after.without_lesson.outcome)), "Before-lesson outcome is visible");
    verify(byId("evolution").textContent.includes(human(evolution.after.with_lesson.result.outcome)), "After-lesson outcome is visible");
    verify(byId("evolution").textContent.includes(human(evolution.rollback.after.result.outcome)), "Rollback outcome is visible");
  }
  const cases = source.evaluation?.cases || [];
  equal(byId("tests").querySelectorAll(".test").length, cases.length, "Every independent evaluation case is visible");
  equal(JSON.parse(detailsValue(byId("tests"), "Inspect the complete independent evaluation report")), source.evaluation,
    "Complete independent test evidence is inspectable");
  const trials = source.model_trials || [];
  if (source.hybrid_evaluation) {
    verify(byId("hybrid").textContent.includes("hand-authored vectors"), "Hybrid fixture boundary is visible");
    verify(byId("hybrid").textContent.includes(source.hybrid_evaluation.query), "Hybrid query is visible");
    equal(JSON.parse(detailsValue(byId("hybrid"), "Inspect hybrid ranking evidence and fixture vectors")),
      source.hybrid_evaluation, "Hybrid evidence matches the report");
    for (const record of source.hybrid_evaluation.after.selected) {
      verify(byId("hybrid").textContent.includes(record.value), "Selected hybrid memory is visible", {id: record.id});
    }
  }
  verify(byId("modelSummary").textContent.includes("OpenAI model trials"), "Current model panel identifies OpenAI");
  if (!trials.length) {
    verify(byId("models").textContent.includes("No live API observations"), "Pending API verification is explicit");
    verify(byId("models").textContent.includes("token estimates"), "Offline counts are identified as estimates");
  }
  const modelCards = [...byId("models").querySelectorAll(".model-card")];
  equal(modelCards.length, trials.length, "Every actual model observation is visible");
  modelCards.forEach((card, index) => {
    const trial = trials[index];
    equal(JSON.parse(detailsValue(card, "Inspect the full trial, prompt, and expected output")), trial,
      "Actual model trial data matches");
    equal(detailsValue(card, "Inspect the actual model response"), trial.result.response, "Actual model response matches");
    verify(card.textContent.includes(String(trial.result.prompt_eval_count)), "Observed model input count is visible", { index });
    if (trial.appropriate_abstention === true) verify(card.textContent.includes("Correct abstention"), "Correct abstention is not labeled a model error", { index });
    counters.model_trials += 1;
  });

  for (const anchor of document.querySelectorAll("a[href]")) {
    const href = anchor.getAttribute("href");
    verify(!/^(?:https?:|javascript:|data:)/i.test(href), "Demo links are local artifact references", { href });
    if (!href.startsWith("#")) {
      const target = path.resolve(path.dirname(htmlPath), decodeURIComponent(href.split("#")[0]));
      verify(fs.existsSync(target), "Linked source artifact exists", { href, target });
    }
  }
  verify(networkAttempts === 0, "The demo made no network attempts", { networkAttempts });
  verify(errors.length === 0, "No DOM or authored-script errors occurred", errors);
} catch (error) {
  failures.push({ message: "Static DOM check stopped with an exception", error: String(error), stack: error.stack });
} finally {
  const result = {
    status: failures.length ? "failed" : "passed",
    checked_at: new Date().toISOString(),
    method: "jsdom static DOM and authored JavaScript execution in a Node VM",
    jsdom_version: jsdomVersion,
    node_version: process.version,
    html_sha256: crypto.createHash("sha256").update(html).digest("hex"),
    report_sha256: crypto.createHash("sha256").update(reportBytes).digest("hex"),
    report_model_trials: source.model_trials?.length || 0,
    counters,
    network_attempts: networkAttempts,
    errors,
    failures,
    evidence_boundary: "No browser was launched. This verifies DOM behavior and evidence binding, not visual layout, screenshots, or browser rendering.",
  };
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, JSON.stringify(result, null, 2) + "\n", "utf8");
  dom.window.close();
  console.log(JSON.stringify({ status: result.status, counters, failures: failures.slice(0, 6), output: outputPath }, null, 2));
  process.exitCode = failures.length ? 1 : 0;
}
