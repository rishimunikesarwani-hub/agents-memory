
"use strict";
const REPORT=JSON.parse(document.getElementById("experiment-data").textContent);
const $=id=>document.getElementById(id);
const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt=value=>typeof value==="number"?value.toLocaleString("en-US"):"—";
const pretty=value=>JSON.stringify(value??null,null,2);
const human=value=>String(value??"unknown").replace(/[_-]/g," ");
const LABELS={full_replay:"Full history replay",last_four:"Last four records",budgeted_recency:"Budgeted recency",accumulated_top3:"Accumulated top-three history",policy:"Memory policy"};
const COLORS={full_replay:"#c36c66",last_four:"#8e9bab",budgeted_recency:"#6693bf",accumulated_top3:"#c5a050",policy:"#82629f"};
const comparisons=REPORT.comparisons||[];
const workflows=[...new Set(comparisons.map(row=>row.workflow))];
let current=null;
let writes=[];

function badge(text,kind=""){return `<span class="chip ${kind}">${esc(text)}</span>`}
function inspected(label,value,klass=""){return `<details class="inspect"><summary>${esc(label)}</summary><pre class="${klass}">${esc(typeof value==="string"?value:pretty(value))}</pre></details>`}
function valueList(object){if(!object||typeof object!=="object")return esc(object??"No output recorded");return `<div class="field-grid">${Object.entries(object).map(([key,value])=>`<div><b>${esc(human(key))}</b>${esc(typeof value==="object"?pretty(value):value)}</div>`).join("")}</div>`}
function memories(records,limit=16){if(!records?.length)return '<div class="empty">No records were selected.</div>';return `<div class="memory-list">${records.slice(0,limit).map(record=>`<div class="memory ${record.pinned?"required":""}"><div class="type">${esc(record.kind||"memory")} · ${esc(human(record.key||"record"))}${record.pinned?" · pinned":""}${record.status?" · "+esc(record.status):""}</div><p>${esc(record.value??record.content??pretty(record))}</p><div class="meta">${esc(record.id??"No ID")} · ${esc(record.source??"source unknown")} · day ${esc(record.observed_at??"?")}</div></div>`).join("")}</div>${records.length>limit?`<p class="small">Showing ${limit} of ${fmt(records.length)} records. The full selection is available below.</p>`:""}`}
function armPanel(arm,isPolicy){
 if(!arm)return '<div class="panel-body empty">This comparison was not recorded.</div>';
 const over=Boolean(arm.overflow)||(Number(arm.tokens)>Number(arm.input_limit));
 const state=arm.state_after||{};
 const success=arm.task_success===true;
 const status=over?"Input exceeds budget":success?"Task succeeded":human(state.stage||arm.status||"not evaluated");
 const title=isPolicy?"After · Memory policy":"Before · "+(LABELS[arm.name]||human(arm.name));
 const output=state.output??state.result;
 const action=state.action?human(state.action):human(state.stage||"no action recorded");
 const percent=Number.isFinite(arm.required_recall)?Math.round(arm.required_recall*100)+"%":"—";
 return `<div class="panel-head"><div><div class="eyebrow">${isPolicy?"Scoped, valid, bounded evidence":"Baseline context assembly"}</div><h2>${esc(title)}</h2></div>${badge(status,over?"bad":success?"good":"warn")}</div><div class="panel-body"><div class="token-row"><div><div class="small">Estimated input · offline tokenizer</div><div class="token-number">${fmt(arm.tokens)} <small>tokens</small></div></div><div class="small">Input limit<br><strong>${fmt(arm.input_limit)} tokens</strong></div></div><div class="meter ${over?"over":""}"><span style="width:${Math.min(100,Math.max(0,100*(arm.tokens||0)/(arm.input_limit||1)))}%"></span></div><div class="small">${over?"The runner blocks this input before inference.":"The estimated prompt fits the allowance. API trials check the exact count before generation."}</div><div class="metrics"><div class="metric"><strong>${esc(percent)}</strong><span>required facts recalled</span></div><div class="metric"><strong>${fmt(arm.selected?.length)}</strong><span>records supplied</span></div><div class="metric"><strong>${fmt(arm.scope_leaks)}</strong><span>scope leaks</span></div></div><div class="outcome ${success?"good":"bad"}"><h3>Agent action · ${esc(action)}</h3><p>${esc(state.reason??state.message??(success?"The deterministic agent produced the expected synthetic result.":"Inspect the recorded state to see why the task did not pass."))}</p>${output?valueList(output):""}</div><div class="memory-label"><span>Memories supplied to this request</span><span class="small">${fmt(arm.stale_fact_count)} stale · ${fmt(arm.duplicate_count)} duplicate</span></div>${memories(arm.selected)}${inspected("Inspect every selected record and its metadata",arm.selected||[])}${inspected("Inspect the exact serialized prompt",arm.prompt||"No prompt recorded","prompt")}${inspected("Inspect exclusion reasons",arm.excluded||[])}${inspected("Inspect the complete agent state",state)}</div>`;
}

function renderSaved(row,policy){
 const counts=row.store_counts||{};
 const tiles=[[counts.total,"Saved records",true],[counts.active,"Active records",false],[Number(counts.superseded||0)+Number(counts.quarantined||0),"Superseded or quarantined",false],[policy?.selected?.length,"Records supplied now",false]];
 $("saved").innerHTML=tiles.map(([value,label,highlight])=>`<div class="tile ${highlight?"highlight":""}"><strong>${fmt(value)}</strong><span>${esc(label)}</span></div>`).join("");
}

function renderChart(){
 const rows=comparisons.filter(row=>row.workflow===$("workflow").value).sort((a,b)=>a.run-b.run);
 const names=["full_replay","last_four","budgeted_recency","accumulated_top3","policy"].filter(name=>rows.some(row=>row.arms.some(arm=>arm.name===name)));
 const width=650,height=275,left=62,right=20,top=20,bottom=50;
 const max=Math.max(1000,...rows.flatMap(row=>row.arms.map(arm=>Number(arm.tokens)||0)));
 const logMax=Math.log10(max+1)*1.06;
 const y=value=>top+(height-top-bottom)*(1-Math.log10(value+1)/logMax);
 const x=index=>left+index*(width-left-right)/Math.max(1,rows.length-1);
 const ticks=[0,10,100,1000,10000,100000,1000000].filter(value=>value<=max);
 let svg=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Input tokens across recorded runs, with a logarithmic vertical scale"><rect width="${width}" height="${height}" fill="white"/>`;
 for(const tick of ticks)svg+=`<line x1="${left}" x2="${width-right}" y1="${y(tick)}" y2="${y(tick)}" stroke="#e9edf2"/><text x="${left-10}" y="${y(tick)+4}" font-size="11" text-anchor="end" fill="#6a7585">${fmt(tick)}</text>`;
 const limit=current?.arms.find(arm=>arm.name==="policy")?.input_limit;
 if(Number.isFinite(limit))svg+=`<line x1="${left}" x2="${width-right}" y1="${y(limit)}" y2="${y(limit)}" stroke="#a99045" stroke-dasharray="5 4"/><text x="${width-right}" y="${y(limit)-7}" text-anchor="end" font-size="10" fill="#917735">Input limit ${fmt(limit)}</text>`;
 for(const name of names){const points=rows.map((row,index)=>({arm:row.arms.find(arm=>arm.name===name),index})).filter(item=>item.arm);svg+=`<polyline points="${points.map(({arm,index})=>`${x(index)},${y(arm.tokens)}`).join(" ")}" fill="none" stroke="${COLORS[name]}" stroke-width="${name==="policy"?3:2}"/>`;for(const {arm,index}of points)svg+=`<circle cx="${x(index)}" cy="${y(arm.tokens)}" r="${name==="policy"?4:3}" fill="${COLORS[name]}"><title>${esc(LABELS[name])}, run ${rows[index].run}: ${fmt(arm.tokens)} tokens</title></circle>`}
 rows.forEach((row,index)=>{svg+=`<text x="${x(index)}" y="${height-25}" font-size="11" text-anchor="middle" fill="#687587">Run ${row.run}</text>`});
 svg+=`<text x="${left}" y="${height-5}" font-size="10" fill="#7c8795">Logarithmic token scale · recorded checkpoints shown at equal spacing</text></svg>`;
 $("chart").innerHTML=svg;$("legend").innerHTML=names.map(name=>`<span><i style="background:${COLORS[name]}"></i>${esc(LABELS[name])}</span>`).join("");
}

function renderTable(row){
 $("comparisonTable").innerHTML=`<table><thead><tr><th>Method</th><th>Input</th><th>Recall</th><th>Task</th></tr></thead><tbody>${row.arms.map(arm=>`<tr data-arm="${esc(arm.name)}" class="${arm.name==="policy"?"current":""}"><td>${esc(LABELS[arm.name]||human(arm.name))}</td><td>${fmt(arm.tokens)}${arm.overflow?" ↑":""}</td><td>${Number.isFinite(arm.required_recall)?Math.round(arm.required_recall*100)+"%":"—"}</td><td>${arm.task_success===true?badge("Pass","good"):badge(arm.overflow?"Blocked":"Did not pass","warn")}</td></tr>`).join("")}</tbody></table>`;
 $("comparisonTable").querySelectorAll("tr[data-arm]").forEach(row=>row.addEventListener("click",()=>{if(row.dataset.arm!=="policy"){$("baseline").value=row.dataset.arm;renderSelection()}}));
}

function renderWrites(){
 writes=(REPORT.write_transitions||[]).filter(event=>event.workflow===current.workflow&&event.run<=current.run);
 const significant=writes.map((event,index)=>({event,index})).filter(({event})=>event.before?.length||event.decision?.status!=="accepted");
 $("writeEvent").innerHTML=writes.map((event,index)=>`<option value="${index}">Run ${esc(event.run)} · ${esc(event.candidate?.key||event.candidate?.id||"memory")} · ${esc(human(event.decision?.status))}</option>`).join("");
 const preferred=significant.at(-1)?.index??writes.length-1;
 $("writeEvent").value=String(preferred);$("writeEvent").disabled=!writes.length;renderWriteDetail();
}

function renderWriteDetail(){
 const event=writes[Number($("writeEvent").value)];
 if(!event){$("writeDetail").innerHTML='<div class="panel-body empty">No write transition was recorded for this checkpoint.</div>';return}
 const decision=event.decision||{};
 $("writeDetail").innerHTML=`<div class="write-description">${badge(human(decision.status),decision.status==="accepted"?"good":"warn")} <strong>${esc(human(decision.reason))}</strong><p class="small">Candidate: ${esc(event.candidate?.value??"No candidate value recorded")}</p></div><div class="write-columns"><div><h3>Saved state before this write</h3>${memories(event.before||[],5)}</div><div><h3>Saved state after this write</h3>${memories(event.after||[],5)}</div></div><div style="padding:0 20px 18px">${inspected("Inspect this complete write transition",event)}</div>`;
}

function renderSelection(){
 current=comparisons.find(row=>row.workflow===$("workflow").value&&String(row.run)===$("run").value);
 if(!current)return;
 const baseline=current.arms.find(arm=>arm.name===$("baseline").value);const policy=current.arms.find(arm=>arm.name==="policy");
 $("before").innerHTML=armPanel(baseline,false);$("after").innerHTML=armPanel(policy,true);
 $("taskContext").innerHTML=`<strong>${esc(human(current.workflow))} · run ${esc(current.run)}</strong> · Same task and event history for both methods.`;
 $("evidenceContext").textContent="Main comparison: deterministic agent + local simulated tools";
 renderSaved(current,policy);renderChart();renderTable(current);renderWrites();
 $("checkpoints").innerHTML=`<p class="small">A checkpoint records the current task state. Restoring it does not rewind the separate memory store.</p><div class="write-columns" style="padding:0"><div><h3>Before the agent step</h3><pre>${esc(pretty(current.checkpoint_before))}</pre></div><div><h3>After the agent step</h3><pre>${esc(pretty(current.checkpoint_after))}</pre></div></div>${inspected("Inspect the independent expected result",current.expected)}`;
}

function renderTests(){
 const evaluation=REPORT.evaluation||{};const cases=evaluation.cases||[];
 const passed=cases.filter(item=>item.status==="passed").length;const failed=cases.filter(item=>item.status==="failed").length;const limitations=cases.filter(item=>item.status==="limitation").length;
 $("testSummary").textContent=`Policy checks · ${passed} passed · ${failed} failed · ${limitations} limitation${limitations===1?"":"s"}`;
 $("tests").innerHTML=`<p class="small">These tests inspect enforcement and persisted state. A disclosed retrieval limitation is not counted as a successful retrieval.</p><div class="test-cards">${cases.map(item=>`<details class="test"><summary>${badge(human(item.status),item.status==="passed"?"good":item.status==="failed"?"bad":"warn")}<br>${esc(human(item.name))}</summary><pre>${esc(pretty(item.evidence??item))}</pre></details>`).join("")}</div>${inspected("Inspect the complete independent evaluation report",evaluation)}`;
}

function renderLearning(name,title){
 const value=REPORT.learning?.[name];
 if(!value){$(name).innerHTML='<div class="empty">This demonstration has not been recorded.</div>';return}
 const lead=name==="compaction"?"Compaction changes working context. The saved evidence and protected task fields must remain inspectable.":"This demonstration changes an explicit lesson used by a deterministic agent. It does not update model weights.";
 let summary="";
 if(name==="compaction"){
  summary=`<div class="saved"><div class="tile"><strong>${fmt(value.before?.message_count)}</strong><span>Messages before</span></div><div class="tile"><strong>${fmt(value.before?.token_count)}</strong><span>Context tokens before</span></div><div class="tile highlight"><strong>${fmt(value.after?.message_count)}</strong><span>Messages after</span></div><div class="tile highlight"><strong>${fmt(value.after?.token_count)}</strong><span>Context tokens after</span></div></div><p class="small">The compact state keeps protected task fields and a reference to the saved source messages.</p>`;
  if(Array.isArray(value.repeated_cycles)&&value.repeated_cycles.length){summary+=`<div class="table-wrap" id="compactionCycles"><table><thead><tr><th>Cycle</th><th>New messages</th><th>Retained source messages</th><th>State input before → after</th><th>State limit</th><th>Check</th></tr></thead><tbody>${value.repeated_cycles.map(cycle=>`<tr><td>${fmt(cycle.cycle)}</td><td>${fmt(cycle.new_message_count)}</td><td>${fmt(cycle.retained_source_count)}</td><td>${fmt(cycle.state_before_tokens)} → ${fmt(cycle.state_after_tokens)}</td><td>${fmt(cycle.state_token_limit)}</td><td>${badge(human(cycle.status),cycle.status==="passed"?"good":"warn")}</td></tr>`).join("")}</tbody></table></div><p class="small">Repeated compaction preserves prior source versions. Saved source history grows while the working state stays bounded in these recorded cycles.</p>`}
 }else{
  const before=value.after?.without_lesson||value.before?.result;const after=value.after?.with_lesson?.result;
  summary=`<div class="write-columns" style="padding:0"><div class="outcome bad"><h3>Same later task · without the lesson</h3><p>${esc(human(before?.outcome))}</p>${inspected("Inspect baseline action trace",before?.trace||before)}</div><div class="outcome good"><h3>Same later task · with the accepted lesson</h3><p>${esc(human(after?.outcome))}</p>${inspected("Inspect changed action trace",after?.trace||after)}</div></div><div class="field-grid"><div><b>Candidate admission</b>${esc(human(value.good_lesson?.admission?.status))}</div><div><b>Unverified recipient</b>${esc(human(value.after?.unknown_recipient?.result?.outcome))}</div><div><b>After explicit rollback</b>${esc(human(value.rollback?.after?.result?.outcome))}</div><div><b>Model weights changed</b>No — this is a stored action-plan lesson.</div></div>`;
 }
 const checks=Object.entries(value.checks||{}).map(([key,passed])=>`<div class="test">${badge(passed===true?"Passed":"Did not pass",passed===true?"good":"bad")}<br><span class="small">${esc(human(key))}</span></div>`).join("");
 $(name).innerHTML=`<p>${esc(lead)}</p>${badge(human(value.status),value.status==="passed"?"good":"warn")}<div style="margin-top:15px">${summary}</div><div class="test-cards" style="margin-top:18px">${checks}</div>${Object.entries(value).filter(([key,item])=>item&&typeof item==="object"&&key!=="checks").map(([key,item])=>inspected(human(key),item)).join("")}${inspected("Inspect complete "+title+" evidence",value)}<p class="small">${esc(value.boundary||"")}</p>`;
}

function renderModels(){
 const trials=REPORT.model_trials||[];
 $("modelSummary").textContent=`OpenAI model trials · ${trials.length} recorded`;
 if(!trials.length){$("models").innerHTML='<div class="empty">OpenAI is configured. No live API observations are recorded in this report. The comparisons above are deterministic and use token estimates.</div>';return}
 $("models").innerHTML='<p class="small">These are actual model responses. Task completion and grounded behavior are separate checks. Correct abstention can reveal missing context without showing a model error. All trials remain visible.</p>'+trials.map((trial,index)=>{
 const result=trial.result||{};const status=trial.trial_trusted===false?"Observation not trusted":trial.task_success===true?"Task completed":trial.appropriate_abstention===true?"Correct abstention · task incomplete":trial.grounded_response===false?"Unsupported response":trial.task_success===false?"Task incomplete":"Not scored";
 const color=trial.trial_trusted===false||trial.grounded_response===false?"bad":trial.task_success===true?"good":"warn";
 const response=result.response??result.message?.content??result.output??result;
 return `<article class="model-card"><div class="model-top"><h3>${esc(human(trial.workflow))} · run ${esc(trial.run)} · ${esc(LABELS[trial.arm]||human(trial.arm))}</h3>${badge(status,color)}</div><p>Repeat ${esc(trial.repeat??"not recorded")} · Model ${esc(result.provider_model??result.model??result.request?.model??trial.model??"see full trial")}</p><div class="field-grid"><div><b>Observed prompt tokens</b>${fmt(result.prompt_eval_count??trial.prompt_eval_count)}</div><div><b>Observed output tokens</b>${fmt(result.eval_count??trial.eval_count)}</div><div><b>Response grounded in supplied evidence</b>${trial.grounded_response===true?"Yes":trial.grounded_response===false?"No":"Not scored"}</div><div><b>Preflight count matches runtime count</b>${result.token_count_match===true?"Yes":result.token_count_match===false?"No":"Not recorded"}</div></div>${inspected("Inspect the actual model response",response)}${inspected("Inspect the full trial, prompt, and expected output",trial)}</article>`;
 }).join("");
}

function renderHybrid(){
 const result=REPORT.hybrid_evaluation;
 if(!result){$("hybrid").innerHTML='<div class="empty">No hybrid evaluation is recorded.</div>';return}
 const modes=[...new Set(comparisons.flatMap(row=>row.arms.filter(arm=>arm.name==="policy").map(arm=>arm.retrieval||"not recorded")))];
 $("hybrid").innerHTML=`<div class="callout"><strong>Offline ranking test: hand-authored vectors</strong>This test verifies the retrieval code. It does not measure OpenAI embedding quality. Live API calls: ${fmt(result.live_api_calls)}.</div><p><b>Query:</b> ${esc(result.query)}<br><b>Current replay retrieval:</b> ${esc(modes.join(", "))}. An incomplete cache uses keyword matching.</p><div class="write-columns"><div><h3>Before: keyword matching</h3>${memories(result.before?.selected||[])}</div><div><h3>After: keyword + vector similarity</h3>${memories(result.after?.selected||[])}</div></div>${inspected("Inspect hybrid ranking evidence and fixture vectors",result)}`;
}

function initialize(){
 if(!comparisons.length){$("before").innerHTML='<div class="panel-body empty">No comparison rows are present in the experiment report.</div>';return}
 $("workflow").innerHTML=workflows.map(workflow=>`<option value="${esc(workflow)}">${esc(human(workflow).replace(/\b[a-e]$/,letter=>letter.toUpperCase()))}</option>`).join("");
 const runs=[...new Set(comparisons.map(row=>row.run))].sort((a,b)=>a-b);
 $("run").innerHTML=runs.map(run=>`<option value="${run}">Run ${run}</option>`).join("");$("run").value=String(runs.includes(200)?200:runs.at(-1));
 const names=[...new Set(comparisons.flatMap(row=>row.arms.map(arm=>arm.name)))].filter(name=>name!=="policy");
 $("baseline").innerHTML=names.map(name=>`<option value="${esc(name)}">${esc(LABELS[name]||human(name))}</option>`).join("");if(names.includes("budgeted_recency"))$("baseline").value="budgeted_recency";
 for(const id of ["workflow","run","baseline"])$(id).addEventListener("change",renderSelection);
 $("writeEvent").addEventListener("change",renderWriteDetail);
 renderSelection();renderTests();renderLearning("compaction","compaction");renderLearning("evolution","learning");renderModels();renderHybrid();
 const limitations=Array.isArray(REPORT.limitations)?REPORT.limitations:[REPORT.limitations].filter(Boolean);
 $("limitations").innerHTML='<strong>Read the evidence boundary</strong><ul>'+limitations.map(item=>`<li>${esc(typeof item==="string"?item:pretty(item))}</li>`).join("")+'</ul>';
 $("footerEvidence").textContent=`${comparisons.length} recorded comparisons · ${workflows.length} workflows · file works offline`;
}
initialize();
