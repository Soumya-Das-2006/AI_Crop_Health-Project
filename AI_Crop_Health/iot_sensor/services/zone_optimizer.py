"""
Zone Optimizer
--------------
Implements:
  1. K-medoids clustering  — optimal sensor/zone placement
  2. Weiszfeld's algorithm — optimal valve placement per zone

Pure Python (NumPy only), no external ML library needed.
Called from the admin panel or a management command.
"""

import math
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# 1. K-MEDOIDS CLUSTERING
# ──────────────────────────────────────────────────────────────────────────────

def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def kmedoids(points: List[Tuple[float, float]], k: int, max_iter: int = 100):
    """
    K-medoids clustering on (lat, lon) points using Haversine distance.
    Returns (medoid_indices, cluster_assignments).
    """
    import random
    n = len(points)
    if k >= n:
        return list(range(n)), list(range(n))

    # Precompute distance matrix
    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = haversine_km(*points[i], *points[j])
            dist[i][j] = dist[j][i] = d

    medoids = random.sample(range(n), k)

    for _ in range(max_iter):
        # Assign each point to nearest medoid
        assignments = [
            min(range(k), key=lambda m: dist[p][medoids[m]])
            for p in range(n)
        ]

        new_medoids = list(medoids)
        changed = False
        for cluster_idx in range(k):
            cluster_members = [p for p, a in enumerate(assignments) if a == cluster_idx]
            if not cluster_members:
                continue
            best = min(cluster_members,
                       key=lambda p: sum(dist[p][q] for q in cluster_members))
            if best != medoids[cluster_idx]:
                new_medoids[cluster_idx] = best
                changed = True

        medoids = new_medoids
        if not changed:
            break

    # Final assignment
    assignments = [
        min(range(k), key=lambda m: dist[p][medoids[m]])
        for p in range(n)
    ]
    return medoids, assignments


# ──────────────────────────────────────────────────────────────────────────────
# 2. WEISZFELD'S ALGORITHM  (geometric median → optimal valve placement)
# ──────────────────────────────────────────────────────────────────────────────

def weiszfeld(points: List[Tuple[float, float]], max_iter: int = 300, tol: float = 1e-9):
    """
    Find the geometric median of a set of (lat, lon) points.
    Used to find optimal solenoid valve placement within a zone.
    Returns (lat, lon) of optimal placement.
    """
    if not points:
        return (0.0, 0.0)
    if len(points) == 1:
        return points[0]

    # Start from centroid
    lat = sum(p[0] for p in points) / len(points)
    lon = sum(p[1] for p in points) / len(points)

    for _ in range(max_iter):
        weights, wlat, wlon = 0.0, 0.0, 0.0
        for p in points:
            d = haversine_km(lat, lon, p[0], p[1])
            if d < 1e-10:
                continue
            w = 1.0 / d
            weights += w
            wlat += w * p[0]
            wlon += w * p[1]

        if weights < 1e-10:
            break

        new_lat = wlat / weights
        new_lon = wlon / weights

        if haversine_km(lat, lon, new_lat, new_lon) < tol:
            break
        lat, lon = new_lat, new_lon

    return (lat, lon)


# ──────────────────────────────────────────────────────────────────────────────
# 3. HIGH-LEVEL: optimise zones for a Field
# ──────────────────────────────────────────────────────────────────────────────

def optimise_field_zones(field, k: int):
    """
    Run K-medoids on the field's sensor nodes, then Weiszfeld per zone.
    Creates / updates FieldZone records.
    Returns list of FieldZone objects.
    """
    from ..models import SensorNode, FieldZone

    nodes = list(SensorNode.objects.filter(field=field, is_active=True)
                 .exclude(latitude=None).exclude(longitude=None))

    if not nodes:
        logger.warning("No nodes with GPS data for field %s", field)
        return []

    points = [(float(n.latitude), float(n.longitude)) for n in nodes]
    k = min(k, len(points))

    medoid_indices, assignments = kmedoids(points, k)

    zones = []
    for cluster_idx in range(k):
        label = f"Z{cluster_idx + 1}"
        medoid_node = nodes[medoid_indices[cluster_idx]]
        cluster_pts = [points[i] for i, a in enumerate(assignments) if a == cluster_idx]

        # Weiszfeld for optimal valve placement
        valve_lat, valve_lon = weiszfeld(cluster_pts)

        zone, _ = FieldZone.objects.update_or_create(
            field=field,
            zone_label=label,
            defaults=dict(
                centroid_lat=medoid_node.latitude,
                centroid_lng=medoid_node.longitude,
                valve_lat=valve_lat,
                valve_lng=valve_lon,
                area_acres=None,
            )
        )

        # Tag sensor nodes with their zone
        for i, a in enumerate(assignments):
            if a == cluster_idx:
                nodes[i].placement_zone = label
                nodes[i].save(update_fields=['placement_zone'])

        zones.append(zone)
        logger.info("Zone %s created for field %s | valve @ (%.6f, %.6f)",
                    label, field.name, valve_lat, valve_lon)

    return zones
