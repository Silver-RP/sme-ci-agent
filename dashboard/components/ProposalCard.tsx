"use client";

/** What the person is deciding on, shown right above the Approve/Reject buttons. Reads the pending interrupt. */

type Obj = Record<string, unknown>;

const isObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);
const text = (v: unknown): string => (v === undefined || v === null ? "" : typeof v === "string" ? v : JSON.stringify(v));

function Row({ label, value, testId }: { label: string; value: string; testId: string }) {
  if (value === "") return null;
  return (
    <p>
      <strong>{label}:</strong> <span data-testid={testId}>{value}</span>
    </p>
  );
}

export function ProposalCard({ pending }: { pending: Obj }) {
  const kind = pending.kind === "rollback" ? "rollback" : pending.kind === "halt" ? "halt" : "proposal";
  const proposal = isObj(pending.proposal) ? pending.proposal : {};
  const sop = isObj(proposal.sop_proposal) ? proposal.sop_proposal : null;
  const current = isObj(pending.current_sop) ? pending.current_sop : null;
  const kpi = isObj(proposal.expected_kpi) ? proposal.expected_kpi : null;
  const kpiText = kpi
    ? [kpi.kpi, kpi.direction, kpi.target !== undefined ? `target ${text(kpi.target)}` : ""].filter((x) => x !== undefined && x !== "").map(text).join(" ")
    : "";
  if (kind === "halt") {
    return (
      <div data-testid="proposal-card" data-kind="halt">
        <h2 data-testid="approval-title">Run stopped, waiting for you</h2>
        <Row label="Reason" value={text(pending.reason)} testId="halt-reason" />
        <p data-testid="halt-explain">
          Investigate again (you can add information in Reason) or finish the run. Nothing changes until you choose.
        </p>
        {pending.sop_still_in_force === true && (
          <p data-testid="sop-in-force">
            The SOP applied earlier ({text(pending.sop_id)}
            {pending.sop_version !== undefined && pending.sop_version !== null ? ` v${text(pending.sop_version)}` : ""}) is still
            in force.
          </p>
        )}
      </div>
    );
  }
  return (
    <div data-testid="proposal-card" data-kind={kind}>
      <h2 data-testid="approval-title">{kind === "rollback" ? "Confirm rollback" : "Review proposal"}</h2>
      {kind === "rollback" && (
        <p data-testid="rollback-explain">
          The KPI after the applied change did not meet the threshold. Approving restores the previous SOP content as a
          new version. Rejecting keeps the applied SOP in force.
        </p>
      )}
      <Row label="Change" value={text(proposal.change)} testId="proposal-change" />
      <Row label="Rationale" value={text(proposal.rationale)} testId="proposal-rationale" />
      <Row label="Expected KPI" value={kpiText} testId="proposal-kpi" />
      {sop && (
        <div data-testid="sop-diff">
          <p>
            <strong>SOP {text(sop.sop_id)}</strong>
            {current?.version !== undefined ? ` (now v${text(current.version)})` : ""}
          </p>
          <p>Current:</p>
          <pre data-testid="sop-old">{current ? text(current.content) : "(not available)"}</pre>
          <p>Proposed:</p>
          <pre data-testid="sop-new">{text(sop.new_content)}</pre>
        </div>
      )}
    </div>
  );
}
