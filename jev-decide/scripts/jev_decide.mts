// Generic Jev decision helper (advisory). Reads a decision SPEC (JSON) — the observed
// state, a bounded Choice question whose options carry what/pros/cons, and optional gate
// thresholds — asks TypeSafe's System One (Jev), and prints the choice + full distribution
// + confidence + margin, then a VERDICT: PROCEED or ESCALATE (human decides).
//
//   node <skill-dir>/scripts/jev_decide.mts <spec.json>   # or pipe the spec on stdin
//
// The verdict is a "when to look" heuristic, never a correctness guarantee — the human owns
// correctness. It ESCALATEs if ANY gate trips:
//   • margin  (top1 − top2) < minMargin      → a close race between options
//   • confidence            < minConfidence  → a diffuse distribution
//   • spec.decision.irreversible === true    → hard-to-reverse/external; always escalate
// Defaults: minMargin 0.15, minConfidence 0.60. Both overridable per spec.
//
// See the `jev-decide` skill (SKILL.md) for how to author a good spec, and
// example-decision.json for a worked example. Zero deps — plain fetch (Node 22.6+ strips types).
import { readFileSync } from 'node:fs';
import { homedir } from 'node:os';

// `tie: true` marks an "either is fine — pick any arbitrarily" option (e.g. "都可以"). It
// means the options are EQUIVALENT, not "unsure": when it wins we waive the margin/confidence
// gates (a benign tie is expected to look low-margin), but never the irreversible gate.
type OptionSpec = { what: string; pros?: string; cons?: string; tie?: boolean } | string;
type Spec = {
  state: unknown;
  decision: {
    instructions: string;
    options: Record<string, OptionSpec>;
    irreversible?: boolean;
  };
  thresholds?: { minConfidence?: number; minMargin?: number };
};

// Cred: ~/.config/typesafe/cred.json { account?, api_key }. Override with TYPESAFE_CRED.
const credPath = process.env.TYPESAFE_CRED ?? `${homedir()}/.config/typesafe/cred.json`;
const cred = JSON.parse(readFileSync(credPath, 'utf8')) as { api_key?: string };
if (!cred.api_key) { console.error(`${credPath} has no api_key.`); process.exit(2); }

// Spec from argv path or stdin.
const specPath = process.argv[2];
const specText = specPath ? readFileSync(specPath, 'utf8') : readFileSync(0, 'utf8');
let spec: Spec;
try { spec = JSON.parse(specText) as Spec; }
catch (e) { console.error(`spec is not valid JSON: ${(e as Error).message}`); process.exit(2); }
if (!spec?.decision?.instructions || !spec.decision.options || Object.keys(spec.decision.options).length < 2) {
  console.error('spec needs decision.instructions and >= 2 decision.options.');
  process.exit(2);
}

const minConfidence = spec.thresholds?.minConfidence ?? 0.6;
const minMargin = spec.thresholds?.minMargin ?? 0.15;

// Strip the runner-only `tie` flag before sending criteria to Jev; track which keys are ties.
const tieKeys = new Set<string>();
const criteria: Record<string, OptionSpec> = {};
for (const [key, opt] of Object.entries(spec.decision.options)) {
  if (typeof opt === 'object' && opt.tie) { tieKeys.add(key); const { tie: _tie, ...rest } = opt; criteria[key] = rest; }
  else criteria[key] = opt;
}

const res = await fetch('https://api.typesafe.ai/v1/systemone', {
  method: 'POST',
  headers: { Authorization: `Bearer ${cred.api_key}`, 'Content-Type': 'application/json' },
  body: JSON.stringify({
    state: spec.state ?? {},
    model: 'jev-latest',
    questions: { decision: { type: 'choice', instructions: spec.decision.instructions, criteria } },
  }),
});
if (!res.ok) { console.error(`System One HTTP ${res.status}: ${(await res.text()).slice(0, 300)}`); process.exit(1); }

const json = (await res.json()) as {
  model: string;
  answers: { decision: { choice: string; probabilities: Record<string, number>; confidence: number } };
  usage?: { input_tokens: number; output_tokens: number };
};
const a = json.answers.decision;
const ranked = Object.entries(a.probabilities).sort((x, y) => y[1] - x[1]);
const margin = ranked.length > 1 ? ranked[0][1] - ranked[1][1] : ranked[0]?.[1] ?? 0;

// A winning tie option means "the options are equivalent — pick any". The close margin is
// then benign and expected, so we waive margin + confidence; irreversible still overrides.
const isTie = tieKeys.has(a.choice);
const reasons: string[] = [];
if (spec.decision.irreversible === true) reasons.push('marked irreversible/external');
if (!isTie && a.confidence < minConfidence) reasons.push(`confidence ${a.confidence.toFixed(2)} < ${minConfidence}`);
if (!isTie && margin < minMargin) reasons.push(`margin ${(margin * 100).toFixed(0)}pt < ${(minMargin * 100).toFixed(0)}pt (close race)`);
const verdict = reasons.length ? 'ESCALATE' : 'PROCEED';

console.log(`Jev (${json.model}) chose: ${a.choice}${isTie ? ' [tie: equivalent]' : ''}   (confidence ${a.confidence.toFixed(2)}, margin ${(margin * 100).toFixed(0)}pt)\n`);
console.log('distribution:');
for (const [opt, p] of ranked) console.log(`  ${(p * 100).toFixed(0).padStart(3)}%  ${opt}${opt === a.choice ? '  ←' : ''}`);
const ok = isTie ? 'options judged equivalent — pick any arbitrarily' : 'clear enough to act on unless you object';
console.log(`\nVERDICT: ${verdict}${verdict === 'ESCALATE' ? ` — human decides (${reasons.join('; ')})` : ` — ${ok}`}`);
if (json.usage) console.log(`\ntokens: in ${json.usage.input_tokens} / out ${json.usage.output_tokens}`);

// Exit 0 = PROCEED, 10 = ESCALATE — lets a caller branch on the gate.
process.exit(verdict === 'ESCALATE' ? 10 : 0);
