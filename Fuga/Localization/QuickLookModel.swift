import ARKit
import Combine
import Foundation

@MainActor
final class QuickLookModel: ObservableObject {
    enum LocationState: String {
        case unconfirmed = "Not located yet"
        case checking = "Looking around"
        case mapUnavailable = "Recognition map not ready"
        case candidate = "Possible location — unverified"
    }
    @Published private(set) var busy = false
    @Published private(set) var message = "Hold the phone up toward the hallway."
    @Published private(set) var locationState: LocationState = .unconfirmed
    @Published private(set) var exportURL: URL?
    private var task: Task<Void, Never>?
    private var generation = UUID()

    /// Frames are taken at least this far apart, so two agreeing frames aren't the same view.
    private static let frameSpacing: TimeInterval = 1.0
    /// With a server: stop after this many frames or seconds and offer Look again.
    private static let maxFrames = 20
    private static let maxSeconds: TimeInterval = 90
    /// Capture-only test (no server): a short burst, then save it.
    private static let captureOnlyFrames = 3

    func cancel() {
        generation = UUID(); task?.cancel(); task = nil; busy = false
        message = "Hold the phone up toward the hallway."
        locationState = .unconfirmed
    }

    /// Looks for the starting location on its own while the camera is open: no tap or
    /// picture-taking. Each frame's image, calibration, timestamp and ARKit transform come
    /// from the SAME ARFrame; it is checked against the map before the next frame is taken.
    /// Stops once two frames give agreeing scan-from-AR transforms (still only a candidate).
    func autoLocate(session: ARSession, floor: Int, destination: String, endpoint: String) {
        cancel()
        exportURL = nil
        guard floor == 4 else {
            locationState = .mapUnavailable
            message = "Floor \(floor)'s recognition map isn't ready yet, so your location can't be found here."
            return
        }
        let token = generation
        let server = endpoint.trimmingCharacters(in: .whitespacesAndNewlines)
        busy = true; locationState = .checking
        message = "Looking around… hold the phone up toward the hallway."
        task = Task {
            var requests = [[String: Any]](), responses = [[String: Any]]()
            var outcome = "Not located yet."
            var finding: LocationState = .unconfirmed
            let sessionID = UUID().uuidString
            let started = ProcessInfo.processInfo.systemUptime
            do {
                let url: URL? = try server.isEmpty ? nil : Self.localizeURL(server)
                let limit = url == nil ? Self.captureOnlyFrames : Self.maxFrames
                while requests.count < limit, ProcessInfo.processInfo.systemUptime - started < Self.maxSeconds {
                    try await Task.sleep(nanoseconds: 300_000_000)
                    guard generation == token else { return }
                    guard let frame = session.currentFrame, case .normal = frame.camera.trackingState else {
                        message = "Getting the camera ready… move the phone slowly."
                        continue
                    }
                    if let last = requests.last?["capture_timestamp"] as? Double,
                       frame.timestamp - last < Self.frameSpacing { continue }
                    let encoded = try await Task.detached(priority: .userInitiated) {
                        try QuickLookCapture.encode(frame: frame, floor: floor, sessionID: sessionID)
                    }.value
                    requests.append(encoded)
                    guard let url else {
                        message = "Saving a camera test… \(requests.count)/\(limit)"
                        continue
                    }
                    message = "Looking around… checking view \(requests.count). Turn slowly if nothing happens."
                    responses.append(try await Self.post(encoded, to: url))
                    if Self.consistent(requests: requests, responses: responses) {
                        finding = .candidate
                        outcome = "Possible starting location found. Saved for review; the walking route still needs verification."
                        break
                    }
                }
                if url == nil {
                    outcome = "Camera test saved. Your location has not been determined; connect the test server to try recognition."
                } else if finding != .candidate {
                    outcome = "Couldn't place you yet. Point the camera at doors, corners or windows, then tap Look again."
                }
            } catch is CancellationError { return }
            catch { outcome = error.localizedDescription }
            guard generation == token, !Task.isCancelled else { return }
            // Export embeds the exact submitted JPEG/calibration/pose pairs and raw replies.
            // This stays in the app sandbox until the user explicitly shares it.
            if !requests.isEmpty {
                do {
                    let folder = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
                        .appendingPathComponent("FugaPrivateCaptures", isDirectory: true)
                    try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
                    let url = folder.appendingPathComponent("\(sessionID).json")
                    let bundle: [String: Any] = ["format": "MGH quick-look diagnostic v1", "session_id": sessionID,
                        "capture_mode": "automatic", "selected_floor": floor, "requested_destination": destination,
                        "requests": requests, "responses": responses, "outcome": outcome,
                        "mapping_reference": false, "navigation_enabled": false,
                        "note": "Camera recognition and route registration are not independently validated. No route was started."]
                    try JSONSerialization.data(withJSONObject: bundle, options: [.prettyPrinted, .sortedKeys])
                        .write(to: url, options: [.atomic, .completeFileProtection])
                    exportURL = url
                } catch { outcome += " Could not save the diagnostic: \(error.localizedDescription)" }
            }
            message = outcome; locationState = finding; busy = false
        }
    }

    private static func localizeURL(_ endpoint: String) throws -> URL {
        guard let base = URL(string: endpoint), ["http", "https"].contains(base.scheme ?? ""),
              base.host != nil, base.user == nil, base.password == nil else {
            throw QuickLookError.message("Enter the development server URL, such as http://computer.local:8765.")
        }
        return base.appendingPathComponent("localize")
    }

    private static func post(_ payload: [String: Any], to url: URL) async throws -> [String: Any] {
        var request = URLRequest(url: url, timeoutInterval: 90)
        request.httpMethod = "POST"; request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: payload)
        let (data, reply) = try await URLSession.shared.data(for: request)
        guard let http = reply as? HTTPURLResponse, http.statusCode == 200,
              let result = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw QuickLookError.message("The recognition server did not accept the frame.")
        }
        return result
    }

    /// All transforms are capture-time pairs in the same AR world and scan map.
    /// Different camera positions should yield the SAME scan-from-AR transform.
    private static func consistent(requests: [[String: Any]], responses: [[String: Any]]) -> Bool {
        let frames = Set(responses.compactMap { $0["coordinate_frame_id"] as? String })
        let maps = Set(responses.compactMap { $0["map_manifest_sha256"] as? String })
        let alignments = zip(requests, responses).compactMap { pair in
            QuickLookGeometry.alignment(request: pair.0, response: pair.1)
        }
        return frames.count == 1 && maps.count == 1 && alignments.count >= 2 &&
            alignments.indices.contains { i in alignments.indices.contains { j in
                i != j && QuickLookGeometry.agree(alignments[i], alignments[j])
            } }
    }
}
