from unittest.mock import patch

from service import ai_management_service


def test_model_list_is_synchronized_before_return():
    catalog = {"models": [{"id": "run-a"}], "selectedModelId": "run-a"}
    with patch.object(ai_management_service.ai_client, "get_ai_models", return_value=catalog):
        with patch.object(ai_management_service.model_catalog_repository, "sync_model_catalog") as sync:
            with patch.object(ai_management_service.model_catalog_repository, "sync_reviewed_class_metrics"):
                with patch.object(ai_management_service.model_catalog_repository, "apply_candidate_flags", side_effect=lambda value: value):
                    result = ai_management_service.get_models()
    sync.assert_called_once_with(catalog)
    assert result is catalog


def test_model_detail_registers_catalog_and_class_metrics():
    catalog = {"models": [{"id": "run-a"}]}
    detail = {"id": "run-a", "classMetrics": [{"className": "bottle", "accuracy": 0.8}]}
    with patch.object(ai_management_service.ai_client, "get_ai_models", return_value=catalog):
        with patch.object(ai_management_service.ai_client, "get_ai_model_detail", return_value=detail):
            with patch.object(ai_management_service.model_catalog_repository, "sync_model_catalog") as sync_catalog:
                with patch.object(ai_management_service.model_catalog_repository, "sync_model_detail") as sync_detail:
                    with patch.object(ai_management_service.model_catalog_repository, "sync_reviewed_class_metrics"):
                        with patch.object(ai_management_service.model_catalog_repository, "find_model_class_metrics", return_value=detail["classMetrics"]):
                            result = ai_management_service.get_model_detail("run-a")
    sync_catalog.assert_called_once_with(catalog)
    sync_detail.assert_called_once_with(detail)
    assert result is detail


def test_gpu_status_is_upserted_before_return():
    system = {"host": "gpu-host", "gpus": [{"index": 0, "name": "GPU"}]}
    with patch.object(ai_management_service.ai_client, "get_ai_system", return_value=system):
        with patch.object(ai_management_service.model_catalog_repository, "sync_gpu_status") as sync:
            result = ai_management_service.get_system()
    sync.assert_called_once_with(system)
    assert result is system

def test_candidate_state_is_persisted_and_refreshed():
    refreshed = {"models": [{"id": "run-a", "isCandidate": True}]}
    with patch.object(ai_management_service.model_catalog_repository, "set_model_candidate", return_value=True) as persist:
        with patch.object(ai_management_service, "get_models", return_value=refreshed) as reload_models:
            result = ai_management_service.set_model_candidate("run-a", True)
    persist.assert_called_once_with("run-a", True)
    reload_models.assert_called_once_with()
    assert result is refreshed

def test_multiple_candidates_are_persisted_in_one_operation():
    refreshed = {"models": [{"id": "run-a", "isCandidate": True}, {"id": "run-b", "isCandidate": True}]}
    with patch.object(ai_management_service.model_catalog_repository, "set_model_candidates", return_value=2) as persist:
        with patch.object(ai_management_service, "get_models", return_value=refreshed):
            result = ai_management_service.set_model_candidates(["run-a", "run-b"], True)
    persist.assert_called_once_with(["run-a", "run-b"], True)
    assert result is refreshed
