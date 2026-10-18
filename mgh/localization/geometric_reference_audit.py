"""Uncalibrated 2D verification for appearance diagnostics, never trusted camera pose."""
import cv2
import numpy as np


def coverage(points, size):
    if len(points) < 3:
        return 0.0
    return float(cv2.contourArea(cv2.convexHull(np.asarray(points, np.float32))) / np.prod(size))


def verify_pair(query_points, reference_points, query_size, reference_size):
    q, r = np.asarray(query_points, np.float64), np.asarray(reference_points, np.float64)
    if q.shape != r.shape or q.ndim != 2 or q.shape[1] != 2 or not np.isfinite(q).all() or not np.isfinite(r).all():
        raise ValueError('Expected finite corresponding Nx2 points.')
    for size in [query_size, reference_size]:
        if np.asarray(size).shape != (2,) or not np.isfinite(size).all() or min(size) <= 0:
            raise ValueError('Image dimensions must be positive and finite.')
    result = dict(matches=len(q), fundamental_inliers=0, homography_inliers=0,
        query_coverage=0.0, reference_coverage=0.0, coverage_weighted_score=0.0,
        planar_or_low_parallax_ambiguous=True, accepted=False, pose_usable_for_app=False,
        navigation_enabled=False, calibration_status='missing',
        meaning='2D consistency can reject some matches but cannot establish room identity or metric pose.')
    fmask = np.zeros(len(q), bool)
    if len(q) < 8:
        return result, fmask
    cv2.setRNGSeed(42)
    fundamental, mask = cv2.findFundamentalMat(q, r, cv2.USAC_MAGSAC, 1.5, .999, 10000)
    cv2.setRNGSeed(42)
    homography, hmask = cv2.findHomography(q, r, cv2.USAC_MAGSAC, 3.0, maxIters=10000, confidence=.999)
    if fundamental is None or fundamental.shape != (3, 3) or mask is None:
        return result, fmask
    fmask = mask.ravel().astype(bool)
    count = int(fmask.sum())
    hcount = int(hmask.sum()) if homography is not None and hmask is not None else 0
    qc, rc = coverage(q[fmask], query_size), coverage(r[fmask], reference_size)
    result.update(fundamental_inliers=count, homography_inliers=hcount,
        query_coverage=qc, reference_coverage=rc,
        fundamental_inlier_ratio=count / len(q),
        coverage_weighted_score=float(count * np.sqrt(min(qc, rc))) if count >= 15 else 0.0,
        planar_or_low_parallax_ambiguous=bool(hcount >= .85 * max(count, 1)),
        fundamental_matrix=fundamental.tolist())
    return result, fmask
