<!--
@file: SCHEDULER_CLEANUP.md
@description: Proposal for scheduler task cleanup
@dependencies: workers/task_manager.py
@created: 2025-09-15
-->

# Scheduler Cleanup Proposal

- Define a predicate to mark tasks as stale.
- Implement idempotent garbage collection in `workers/task_manager.py`.
- Expose metrics for cleanup operations.
