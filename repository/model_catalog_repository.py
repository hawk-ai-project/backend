"""Persistence for AI experiment, per-class metric, and GPU catalog data."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pymysql

from common.db import engine, fetch_query


def _datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None

def _json(value: Any) -> str | None:
    return json.dumps(value, ensure_ascii=False) if value is not None else None


def sync_model_catalog(catalog: dict[str, Any]) -> None:
    models = catalog.get("models") or []
    selected_id = catalog.get("selectedModelId")
    connection = engine.raw_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("UPDATE ai_models SET is_selected=FALSE WHERE is_selected=TRUE")
            for model in models:
                metrics = model.get("metrics") or {}
                cursor.execute(
                    """INSERT INTO ai_models
                    (external_id,name,run_path,runs_directory,base_model,optimizer,epochs,image_size,
                     batch_size,device,precision_score,recall_score,map50,map50_95,train_box_loss,
                     val_box_loss,has_weights,weight_path,artifact_count,is_selected,source_updated_at,
                     config_json,artifacts_json,files_json,last_synced_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                            %s,%s,%s,UTC_TIMESTAMP(6))
                    ON DUPLICATE KEY UPDATE name=VALUES(name),run_path=VALUES(run_path),
                    runs_directory=VALUES(runs_directory),base_model=VALUES(base_model),optimizer=VALUES(optimizer),
                    epochs=VALUES(epochs),image_size=VALUES(image_size),batch_size=VALUES(batch_size),
                    device=VALUES(device),precision_score=VALUES(precision_score),recall_score=VALUES(recall_score),
                    map50=VALUES(map50),map50_95=VALUES(map50_95),train_box_loss=VALUES(train_box_loss),
                    val_box_loss=VALUES(val_box_loss),has_weights=VALUES(has_weights),weight_path=VALUES(weight_path),
                    artifact_count=VALUES(artifact_count),is_selected=VALUES(is_selected),
                    source_updated_at=VALUES(source_updated_at),config_json=COALESCE(VALUES(config_json),config_json),
                    artifacts_json=COALESCE(VALUES(artifacts_json),artifacts_json),
                    files_json=COALESCE(VALUES(files_json),files_json),last_synced_at=UTC_TIMESTAMP(6)""",
                    (
                        model.get("id"), model.get("name") or model.get("id"), model.get("path"),
                        catalog.get("runsDirectory"), model.get("model"), model.get("optimizer"),
                        model.get("epochs"), model.get("imageSize"), model.get("batch"), model.get("device"),
                        metrics.get("precision"), metrics.get("recall"), metrics.get("map50"),
                        metrics.get("map50_95"), metrics.get("train_box_loss"), metrics.get("val_box_loss"),
                        bool(model.get("hasWeights")), model.get("weightPath"), model.get("artifactCount") or 0,
                        model.get("id") == selected_id, _datetime(model.get("updatedAt")), _json(model.get("config")),
                        _json(model.get("artifacts")), _json(model.get("files")),
                    ),
                )
                cursor.execute("SELECT id FROM ai_models WHERE external_id=%s", (model.get("id"),))
                row = cursor.fetchone()
                if row:
                    _replace_class_metrics(cursor, row["id"], model.get("classMetrics") or [])
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def apply_candidate_flags(catalog: dict[str, Any]) -> dict[str, Any]:
    rows = fetch_query("SELECT external_id FROM ai_models WHERE is_candidate=TRUE") or []
    candidate_ids = {row["external_id"] for row in rows}
    for model in catalog.get("models") or []:
        model["isCandidate"] = model.get("id") in candidate_ids
    catalog["candidateModelIds"] = sorted(candidate_ids)
    return catalog


def set_model_candidates(external_ids: list[str], candidate: bool) -> int:
    unique_ids = list(dict.fromkeys(external_ids))
    placeholders = ",".join(["%s"] * len(unique_ids))
    connection = engine.raw_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE ai_models SET is_candidate=%s,updated_at=UTC_TIMESTAMP(6) WHERE external_id IN ({placeholders})",
                tuple([candidate, *unique_ids]),
            )
            affected = cursor.rowcount
        connection.commit()
        return affected
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

def set_model_candidate(external_id: str, candidate: bool) -> bool:
    connection = engine.raw_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE ai_models SET is_candidate=%s,updated_at=UTC_TIMESTAMP(6) WHERE external_id=%s",
                (candidate, external_id),
            )
            affected = cursor.rowcount
        connection.commit()
        return affected > 0
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

def sync_model_detail(detail: dict[str, Any]) -> None:
    external_id = detail.get("id")
    if not external_id:
        return
    connection = engine.raw_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            metrics = detail.get("metrics") or {}
            cursor.execute(
                """UPDATE ai_models SET name=COALESCE(%s,name),precision_score=COALESCE(%s,precision_score),
                recall_score=COALESCE(%s,recall_score),map50=COALESCE(%s,map50),map50_95=COALESCE(%s,map50_95),
                config_json=%s,artifacts_json=%s,files_json=%s,last_synced_at=UTC_TIMESTAMP(6)
                WHERE external_id=%s""",
                (detail.get("name"), metrics.get("precision"), metrics.get("recall"), metrics.get("map50"),
                 metrics.get("map50_95"), _json(detail.get("config")), _json(detail.get("artifacts")),
                 _json(detail.get("files")), external_id),
            )
            cursor.execute("SELECT id FROM ai_models WHERE external_id=%s", (external_id,))
            row = cursor.fetchone()
            if row:
                _replace_class_metrics(cursor, row["id"], detail.get("classMetrics") or [])
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _replace_class_metrics(cursor, model_id: int, metrics: list[dict[str, Any]]) -> None:
    if not metrics:
        return
    cursor.execute("DELETE FROM ai_model_class_metrics WHERE model_id=%s", (model_id,))
    for metric in metrics:
        class_name = metric.get("className") or metric.get("name")
        if not class_name:
            continue
        cursor.execute(
            """INSERT INTO ai_model_class_metrics
            (model_id,class_name,class_index,accuracy,precision_score,recall_score,map50,map50_95,
             true_positives,false_positives,false_negatives,support,measured_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,UTC_TIMESTAMP(6))""",
            (model_id, str(class_name)[:100], metric.get("classIndex"), metric.get("accuracy"),
             metric.get("precision"), metric.get("recall"), metric.get("map50"), metric.get("map50_95"),
             metric.get("truePositives"), metric.get("falsePositives"), metric.get("falseNegatives"),
             metric.get("support")),
        )


def sync_reviewed_class_metrics() -> None:
    """Fill missing validation metrics from human-reviewed production detections."""
    rows = fetch_query(
        """SELECT grouped.modelId,wt.name_ko AS className,grouped.classId,
        SUM(grouped.tp) AS tp,SUM(grouped.fp) AS fp,SUM(grouped.fn) AS fn
        FROM (
          SELECT m.id AS modelId,d.waste_type_id AS classId,
          SUM(d.review_result='TRUE_POSITIVE') AS tp,
          SUM(d.review_result='FALSE_POSITIVE') AS fp,0 AS fn
          FROM detections d JOIN detection_runs r ON r.id=d.detection_run_id
          JOIN ai_models m ON (m.name=r.model_name OR m.external_id=r.model_name OR m.name=r.model_version)
          WHERE d.review_result IN ('TRUE_POSITIVE','FALSE_POSITIVE')
          GROUP BY m.id,d.waste_type_id
          UNION ALL
          SELECT m.id AS modelId,COALESCE(d.actual_waste_type_id,d.waste_type_id) AS classId,
          0 AS tp,0 AS fp,COUNT(*) AS fn
          FROM detections d JOIN detection_runs r ON r.id=d.detection_run_id
          JOIN ai_models m ON (m.name=r.model_name OR m.external_id=r.model_name OR m.name=r.model_version)
          WHERE d.review_result='FALSE_NEGATIVE'
          GROUP BY m.id,COALESCE(d.actual_waste_type_id,d.waste_type_id)
        ) grouped JOIN waste_types wt ON wt.id=grouped.classId
        GROUP BY grouped.modelId,wt.name_ko,grouped.classId"""
    ) or []
    connection = engine.raw_connection()
    try:
        with connection.cursor() as cursor:
            for row in rows:
                tp, fp, fn = int(row["tp"] or 0), int(row["fp"] or 0), int(row["fn"] or 0)
                precision = tp / (tp + fp) if tp + fp else 0.0
                recall = tp / (tp + fn) if tp + fn else 0.0
                accuracy = tp / (tp + fp + fn) if tp + fp + fn else 0.0
                cursor.execute(
                    """INSERT INTO ai_model_class_metrics
                    (model_id,class_name,accuracy,precision_score,recall_score,true_positives,
                     false_positives,false_negatives,support,metric_source,measured_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'OPERATIONAL_REVIEW',UTC_TIMESTAMP(6))
                    ON DUPLICATE KEY UPDATE
                    accuracy=IF(metric_source='OPERATIONAL_REVIEW',VALUES(accuracy),accuracy),
                    precision_score=IF(metric_source='OPERATIONAL_REVIEW',VALUES(precision_score),precision_score),
                    recall_score=IF(metric_source='OPERATIONAL_REVIEW',VALUES(recall_score),recall_score),
                    true_positives=IF(metric_source='OPERATIONAL_REVIEW',VALUES(true_positives),true_positives),
                    false_positives=IF(metric_source='OPERATIONAL_REVIEW',VALUES(false_positives),false_positives),
                    false_negatives=IF(metric_source='OPERATIONAL_REVIEW',VALUES(false_negatives),false_negatives),
                    support=IF(metric_source='OPERATIONAL_REVIEW',VALUES(support),support),
                    measured_at=IF(metric_source='OPERATIONAL_REVIEW',UTC_TIMESTAMP(6),measured_at)""",
                    (row["modelId"], row["className"], accuracy, precision, recall, tp, fp, fn, tp + fn),
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

def sync_gpu_status(system: dict[str, Any]) -> None:
    host = str(system.get("host") or "unknown")[:255]
    gpus = system.get("gpus") or []
    connection = engine.raw_connection()
    try:
        with connection.cursor() as cursor:
            for gpu in gpus:
                cursor.execute(
                    """INSERT INTO ai_gpu_devices
                    (host_name,device_index,device_name,temperature_c,utilization_percent,memory_total_mib,
                     memory_used_mib,memory_free_mib,power_draw_w,power_limit_w,cuda_available,
                     system_timestamp,last_synced_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,UTC_TIMESTAMP(6))
                    ON DUPLICATE KEY UPDATE device_name=VALUES(device_name),temperature_c=VALUES(temperature_c),
                    utilization_percent=VALUES(utilization_percent),memory_total_mib=VALUES(memory_total_mib),
                    memory_used_mib=VALUES(memory_used_mib),memory_free_mib=VALUES(memory_free_mib),
                    power_draw_w=VALUES(power_draw_w),power_limit_w=VALUES(power_limit_w),
                    cuda_available=VALUES(cuda_available),system_timestamp=VALUES(system_timestamp),
                    last_synced_at=UTC_TIMESTAMP(6)""",
                    (host, int(float(gpu.get("index", 0))), gpu.get("name"), gpu.get("temperatureC"),
                     gpu.get("utilizationPercent"), gpu.get("memoryTotalMiB"), gpu.get("memoryUsedMiB"),
                     gpu.get("memoryFreeMiB"), gpu.get("powerDrawW"), gpu.get("powerLimitW"),
                     bool((system.get("torchCuda") or {}).get("available")), _datetime(system.get("timestamp"))),
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def find_model_class_metrics(external_id: str) -> list[dict[str, Any]]:
    rows = fetch_query(
        """SELECT cm.class_name AS className,cm.class_index AS classIndex,cm.accuracy,
        cm.precision_score AS `precision`,cm.recall_score AS `recall`,cm.map50,cm.map50_95,
        cm.true_positives AS truePositives,cm.false_positives AS falsePositives,
        cm.false_negatives AS falseNegatives,cm.support,cm.metric_source AS metricSource
        FROM ai_model_class_metrics cm JOIN ai_models m ON m.id=cm.model_id
        WHERE m.external_id=%s ORDER BY cm.class_index,cm.class_name""", (external_id,),
    )
    return rows if isinstance(rows, list) else []

def model_recommendation_context() -> str:
    models = fetch_query(
        """SELECT id,external_id,name,base_model,optimizer,epochs,image_size,batch_size,device,
        precision_score,recall_score,map50,map50_95,has_weights,is_selected,source_updated_at
        FROM ai_models ORDER BY is_selected DESC,map50_95 DESC,map50 DESC,last_synced_at DESC"""
    ) or []
    if not models:
        return "저장된 AI 모델 정보가 없습니다."
    ids = [model["id"] for model in models]
    placeholders = ",".join(["%s"] * len(ids))
    class_rows = fetch_query(
        f"""SELECT model_id,class_name,accuracy,precision_score,recall_score,map50,map50_95,support
        FROM ai_model_class_metrics WHERE model_id IN ({placeholders})
        ORDER BY model_id,accuracy DESC,class_name""", tuple(ids),
    ) or []
    by_model: dict[int, list[dict[str, Any]]] = {}
    for row in class_rows:
        by_model.setdefault(row["model_id"], []).append(row)
    lines = ["DB에 동기화된 객체 탐지 모델 카탈로그입니다. 사용자 목적과 클래스별 성능을 비교해 추천하세요."]
    for model in models:
        lines.append(
            f"- 모델 {model['name']} (ID: {model['external_id']}): base={model.get('base_model') or '-'}, "
            f"mAP50={model.get('map50')}, mAP50-95={model.get('map50_95')}, "
            f"precision={model.get('precision_score')}, recall={model.get('recall_score')}, "
            f"weights={bool(model.get('has_weights'))}, selected={bool(model.get('is_selected'))}, "
            f"img={model.get('image_size')}, batch={model.get('batch_size')}, device={model.get('device') or '-'}"
        )
        for metric in by_model.get(model["id"], []):
            lines.append(
                f"  - 클래스 {metric['class_name']}: accuracy={metric.get('accuracy')}, "
                f"precision={metric.get('precision_score')}, recall={metric.get('recall_score')}, "
                f"mAP50={metric.get('map50')}, mAP50-95={metric.get('map50_95')}, support={metric.get('support')}"
            )
    return "\n".join(lines)