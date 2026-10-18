import ARKit
import Combine
import Foundation

@MainActor
final class QuickLookModel: ObservableObject {
    enum LocationState: String {
        case unconfirmed = "Not located yet"
        case checking = "Checking the camera"
        case mapUnavailable = "Recognition map not ready"
        case candidate = "Possible location — unverified"
    }
    @Published private(set) var busy = false
    @Published private(set) var message = "Choose your floor and point the camera down the hallway."
    @Published private(set) var locationState: LocationState = .unconfirmed
    @Published private(set) var exportURL: URL?
    private var task: Task<Void, Never>?
    private var generation = UUID()

    func cancel() {
        generation = UUID(); task?.cancel(); task = nil; busy = false; exportURL = nil
        message = "Choose your floor and point the camera down the hallway."
        locationState = .unconfirmed
    }

    func find(session: ARSession, floor: Int, destination: String, endpoint: String) {
        cancel()
        let token = generation
        busy = true; exportURL = nil; locationState = .checking
        task = Task {
            var requests = [[String: Any]](), responses = [[String: Any]]()
            var outcome = "Not located yet."
            var finding: LocationState = .unconfirmed
            let sessionID = UUID().uuidString
            do {
                // Capture a short burst FIRST; network response latency cannot change its poses.
                for i in 0..<3 {
                    try Task.checkCancellation()
                    guard let frame = session.currentFrame else {
                        throw QuickLookError.message("The camera is not ready yet.")
                    }
                    message = "Looking at the hallway… \(i + 1)/3"
                    let encoded = try await Task.detached(priority: .userInitiated) {
                        try QuickLookCapture.encode(frame: frame, floor: floor, sessionID: sessionID)
                    }.value
                    if let last = requests.last?["capture_timestamp"] as? Double,
                       (encoded["capture_timestamp"] as? Double ?? last) - last < 0.5 {
                        throw QuickLookError.message("The camera did not provide a new frame.")
                    }
                    requests.append(encoded)
                    if i < 2 { try await Task.sleep(nanoseconds: 700_000_000) }
                }
                try Task.checkCancellation()
                guard generation == token else { return }
                if floor != 4 {
                    finding = .mapUnavailable
                    outcome = "Floor \(floor) is captured for testing. Its recognition map is not ready yet."
                } else if endpoint.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    outcome = "Camera test saved. Your location has not been determined; connect the test server to try recognition."
                } else {
                    guard let base = URL(string: endpoint), ["http", "https"].contains(base.scheme ?? ""),
                          base.host != nil, base.user == nil, base.password == nil else {
                        throw QuickLookError.message("Enter the development server URL, such as http://computer.local:8765.")
                    }
                    let url = base.appendingPathComponent("localize")
                    for (i, payload) in requests.enumerated() {
                        try Task.checkCancellation()
                        message = "Checking the saved map… \(i + 1)/3. This prototype can take a while."
                        var request = URLRequest(url: url, timeoutInterval: 90)
                        request.httpMethod = "POST"; request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                        request.httpBody = try JSONSerialization.data(withJSONObject: payload)
                        let (data, reply) = try await URLSession.shared.data(for: request)
                        guard let http = reply as? HTTPURLResponse, http.statusCode == 200,
                              let result = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                            throw QuickLookError.message("The recognition server did not accept the frame.")
                        }
                        responses.append(result)
                    }
                    // All transforms are capture-time pairs in the same AR world and scan map.
                    // Different camera positions should yield the SAME scan-from-AR transform.
                    let frames = Set(responses.compactMap { $0["coordinate_frame_id"] as? String })
                    let maps = Set(responses.compactMap { $0["map_manifest_sha256"] as? String })
                    let alignments = zip(requests, responses).compactMap { pair in
                        QuickLookGeometry.alignment(request: pair.0, response: pair.1)
                    }
                    let consistent = frames.count == 1 && maps.count == 1 && alignments.count >= 2 &&
                        alignments.indices.contains { i in alignments.indices.contains { j in
                            i != j && QuickLookGeometry.agree(alignments[i], alignments[j])
                        } }
                    outcome = consistent
                        ? "Possible starting location found. Saved for review; the walking route still needs verification."
                        : "Starting location is uncertain. Try a view with doors, corners or windows."
                    finding = consistent ? .candidate : .unconfirmed
                }
            } catch is CancellationError { return }
            catch { outcome = error.localizedDescription }
            guard generation == token, !Task.isCancelled else { return }
            // Export embeds the exact submitted JPEG/calibration/pose pairs and raw replies.
            // This stays in the app sandbox until the user explicitly shares it.
            do {
                let folder = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
                    .appendingPathComponent("FugaPrivateCaptures", isDirectory: true)
                try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
                let url = folder.appendingPathComponent("\(sessionID).json")
                let bundle: [String: Any] = ["format": "MGH quick-look diagnostic v1", "session_id": sessionID,
                    "selected_floor": floor, "requested_destination": destination,
                    "requests": requests, "responses": responses, "outcome": outcome,
                    "mapping_reference": false, "navigation_enabled": false,
                    "note": "Camera recognition and route registration are not independently validated. No route was started."]
                try JSONSerialization.data(withJSONObject: bundle, options: [.prettyPrinted, .sortedKeys])
                    .write(to: url, options: [.atomic, .completeFileProtection])
                exportURL = url
            } catch { outcome += " Could not save the diagnostic: \(error.localizedDescription)" }
            message = outcome; locationState = finding; busy = false
        }
    }
}
