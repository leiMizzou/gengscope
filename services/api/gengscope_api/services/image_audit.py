from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, ImageStat
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from gengscope_api.db.models import AlgorithmicSignal, EvidencePointer, Paper, ReviewTask, SourceArtifact
from gengscope_api.services.artifacts import IMAGE_ARTIFACT_TYPES


ANALYZER_NAME = "gengscope.image"
ANALYZER_VERSION = "0.3.0"
TERMINAL_SIGNAL_STATUSES = {"confirmed_signal", "false_positive", "not_actionable", "promoted_to_event"}
CORRELATION_CHANNELS = ("gray", "red", "green", "blue")


def run_image_audit(
    db: Session,
    *,
    artifact_id: str,
    compare_artifact_ids: list[str] | None = None,
    max_hamming_distance: int = 10,
    enable_patch_similarity: bool = True,
    max_patch_hamming_distance: int = 6,
    patch_grid_size: int = 4,
    min_patch_stddev: float = 8.0,
    enable_shift_correlation: bool = True,
    min_shift_correlation: float = 0.86,
    max_shift_fraction: float = 0.18,
    correlation_size: int = 64,
    create_review_tasks: bool = True,
    priority: int = 8,
) -> dict[str, Any]:
    artifact = db.get(SourceArtifact, artifact_id)
    if artifact is None:
        raise LookupError(f"No artifact found for id {artifact_id}")
    if not _is_image_artifact(artifact):
        raise ValueError("image audit requires an image artifact")
    paper = db.get(Paper, artifact.paper_id)
    if paper is None:
        raise LookupError(f"No paper found for artifact {artifact_id}")

    peers = _peer_artifacts(db, artifact, compare_artifact_ids)
    target_image = _load_image(_artifact_path(artifact))
    target_hashes = _image_hash_variants(target_image)
    findings = []
    for peer in peers:
        peer_image = _load_image(_artifact_path(peer))
        peer_hash = _average_hash(peer_image)
        best = min(
            (
                {
                    "transform": transform,
                    "distance": _hamming_distance(target_hash, peer_hash),
                    "peer": peer,
                }
                for transform, target_hash in target_hashes.items()
            ),
            key=lambda item: item["distance"],
        )
        if best["distance"] <= max_hamming_distance:
            findings.append(_finding(artifact, peer, best["transform"], best["distance"], max_hamming_distance))
            continue
        if enable_patch_similarity:
            patch_finding = _patch_similarity_finding(
                artifact,
                target_image,
                peer,
                peer_image,
                max_patch_hamming_distance=max_patch_hamming_distance,
                patch_grid_size=patch_grid_size,
                min_patch_stddev=min_patch_stddev,
            )
            if patch_finding:
                findings.append(patch_finding)
                continue
        if enable_shift_correlation:
            correlation_finding = _shift_correlation_finding(
                artifact,
                target_image,
                peer,
                peer_image,
                min_shift_correlation=min_shift_correlation,
                max_shift_fraction=max_shift_fraction,
                correlation_size=correlation_size,
                min_patch_stddev=min_patch_stddev,
            )
            if correlation_finding:
                findings.append(correlation_finding)

    signals: list[AlgorithmicSignal] = []
    created_review_tasks = 0
    for finding in findings[:20]:
        signal, created_task = _upsert_signal(db, paper, artifact, finding, create_review_tasks, priority)
        signals.append(signal)
        created_review_tasks += int(created_task)

    paper.audit_status = "in_review" if signals else "reviewed"
    db.commit()
    for signal in signals:
        db.refresh(signal)
    return {
        "artifact_id": artifact.id,
        "paper_id": paper.id,
        "compared_artifact_count": len(peers),
        "signal_count": len(signals),
        "created_review_tasks": created_review_tasks,
        "signals": [_signal_dict(signal) for signal in signals],
        "conclusion_boundary": "图像审计只产生 algorithmic_signal，用于排序和人工复核，不能单独证明论文或作者造假。",
    }


def _peer_artifacts(db: Session, artifact: SourceArtifact, compare_artifact_ids: list[str] | None) -> list[SourceArtifact]:
    if compare_artifact_ids:
        peers = db.scalars(select(SourceArtifact).where(SourceArtifact.id.in_(compare_artifact_ids))).all()
    else:
        peers = db.scalars(select(SourceArtifact).where(SourceArtifact.paper_id == artifact.paper_id, SourceArtifact.id != artifact.id)).all()
    return [peer for peer in peers if peer.id != artifact.id and _is_image_artifact(peer)]


def _is_image_artifact(artifact: SourceArtifact) -> bool:
    if artifact.artifact_type in IMAGE_ARTIFACT_TYPES:
        return True
    if artifact.content_type and artifact.content_type.startswith("image/"):
        return True
    filename = (artifact.filename or artifact.source_url or "").lower()
    return filename.endswith((".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"))


def _artifact_path(artifact: SourceArtifact) -> Path:
    storage_uri = artifact.storage_uri
    if not storage_uri and artifact.source_url.startswith("file://"):
        storage_uri = artifact.source_url.removeprefix("file://")
    if not storage_uri:
        raise ValueError("image audit requires locally stored image artifacts")
    path = Path(storage_uri)
    if not path.exists() or not path.is_file():
        raise ValueError(f"artifact file does not exist: {storage_uri}")
    return path


def _image_hash_variants(image: Image.Image) -> dict[str, int]:
    return {transform: _average_hash(transformed) for transform, transformed in _image_transform_variants(image).items()}


def _image_transform_variants(image: Image.Image) -> dict[str, Image.Image]:
    return {
        "original": image,
        "flip_horizontal": ImageOps.mirror(image),
        "flip_vertical": ImageOps.flip(image),
        "rotate_90": image.rotate(90, expand=True),
        "rotate_180": image.rotate(180, expand=True),
        "rotate_270": image.rotate(270, expand=True),
    }


def _correlation_transform_variants(image: Image.Image) -> dict[str, Image.Image]:
    return {
        "original": image,
        "flip_horizontal": ImageOps.mirror(image),
        "flip_vertical": ImageOps.flip(image),
        "rotate_180": image.rotate(180, expand=True),
    }


def _patch_similarity_finding(
    artifact: SourceArtifact,
    target_image: Image.Image,
    peer: SourceArtifact,
    peer_image: Image.Image,
    *,
    max_patch_hamming_distance: int,
    patch_grid_size: int,
    min_patch_stddev: float,
) -> dict[str, Any] | None:
    target_regions = _image_regions(target_image, patch_grid_size, min_patch_stddev)
    peer_regions = _image_regions(peer_image, patch_grid_size, min_patch_stddev)
    best: dict[str, Any] | None = None
    for target_region in target_regions:
        for peer_region in peer_regions:
            if target_region["label"] == "full" and peer_region["label"] == "full":
                continue
            peer_hash = _average_hash(peer_region["image"])
            for transform, target_hash in _image_hash_variants(target_region["image"]).items():
                distance = _hamming_distance(target_hash, peer_hash)
                candidate = {
                    "distance": distance,
                    "transform": transform,
                    "target_region": target_region,
                    "peer_region": peer_region,
                }
                if best is None or distance < best["distance"]:
                    best = candidate
    if best is None or best["distance"] > max_patch_hamming_distance:
        return None
    return _patch_finding(artifact, peer, best, max_patch_hamming_distance)


def _shift_correlation_finding(
    artifact: SourceArtifact,
    target_image: Image.Image,
    peer: SourceArtifact,
    peer_image: Image.Image,
    *,
    min_shift_correlation: float,
    max_shift_fraction: float,
    correlation_size: int,
    min_patch_stddev: float,
) -> dict[str, Any] | None:
    if _stddev(target_image) < min_patch_stddev or _stddev(peer_image) < min_patch_stddev:
        return None
    normalized_size = max(32, min(correlation_size, 160))
    max_shift_pixels = max(0, min(round(normalized_size * max_shift_fraction), normalized_size // 3))
    best: dict[str, Any] | None = None
    peer_samples = {
        channel: _correlation_sample(peer_image, channel, normalized_size)
        for channel in CORRELATION_CHANNELS
    }
    for transform, transformed in _correlation_transform_variants(target_image).items():
        for channel, peer_sample in peer_samples.items():
            target_sample = _correlation_sample(transformed, channel, normalized_size)
            if not _has_informative_content(target_sample) or not _has_informative_content(peer_sample):
                continue
            match = _best_shifted_correlation(
                target_sample,
                peer_sample,
                max_shift_pixels=max_shift_pixels,
                min_overlap_ratio=0.72,
            )
            candidate = {
                "correlation": match["correlation"],
                "transform": transform,
                "channel": channel,
                "shift": match["shift"],
                "overlap_ratio": match["overlap_ratio"],
                "target_stddev": round(_sample_stddev(target_sample), 4),
                "matched_stddev": round(_sample_stddev(peer_sample), 4),
            }
            if best is None or candidate["correlation"] > best["correlation"]:
                best = candidate
    if best is None or best["correlation"] < min_shift_correlation:
        return None
    return _correlation_finding(artifact, peer, best, min_shift_correlation, normalized_size, max_shift_pixels)


def _image_regions(image: Image.Image, grid_size: int, min_patch_stddev: float) -> list[dict[str, Any]]:
    normalized_grid_size = max(2, min(grid_size, 8))
    width, height = image.size
    regions: list[dict[str, Any]] = []
    if _stddev(image) >= min_patch_stddev:
        regions.append({"label": "full", "bbox": {"x": 0, "y": 0, "width": width, "height": height}, "image": image})
    step_x = width / normalized_grid_size
    step_y = height / normalized_grid_size
    for row in range(normalized_grid_size):
        for column in range(normalized_grid_size):
            left = round(column * step_x)
            upper = round(row * step_y)
            right = round((column + 1) * step_x)
            lower = round((row + 1) * step_y)
            if right <= left or lower <= upper:
                continue
            patch = image.crop((left, upper, right, lower))
            if _stddev(patch) < min_patch_stddev:
                continue
            regions.append(
                {
                    "label": f"r{row}c{column}",
                    "bbox": {"x": left, "y": upper, "width": right - left, "height": lower - upper},
                    "image": patch,
                }
            )
    return regions


def _stddev(image: Image.Image) -> float:
    stat = ImageStat.Stat(image.convert("L"))
    return float(stat.stddev[0]) if stat.stddev else 0.0


def _load_image(path: Path) -> Image.Image:
    try:
        with Image.open(path) as image:
            return image.convert("RGB")
    except Exception as exc:  # Pillow raises several format-specific exceptions.
        raise ValueError(f"cannot read image artifact: {path}") from exc


def _average_hash(image: Image.Image, size: int = 16) -> int:
    resized = image.convert("L").resize((size, size), Image.Resampling.LANCZOS)
    if hasattr(resized, "get_flattened_data"):
        pixels = list(resized.get_flattened_data())
    else:
        pixels = list(resized.getdata())
    average = sum(pixels) / len(pixels)
    value = 0
    for pixel in pixels:
        value = (value << 1) | int(pixel >= average)
    return value


def _hamming_distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def _correlation_sample(image: Image.Image, channel: str, size: int) -> list[float]:
    if channel == "gray":
        channel_image = image.convert("L")
    elif channel == "red":
        channel_image = image.convert("RGB").getchannel("R")
    elif channel == "green":
        channel_image = image.convert("RGB").getchannel("G")
    elif channel == "blue":
        channel_image = image.convert("RGB").getchannel("B")
    else:
        raise ValueError(f"unsupported correlation channel: {channel}")
    resized = channel_image.resize((size, size), Image.Resampling.BICUBIC)
    if hasattr(resized, "get_flattened_data"):
        return [float(pixel) for pixel in resized.get_flattened_data()]
    return [float(pixel) for pixel in resized.getdata()]


def _best_shifted_correlation(
    left: list[float],
    right: list[float],
    *,
    max_shift_pixels: int,
    min_overlap_ratio: float,
) -> dict[str, Any]:
    size = round(math.sqrt(len(left)))
    step = max(1, max_shift_pixels // 8)
    best = {"correlation": -1.0, "shift": {"x": 0, "y": 0}, "overlap_ratio": 1.0}
    for dy in range(-max_shift_pixels, max_shift_pixels + 1, step):
        for dx in range(-max_shift_pixels, max_shift_pixels + 1, step):
            left_x = max(0, dx)
            left_y = max(0, dy)
            right_x = max(0, -dx)
            right_y = max(0, -dy)
            width = size - abs(dx)
            height = size - abs(dy)
            if width <= 0 or height <= 0:
                continue
            overlap_ratio = (width * height) / (size * size)
            if overlap_ratio < min_overlap_ratio:
                continue
            correlation = _overlap_correlation(left, right, size, left_x, left_y, right_x, right_y, width, height)
            if correlation > best["correlation"]:
                best = {
                    "correlation": correlation,
                    "shift": {"x": dx, "y": dy},
                    "overlap_ratio": round(overlap_ratio, 4),
                }
    return best


def _overlap_correlation(
    left: list[float],
    right: list[float],
    size: int,
    left_x: int,
    left_y: int,
    right_x: int,
    right_y: int,
    width: int,
    height: int,
) -> float:
    count = width * height
    sum_left = 0.0
    sum_right = 0.0
    sum_left_sq = 0.0
    sum_right_sq = 0.0
    sum_product = 0.0
    for row in range(height):
        left_offset = (left_y + row) * size + left_x
        right_offset = (right_y + row) * size + right_x
        for column in range(width):
            left_value = left[left_offset + column]
            right_value = right[right_offset + column]
            sum_left += left_value
            sum_right += right_value
            sum_left_sq += left_value * left_value
            sum_right_sq += right_value * right_value
            sum_product += left_value * right_value
    left_variance = sum_left_sq - (sum_left * sum_left / count)
    right_variance = sum_right_sq - (sum_right * sum_right / count)
    if left_variance <= 0.0 or right_variance <= 0.0:
        return -1.0
    covariance = sum_product - (sum_left * sum_right / count)
    return covariance / math.sqrt(left_variance * right_variance)


def _has_informative_content(sample: list[float]) -> bool:
    stddev = _sample_stddev(sample)
    if stddev < 4.0:
        return False
    ordered = sorted(sample)
    median = ordered[len(ordered) // 2]
    threshold = max(8.0, stddev * 0.45)
    informative_count = sum(1 for value in sample if abs(value - median) >= threshold)
    return informative_count / len(sample) >= 0.03


def _sample_stddev(sample: list[float]) -> float:
    average = sum(sample) / len(sample)
    variance = sum((value - average) ** 2 for value in sample) / len(sample)
    return math.sqrt(variance)


def _finding(
    artifact: SourceArtifact,
    peer: SourceArtifact,
    transform: str,
    distance: int,
    max_hamming_distance: int,
) -> dict[str, Any]:
    severity = "high" if distance <= 4 else "medium"
    confidence = round(max(0.5, 1 - distance / max(max_hamming_distance * 2, 1)), 3)
    target_name = artifact.filename or artifact.id
    peer_name = peer.filename or peer.id
    return {
        "signal_type": "image_panel_similarity",
        "severity": severity,
        "confidence": confidence,
        "summary": f"图片材料 {target_name} 与 {peer_name} 在 {transform} 比较下高度相似。",
        "metrics": {
            "target_artifact_id": artifact.id,
            "matched_artifact_id": peer.id,
            "transform": transform,
            "hamming_distance": distance,
            "max_hamming_distance": max_hamming_distance,
        },
    }


def _patch_finding(
    artifact: SourceArtifact,
    peer: SourceArtifact,
    best: dict[str, Any],
    max_patch_hamming_distance: int,
) -> dict[str, Any]:
    distance = best["distance"]
    severity = "high" if distance <= 2 else "medium"
    confidence = round(max(0.55, 1 - distance / max(max_patch_hamming_distance * 2, 1)), 3)
    target_name = artifact.filename or artifact.id
    peer_name = peer.filename or peer.id
    target_region = best["target_region"]
    peer_region = best["peer_region"]
    return {
        "signal_type": "image_patch_similarity",
        "severity": severity,
        "confidence": confidence,
        "summary": (
            f"图片材料 {target_name} 的区域 {target_region['label']} 与 {peer_name} 的区域 "
            f"{peer_region['label']} 高度相似，可能存在裁剪或局部复用，需要人工复核。"
        ),
        "metrics": {
            "target_artifact_id": artifact.id,
            "matched_artifact_id": peer.id,
            "transform": best["transform"],
            "hamming_distance": distance,
            "max_patch_hamming_distance": max_patch_hamming_distance,
            "target_region": {"label": target_region["label"], "bbox": target_region["bbox"]},
            "matched_region": {"label": peer_region["label"], "bbox": peer_region["bbox"]},
            "comparison": "patch_similarity",
        },
    }


def _correlation_finding(
    artifact: SourceArtifact,
    peer: SourceArtifact,
    best: dict[str, Any],
    min_shift_correlation: float,
    correlation_size: int,
    max_shift_pixels: int,
) -> dict[str, Any]:
    correlation = best["correlation"]
    severity = "high" if correlation >= 0.9 else "medium"
    confidence = round(min(0.99, max(0.58, 0.35 + correlation * 0.65)), 3)
    target_name = artifact.filename or artifact.id
    peer_name = peer.filename or peer.id
    return {
        "signal_type": "image_shift_correlation",
        "severity": severity,
        "confidence": confidence,
        "summary": (
            f"图片材料 {target_name} 与 {peer_name} 在 {best['transform']} / {best['channel']} 通道比较下 "
            f"出现高相关面板相似性，需要人工复核是否存在平移、裁剪或亮度变化后的复用。"
        ),
        "metrics": {
            "target_artifact_id": artifact.id,
            "matched_artifact_id": peer.id,
            "comparison": "shift_tolerant_normalized_correlation",
            "transform": best["transform"],
            "channel": best["channel"],
            "max_correlation": round(correlation, 4),
            "min_shift_correlation": min_shift_correlation,
            "shift_pixels": best["shift"],
            "overlap_ratio": best["overlap_ratio"],
            "correlation_size": correlation_size,
            "max_shift_pixels": max_shift_pixels,
            "target_stddev": best["target_stddev"],
            "matched_stddev": best["matched_stddev"],
        },
    }


def _upsert_signal(
    db: Session,
    paper: Paper,
    artifact: SourceArtifact,
    finding: dict[str, Any],
    create_review_task: bool,
    priority: int,
) -> tuple[AlgorithmicSignal, bool]:
    signal = db.scalar(
        select(AlgorithmicSignal).where(
            AlgorithmicSignal.paper_id == paper.id,
            AlgorithmicSignal.artifact_id == artifact.id,
            AlgorithmicSignal.signal_type == finding["signal_type"],
            AlgorithmicSignal.analyzer_name == ANALYZER_NAME,
            AlgorithmicSignal.summary == finding["summary"],
        )
    )
    if signal is None:
        signal = AlgorithmicSignal(
            paper=paper,
            artifact_id=artifact.id,
            signal_type=finding["signal_type"],
            severity=finding["severity"],
            confidence=finding["confidence"],
            analyzer_name=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            summary=finding["summary"],
            metrics_json=finding["metrics"],
            status="needs_review",
        )
        db.add(signal)
        db.flush()
    else:
        signal.severity = finding["severity"]
        signal.confidence = finding["confidence"]
        signal.analyzer_version = ANALYZER_VERSION
        signal.metrics_json = finding["metrics"]
        if signal.status not in TERMINAL_SIGNAL_STATUSES:
            signal.status = "needs_review"
        db.execute(delete(EvidencePointer).where(EvidencePointer.signal_id == signal.id))

    db.add(
        EvidencePointer(
            paper_id=paper.id,
            signal=signal,
            artifact=artifact,
            evidence_url=artifact.source_url,
            evidence_summary=finding["summary"],
        )
    )

    created_task = False
    if create_review_task and signal.status not in TERMINAL_SIGNAL_STATUSES:
        existing_task = db.scalar(select(ReviewTask).where(ReviewTask.signal_id == signal.id, ReviewTask.status == "open"))
        if existing_task is None:
            db.add(ReviewTask(paper=paper, signal=signal, task_type="signal_review", priority=priority))
            created_task = True
    return signal, created_task


def _signal_dict(signal: AlgorithmicSignal) -> dict[str, Any]:
    return {
        "id": signal.id,
        "paper_id": signal.paper_id,
        "artifact_id": signal.artifact_id,
        "signal_type": signal.signal_type,
        "severity": signal.severity,
        "confidence": signal.confidence,
        "status": signal.status,
        "summary": signal.summary,
        "metrics": signal.metrics_json,
    }
