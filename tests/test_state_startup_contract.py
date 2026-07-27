from __future__ import annotations

import ast
import unittest
from pathlib import Path

from wild_boar_proxy import (
    state_lock,
    state_startup_contract,
    state_startup_lock,
    state_startup_recovery,
    state_startup_schema,
    state_startup_truth,
    state_temp_prefix,
    state_transaction,
)


class StateStartupContractCoreTests(unittest.TestCase):
    def empty_transaction_cleanup(
        self,
        *,
        deleted_artifact_paths: tuple[str, ...] = (),
        skipped_artifact_paths: tuple[str, ...] = (),
        stale_artifact_paths: tuple[str, ...] = (),
        incomplete_transaction_ids: tuple[str, ...] = (),
        recoverable_transaction_ids: tuple[str, ...] = (),
        blocked_transaction_ids: tuple[str, ...] = (),
        invalid_metadata_paths: tuple[str, ...] = (),
    ) -> state_transaction.TransactionTempCleanupResult:
        return state_transaction.TransactionTempCleanupResult(
            deleted_artifact_paths=deleted_artifact_paths,
            skipped_artifact_paths=skipped_artifact_paths,
            stale_artifact_paths=stale_artifact_paths,
            incomplete_transaction_ids=incomplete_transaction_ids,
            recoverable_transaction_ids=recoverable_transaction_ids,
            blocked_transaction_ids=blocked_transaction_ids,
            invalid_metadata_paths=invalid_metadata_paths,
        )

    def empty_prefix_cleanup(
        self,
        *,
        deleted_paths: tuple[str, ...] = (),
        skipped_paths: tuple[str, ...] = (),
        stale_paths: tuple[str, ...] = (),
        fresh_paths: tuple[str, ...] = (),
        blocked_paths: tuple[str, ...] = (),
        invalid_roots: tuple[str, ...] = (),
    ) -> state_temp_prefix.PrefixedTempCleanupResult:
        return state_temp_prefix.PrefixedTempCleanupResult(
            deleted_paths=deleted_paths,
            skipped_paths=skipped_paths,
            stale_paths=stale_paths,
            fresh_paths=fresh_paths,
            blocked_paths=blocked_paths,
            invalid_roots=invalid_roots,
        )

    def temp_recovery(
        self,
        *,
        outcome: str = state_startup_recovery.TEMP_RECOVERY_CLEAN,
        cleanup_performed: bool = False,
        blocking_reasons: tuple[str, ...] = (),
    ) -> state_startup_recovery.StartupTempRecoveryResult:
        transaction_cleanup = self.empty_transaction_cleanup(
            deleted_artifact_paths=("/tmp/txn.tmp",) if cleanup_performed else (),
            incomplete_transaction_ids=("txn-1",)
            if state_startup_recovery.REASON_TRANSACTION_INCOMPLETE in blocking_reasons
            else (),
            recoverable_transaction_ids=("txn-1",)
            if state_startup_recovery.REASON_TRANSACTION_RECOVERABLE in blocking_reasons
            else (),
            blocked_transaction_ids=("txn-1",)
            if state_startup_recovery.REASON_TRANSACTION_BLOCKED in blocking_reasons
            else (),
            invalid_metadata_paths=("/tmp/txn.transaction.json",)
            if state_startup_recovery.REASON_TRANSACTION_INVALID_METADATA in blocking_reasons
            else (),
        )
        prefix_cleanup = self.empty_prefix_cleanup()
        machine_error_code = {
            state_startup_recovery.TEMP_RECOVERY_CLEAN: (
                state_startup_recovery.STATE_STARTUP_TEMP_CLEAN
            ),
            state_startup_recovery.TEMP_RECOVERY_RECOVERED: (
                state_startup_recovery.STATE_STARTUP_TEMP_RECOVERED
            ),
            state_startup_recovery.TEMP_RECOVERY_BLOCKED: (
                state_startup_recovery.STATE_STARTUP_TEMP_BLOCKED
            ),
        }[outcome]
        return state_startup_recovery.StartupTempRecoveryResult(
            temp_recovery_outcome=outcome,
            machine_error_code=machine_error_code,
            cleanup_performed=cleanup_performed,
            blocking_reasons=blocking_reasons,
            transaction_cleanup=transaction_cleanup,
            prefix_cleanup=prefix_cleanup,
        )

    def lock_assessment(
        self,
        *,
        outcome: str,
        machine_error_code: str,
        reason: str,
        owner_classification: state_lock.LockOwnerClassification | None = None,
    ) -> state_startup_lock.StartupLockSliceAssessment:
        return state_startup_lock.StartupLockSliceAssessment(
            lock_slice_outcome=outcome,
            machine_error_code=machine_error_code,
            reason=reason,
            owner_classification=owner_classification,
        )

    def lock_recovery(
        self,
        *,
        outcome: str = state_startup_lock.LOCK_SLICE_RECOVERY_CLEAN,
        cleanup_performed: bool = False,
        assessment: state_startup_lock.StartupLockSliceAssessment | None = None,
        reason: str = "lock slice is clean",
        deleted_lock_path: str | None = None,
    ) -> state_startup_lock.StartupLockSliceRecoveryResult:
        machine_error_code = {
            state_startup_lock.LOCK_SLICE_RECOVERY_CLEAN: (
                state_startup_lock.STATE_STARTUP_LOCK_SLICE_RECOVERY_CLEAN
            ),
            state_startup_lock.LOCK_SLICE_RECOVERY_RECOVERED: (
                state_startup_lock.STATE_STARTUP_LOCK_SLICE_RECOVERY_RECOVERED
            ),
            state_startup_lock.LOCK_SLICE_RECOVERY_BLOCKED: (
                state_startup_lock.STATE_STARTUP_LOCK_SLICE_RECOVERY_BLOCKED
            ),
        }[outcome]
        return state_startup_lock.StartupLockSliceRecoveryResult(
            lock_slice_recovery_outcome=outcome,
            machine_error_code=machine_error_code,
            cleanup_performed=cleanup_performed,
            reason=reason,
            assessment=assessment,
            deleted_lock_path=deleted_lock_path,
        )

    def schema_assessment(
        self,
        *,
        outcome: str = state_startup_schema.SCHEMA_SLICE_CURRENT,
    ) -> state_startup_schema.StartupSchemaSliceAssessment:
        machine_error_code = {
            state_startup_schema.SCHEMA_SLICE_ABSENT: (
                state_startup_schema.STATE_STARTUP_SCHEMA_SLICE_ABSENT
            ),
            state_startup_schema.SCHEMA_SLICE_CURRENT: (
                state_startup_schema.STATE_STARTUP_SCHEMA_SLICE_CURRENT
            ),
            state_startup_schema.SCHEMA_SLICE_MIGRATABLE: (
                state_startup_schema.STATE_STARTUP_SCHEMA_SLICE_MIGRATABLE
            ),
            state_startup_schema.SCHEMA_SLICE_BLOCKED: (
                state_startup_schema.STATE_STARTUP_SCHEMA_SLICE_BLOCKED
            ),
        }[outcome]
        return state_startup_schema.StartupSchemaSliceAssessment(
            schema_slice_outcome=outcome,
            machine_error_code=machine_error_code,
            reason=outcome,
            from_schema_version=2 if outcome != state_startup_schema.SCHEMA_SLICE_ABSENT else None,
            target_schema_version=2,
            migration_path_available=(
                outcome == state_startup_schema.SCHEMA_SLICE_MIGRATABLE
            ),
            legacy_bootstrap_required=False,
        )

    def truth_assessment(
        self,
        *,
        outcome: str = state_startup_truth.TRUTH_SLICE_CONSISTENT,
    ) -> state_startup_truth.StartupTruthSliceAssessment:
        machine_error_code = {
            state_startup_truth.TRUTH_SLICE_CONSISTENT: (
                state_startup_truth.STATE_STARTUP_TRUTH_SLICE_CONSISTENT
            ),
            state_startup_truth.TRUTH_SLICE_PARTIAL: (
                state_startup_truth.STATE_STARTUP_TRUTH_SLICE_PARTIAL
            ),
            state_startup_truth.TRUTH_SLICE_CONTRADICTED: (
                state_startup_truth.STATE_STARTUP_TRUTH_SLICE_CONTRADICTED
            ),
            state_startup_truth.TRUTH_SLICE_BLOCKED: (
                state_startup_truth.STATE_STARTUP_TRUTH_SLICE_BLOCKED
            ),
        }[outcome]
        contradiction_fields = ("effective_mode",) if outcome == state_startup_truth.TRUTH_SLICE_CONTRADICTED else ()
        return state_startup_truth.StartupTruthSliceAssessment(
            truth_slice_outcome=outcome,
            machine_error_code=machine_error_code,
            reason=outcome,
            registry_present=True,
            supervisor_state_present=True,
            effective_mode_artifact_present=outcome != state_startup_truth.TRUTH_SLICE_PARTIAL,
            selected_backend_snapshot_present=False,
            contradiction_fields=contradiction_fields,
        )

    def aggregate(
        self,
        *,
        temp_recovery: state_startup_recovery.StartupTempRecoveryResult | None = None,
        lock_recovery: state_startup_lock.StartupLockSliceRecoveryResult | None = None,
        schema_assessment: state_startup_schema.StartupSchemaSliceAssessment | None = None,
        truth_assessment: state_startup_truth.StartupTruthSliceAssessment | None = None,
    ) -> state_startup_contract.StartupContractCoreResult:
        return state_startup_contract.aggregate_startup_contract_core(
            temp_recovery=self.temp_recovery() if temp_recovery is None else temp_recovery,
            lock_recovery=self.lock_recovery() if lock_recovery is None else lock_recovery,
            schema_assessment=(
                self.schema_assessment() if schema_assessment is None else schema_assessment
            ),
            truth_assessment=(
                self.truth_assessment() if truth_assessment is None else truth_assessment
            ),
        )

    def test_all_clean_slices_return_clean_startup_contract(self) -> None:
        result = self.aggregate()

        self.assertEqual(
            result.startup_contract_outcome,
            state_startup_contract.STARTUP_CONTRACT_CLEAN,
        )
        self.assertEqual(
            result.machine_error_code,
            state_startup_contract.STATE_STARTUP_CONTRACT_CLEAN,
        )
        self.assertFalse(result.cleanup_performed)
        self.assertEqual(result.blocking_reasons, ())

    def test_temp_recovered_with_clean_other_slices_returns_auto_recovered(self) -> None:
        result = self.aggregate(
            temp_recovery=self.temp_recovery(
                outcome=state_startup_recovery.TEMP_RECOVERY_RECOVERED,
                cleanup_performed=True,
            )
        )

        self.assertEqual(
            result.startup_contract_outcome,
            state_startup_contract.STARTUP_CONTRACT_AUTO_RECOVERED,
        )
        self.assertTrue(result.cleanup_performed)

    def test_lock_recovered_with_clean_other_slices_returns_auto_recovered(self) -> None:
        result = self.aggregate(
            lock_recovery=self.lock_recovery(
                outcome=state_startup_lock.LOCK_SLICE_RECOVERY_RECOVERED,
                cleanup_performed=True,
                deleted_lock_path="/tmp/wild-boar-proxy.lock",
            )
        )

        self.assertEqual(
            result.startup_contract_outcome,
            state_startup_contract.STARTUP_CONTRACT_AUTO_RECOVERED,
        )
        self.assertTrue(result.cleanup_performed)

    def test_temp_and_lock_recovered_return_auto_recovered(self) -> None:
        result = self.aggregate(
            temp_recovery=self.temp_recovery(
                outcome=state_startup_recovery.TEMP_RECOVERY_RECOVERED,
                cleanup_performed=True,
            ),
            lock_recovery=self.lock_recovery(
                outcome=state_startup_lock.LOCK_SLICE_RECOVERY_RECOVERED,
                cleanup_performed=True,
                deleted_lock_path="/tmp/wild-boar-proxy.lock",
            ),
        )

        self.assertEqual(
            result.startup_contract_outcome,
            state_startup_contract.STARTUP_CONTRACT_AUTO_RECOVERED,
        )
        self.assertTrue(result.cleanup_performed)

    def test_temp_blocked_returns_blocked_contract(self) -> None:
        result = self.aggregate(
            temp_recovery=self.temp_recovery(
                outcome=state_startup_recovery.TEMP_RECOVERY_BLOCKED,
                blocking_reasons=(state_startup_recovery.REASON_TRANSACTION_INCOMPLETE,),
            )
        )

        self.assertEqual(
            result.startup_contract_outcome,
            state_startup_contract.STARTUP_CONTRACT_BLOCKED,
        )
        self.assertEqual(
            result.machine_error_code,
            state_startup_contract.STATE_STARTUP_CONTRACT_BLOCKED,
        )
        self.assertIn(
            state_startup_recovery.REASON_TRANSACTION_INCOMPLETE,
            result.blocking_reasons,
        )

    def test_lock_blocked_returns_blocked_contract(self) -> None:
        assessment = self.lock_assessment(
            outcome=state_startup_lock.LOCK_SLICE_SUSPICIOUS,
            machine_error_code=state_startup_lock.STATE_STARTUP_LOCK_SLICE_SUSPICIOUS,
            reason="lock owner metadata is suspicious",
        )
        result = self.aggregate(
            lock_recovery=self.lock_recovery(
                outcome=state_startup_lock.LOCK_SLICE_RECOVERY_BLOCKED,
                assessment=assessment,
                reason=assessment.reason,
            )
        )

        self.assertEqual(
            result.startup_contract_outcome,
            state_startup_contract.STARTUP_CONTRACT_BLOCKED,
        )
        self.assertIn(state_startup_lock.LOCK_SLICE_SUSPICIOUS, result.blocking_reasons)

    def test_lock_blocked_without_assessment_uses_generic_reason(self) -> None:
        result = self.aggregate(
            lock_recovery=self.lock_recovery(
                outcome=state_startup_lock.LOCK_SLICE_RECOVERY_BLOCKED,
                assessment=None,
                reason="existing admitted control-owned lock file requires same-source assessment facts",
            )
        )

        self.assertEqual(
            result.startup_contract_outcome,
            state_startup_contract.STARTUP_CONTRACT_BLOCKED,
        )
        self.assertIn(
            state_startup_contract.REASON_LOCK_RECOVERY_BLOCKED,
            result.blocking_reasons,
        )

    def test_truth_partial_returns_blocked_contract(self) -> None:
        result = self.aggregate(
            truth_assessment=self.truth_assessment(
                outcome=state_startup_truth.TRUTH_SLICE_PARTIAL
            )
        )

        self.assertEqual(
            result.startup_contract_outcome,
            state_startup_contract.STARTUP_CONTRACT_BLOCKED,
        )
        self.assertIn(state_startup_truth.TRUTH_SLICE_PARTIAL, result.blocking_reasons)

    def test_truth_contradicted_returns_blocked_contract(self) -> None:
        result = self.aggregate(
            truth_assessment=self.truth_assessment(
                outcome=state_startup_truth.TRUTH_SLICE_CONTRADICTED
            )
        )

        self.assertEqual(
            result.startup_contract_outcome,
            state_startup_contract.STARTUP_CONTRACT_BLOCKED,
        )
        self.assertIn(
            state_startup_truth.TRUTH_SLICE_CONTRADICTED,
            result.blocking_reasons,
        )

    def test_truth_blocked_returns_blocked_contract(self) -> None:
        result = self.aggregate(
            truth_assessment=self.truth_assessment(
                outcome=state_startup_truth.TRUTH_SLICE_BLOCKED
            )
        )

        self.assertEqual(
            result.startup_contract_outcome,
            state_startup_contract.STARTUP_CONTRACT_BLOCKED,
        )
        self.assertIn(state_startup_truth.TRUTH_SLICE_BLOCKED, result.blocking_reasons)

    def test_schema_absent_returns_blocked_contract(self) -> None:
        result = self.aggregate(
            schema_assessment=self.schema_assessment(
                outcome=state_startup_schema.SCHEMA_SLICE_ABSENT
            )
        )

        self.assertEqual(
            result.startup_contract_outcome,
            state_startup_contract.STARTUP_CONTRACT_BLOCKED,
        )
        self.assertIn(state_startup_schema.SCHEMA_SLICE_ABSENT, result.blocking_reasons)

    def test_schema_migratable_returns_blocked_contract(self) -> None:
        result = self.aggregate(
            schema_assessment=self.schema_assessment(
                outcome=state_startup_schema.SCHEMA_SLICE_MIGRATABLE
            )
        )

        self.assertEqual(
            result.startup_contract_outcome,
            state_startup_contract.STARTUP_CONTRACT_BLOCKED,
        )
        self.assertIn(
            state_startup_schema.SCHEMA_SLICE_MIGRATABLE,
            result.blocking_reasons,
        )

    def test_cleanup_performed_remains_true_when_schema_still_blocks(self) -> None:
        result = self.aggregate(
            temp_recovery=self.temp_recovery(
                outcome=state_startup_recovery.TEMP_RECOVERY_RECOVERED,
                cleanup_performed=True,
            ),
            schema_assessment=self.schema_assessment(
                outcome=state_startup_schema.SCHEMA_SLICE_MIGRATABLE
            ),
        )

        self.assertEqual(
            result.startup_contract_outcome,
            state_startup_contract.STARTUP_CONTRACT_BLOCKED,
        )
        self.assertTrue(result.cleanup_performed)
        self.assertIn(
            state_startup_schema.SCHEMA_SLICE_MIGRATABLE,
            result.blocking_reasons,
        )

    def test_schema_blocked_returns_blocked_contract(self) -> None:
        result = self.aggregate(
            schema_assessment=self.schema_assessment(
                outcome=state_startup_schema.SCHEMA_SLICE_BLOCKED
            )
        )

        self.assertEqual(
            result.startup_contract_outcome,
            state_startup_contract.STARTUP_CONTRACT_BLOCKED,
        )
        self.assertIn(state_startup_schema.SCHEMA_SLICE_BLOCKED, result.blocking_reasons)

    def test_result_dataclass_does_not_expose_packet_startup_or_rollback_fields(self) -> None:
        field_names = set(state_startup_contract.StartupContractCoreResult.__dataclass_fields__)
        forbidden = {
            "status",
            "effect",
            "exit_code",
            "human_message",
            "next_action",
            "operator_action",
            "changed_files",
            "startup_clean",
            "auto_recovered",
            "repair_required",
            "rollback_available",
            "rollback_id",
        }
        self.assertTrue(forbidden.isdisjoint(field_names))

    def test_module_does_not_import_runtime_or_cli_layers(self) -> None:
        source = Path(state_startup_contract.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

        forbidden = {
            "wild_boar_proxy.runtime",
            "wild_boar_proxy.operator_surface",
            "wild_boar_proxy.cli",
            "wild_boar_proxy.web_design_live_server",
            "wild_boar_proxy.command_effects",
        }
        self.assertTrue(forbidden.isdisjoint(imported_modules))


if __name__ == "__main__":
    unittest.main()
