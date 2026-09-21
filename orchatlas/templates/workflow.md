# OrchAtlas workflow

Use this workflow for a substantial implementation request in a project configured
with OrchAtlas. Keep trivial edits in the current thread. An explicit request for
single-agent work takes precedence. Worker and reviewer children execute their
assignment instead of starting this workflow again.

1. Read the project guidance and record the current workspace baseline, including
   existing changes. Define the objective, acceptance criteria, allowed paths and
   verification commands. Resolve missing product decisions before dispatch.
2. Give one ${builder} a coherent implementation bundle, the baseline and required
   contracts. Ask it to own discovery, implementation, tests and corrections inside
   that scope, returning changed paths, check results and remaining risks.
3. Let the worker finish using the host's native continuation/wait tools. Preserve
   the user's progress visibility. Keep one active writer; the coordinator does not
   edit the same paths while that writer owns the task.
4. ${review_step}
5. Send actionable findings to the same builder in one batch. Allow at most
   ${max_fix_rounds} correction round(s), then reassess with the user if acceptance
   still fails. This bound never turns failing work into accepted work.
6. Accept only when the actual patch meets the contract and relevant checks have
   evidence. Report changes, verification and limitations. For interrupted work,
   retain a compact checkpoint of the baseline, decisions, completed work and next
   action using the project's existing convention.

Use the native agents below and retain the project's permissions and existing
authorization. A configured model is not proof of runtime routing; identify the
model/provider from host metadata when available and otherwise report unverified.
If an agent or model is unavailable, stop that delegation and explain the missing
prerequisite. A different model/provider requires an explicit user choice.

An implementation request does not itself authorize publishing, deployments or
production migrations. These instructions guide the agent; they do not enforce
a monetary budget, filesystem isolation or deterministic scheduling.
