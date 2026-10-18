import ARKit
import Combine
import Foundation

/// Shows the DRAFT route from a possible starting location: the green floor line and the
/// arrow only. It never speaks, never vibrates and never starts RouteNavigator guidance
/// (`RouteNavigator.guidanceEnabled` stays false). The route comes from the development
/// server's draft scan-frame graph: corridors are where the scan walked, the target is a
/// room sign viewpoint, not a verified doorway.
@MainActor
final class RoutePreview: ObservableObject {
    enum State: Equatable {
        case off, requesting, showing
        case unavailable(String)
    }
    @Published private(set) var state: State = .off
    @Published private(set) var relativeBearing: Double = 0
    @Published private(set) var distanceRemaining: Double = 0
    @Published private(set) var summary = ""
    @Published private(set) var offRoute = false
    let floorPath = FloorPathNode()
    private var path: [PathPoint] = []
    private var task: Task<Void, Never>?

    /// Off the drawn route by more than this, the preview says so instead of pointing.
    private static let offRouteMeters = 3.0

    func clear() {
        task?.cancel(); task = nil
        path = []; floorPath.hide()
        state = .off; summary = ""; offRoute = false
    }

    func start(session: ARSession, candidate: QuickLookModel.Candidate, room: String) {
        clear()
        state = .requesting
        summary = "Asking for a draft route to room \(room)…"
        task = Task { [weak self] in
            guard let self else { return }
            do {
                guard let frame = session.currentFrame, case .normal = frame.camera.trackingState else {
                    throw QuickLookError.message("Hold the phone up so camera tracking resumes, then Look again.")
                }
                let pose = RoutePreviewMath.scanPose(arCamera: frame.camera.transform, scanFromAR: candidate.scanFromAR)
                let body: [String: Any] = [
                    "destination_room": room, "building_id": "MGH", "selected_floor": candidate.floor,
                    "coordinate_frame_id": candidate.coordinateFrameID,
                    "map_manifest_sha256": candidate.mapManifestSHA256,
                    "position_scan_m": [pose.position.x, pose.position.y, pose.position.z].map { Double($0) },
                    "forward_scan": [pose.forward.x, pose.forward.y, pose.forward.z].map { Double($0) }]
                var request = URLRequest(url: candidate.server.appendingPathComponent("route"), timeoutInterval: 30)
                request.httpMethod = "POST"; request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                request.httpBody = try JSONSerialization.data(withJSONObject: body)
                let (data, reply) = try await URLSession.shared.data(for: request)
                guard let http = reply as? HTTPURLResponse, http.statusCode == 200,
                      let result = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                    throw QuickLookError.message("The server did not return a route.")
                }
                guard result["ok"] as? Bool == true else {
                    let reason = result["reason"] as? String ?? result["status"] as? String ?? "unknown"
                    throw QuickLookError.message("No draft route to room \(room): \(reason).")
                }
                // Only a route in the SAME map frame as the alignment can be drawn, and it must
                // say it is unverified; anything else is refused rather than shown.
                guard result["coordinate_frame_id"] as? String == candidate.coordinateFrameID,
                      result["map_manifest_sha256"] as? String == candidate.mapManifestSHA256,
                      result["destination_room"] as? String == room,
                      result["verified"] as? Bool == false, result["guidance_allowed"] as? Bool == false,
                      let xz = result["path_scan_xz"] as? [[Double]],
                      let points = RoutePreviewMath.arTopDown(scanXZ: xz, scanY: Double(pose.position.y),
                                                              scanFromAR: candidate.scanFromAR) else {
                    throw QuickLookError.message("The route reply did not match this location's map.")
                }
                try Task.checkCancellation()
                self.path = RoutePreviewMath.withAlong(points)
                let meters = Int((result["meters"] as? Double ?? self.path.last?.along ?? 0).rounded())
                self.summary = "Draft route to room \(room), about \(meters) m. Unverified preview: not guidance."
                self.state = .showing
                while !Task.isCancelled {
                    self.update(session.currentFrame)
                    try await Task.sleep(nanoseconds: 100_000_000)
                }
            } catch is CancellationError {
            } catch {
                self.path = []; self.floorPath.hide()
                self.state = .unavailable(error.localizedDescription); self.summary = error.localizedDescription
            }
        }
    }

    private func update(_ frame: ARFrame?) {
        guard let frame, case .normal = frame.camera.trackingState,
              let pose = RouteNavigator.topDownPose(frame.camera.transform), let end = path.last else {
            floorPath.hide(); return
        }
        let hit = RoutePreviewMath.project(pose.position, on: path)
        offRoute = hit.offset > Self.offRouteMeters
        distanceRemaining = max(0, end.along - hit.along)
        if let aim = RoutePreviewMath.point(on: path, along: hit.along + 2) {
            relativeBearing = RouteTracker.relativeBearing(from: pose.position, headingDegrees: pose.heading, to: aim)
        }
        floorPath.update(path: RoutePreviewMath.remaining(from: pose.position, on: path),
                         floorY: floorPath.floorHeight(frame) + 0.01)
    }
}
