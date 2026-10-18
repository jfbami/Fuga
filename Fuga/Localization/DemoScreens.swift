import ARKit
import SwiftUI

// DEMO BRANCH ONLY (demo-purpose-only). A cleaner front end over the SAME location
// and route code as mgh-localization: QuickLookModel (automatic camera location),
// RoutePreview (draft line + arrow, no voice/vibration) and the development server.
// Every original tool (server address, export, voice & vibration test, manual test)
// is still here: the original screen opens from the gear.

/// Home: pick the floor, optionally say where to go, then one Find location button.
struct DemoHomeView<Tools: View>: View {
    let session: ARSession
    var onCameraWork: () -> Void = {}
    /// The original developer screen; `close` dismisses it.
    @ViewBuilder let developerTools: (@escaping () -> Void) -> Tools

    @AppStorage("demoFloor") private var floor = 4
    @State private var destination = ""
    @State private var showFind = false
    @State private var showTools = false
    @State private var typing = false
    @State private var typed = ""
    @StateObject private var voice = DestinationVoice()

    var body: some View {
        ZStack {
            LinearGradient(colors: [Color(red: 0.04, green: 0.10, blue: 0.07), .black],
                           startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea()
            VStack(spacing: 24) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Fuga").font(.system(size: 40, weight: .bold, design: .rounded))
                        Text("Mary Gates Hall").font(.headline).foregroundStyle(.white.opacity(0.6))
                    }
                    Spacer()
                    Button {
                        voice.stop(); onCameraWork(); showTools = true
                    } label: {
                        Image(systemName: "gearshape.fill").font(.title2).foregroundStyle(.white.opacity(0.6))
                    }
                    .accessibilityLabel("Developer tools")
                }
                Spacer()
                floorPicker
                destinationCard
                Button {
                    voice.stop(); onCameraWork(); showFind = true
                } label: {
                    Label("Find location", systemImage: "location.viewfinder")
                        .font(.title2.bold())
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 22)
                }
                .buttonStyle(.borderedProminent)
                .tint(.fugaGreen)
                .clipShape(RoundedRectangle(cornerRadius: 22))
                Text("Point the camera down the hallway. You don't need to pick where you are.")
                    .font(.footnote).foregroundStyle(.white.opacity(0.55))
                    .multilineTextAlignment(.center)
            }
            .padding(24)
            .foregroundStyle(.white)
        }
        .fullScreenCover(isPresented: $showFind) {
            DemoFindView(session: session, floor: floor, destination: destination)
        }
        .sheet(isPresented: $showTools) { developerTools { showTools = false } }
        .onChange(of: voice.transcript) { _, text in
            if let room = DestinationVoice.room(in: text) { destination = room }
        }
        .alert("Destination room", isPresented: $typing) {
            TextField("For example 440", text: $typed).keyboardType(.numberPad)
            Button("Set") {
                if let room = DestinationVoice.room(in: typed) { destination = room } else if typed.isEmpty { destination = "" }
            }
            Button("Cancel", role: .cancel) {}
        }
        .onDisappear { voice.stop() }
    }

    private var floorPicker: some View {
        HStack(spacing: 10) {
            ForEach([2, 3, 4], id: \.self) { f in
                Button { floor = f } label: {
                    Text("Floor \(f)").font(.headline)
                        .frame(maxWidth: .infinity).padding(.vertical, 14)
                        .background(floor == f ? Color.fugaGreen : Color.white.opacity(0.08),
                                    in: RoundedRectangle(cornerRadius: 14))
                        .foregroundStyle(floor == f ? Color.black : Color.white)
                }
                .accessibilityAddTraits(floor == f ? .isSelected : [])
            }
        }
    }

    private var destinationCard: some View {
        VStack(spacing: 12) {
            Text(destination.isEmpty ? "Where to? (optional)" : "To room \(destination)")
                .font(.title3.weight(.semibold))
            if voice.listening {
                Text(voice.transcript.isEmpty ? "Listening…" : voice.transcript).foregroundStyle(.white.opacity(0.7))
            } else if let note = voice.message {
                Text(note).font(.footnote).foregroundStyle(.white.opacity(0.6))
            }
            HStack(spacing: 10) {
                Button {
                    if voice.listening { voice.stop() } else { onCameraWork(); Task { await voice.start() } }
                } label: {
                    Label(voice.listening ? "Stop" : "Say a room", systemImage: voice.listening ? "stop.fill" : "mic.fill")
                        .frame(maxWidth: .infinity).padding(.vertical, 10)
                }
                .buttonStyle(.bordered).tint(.white)
                Button { typed = destination; typing = true } label: {
                    Image(systemName: "keyboard").padding(.vertical, 10)
                }
                .buttonStyle(.bordered).tint(.white)
                .accessibilityLabel("Type a room number")
                if !destination.isEmpty {
                    Button { destination = "" } label: { Image(systemName: "xmark").padding(.vertical, 10) }
                        .buttonStyle(.bordered).tint(.white)
                        .accessibilityLabel("Clear destination")
                }
            }
        }
        .frame(maxWidth: .infinity)
        .padding(18)
        .background(Color.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 20))
    }
}

/// Full-screen camera: finds where you are on its own, names the nearest known room,
/// then (with a destination) shows the draft route line and arrow. Nothing here speaks,
/// vibrates or starts walking guidance; RouteNavigator.guidanceEnabled stays false.
@MainActor
struct DemoFindView: View {
    let session: ARSession
    let floor: Int
    let destination: String

    struct NearestRoom: Equatable { let room: String; let meters: Double }
    /// Rooms with a draft target in the server's route graph (420 has none).
    static let knownRooms = ["416", "430", "440"]

    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var model = QuickLookModel()
    @StateObject private var preview = RoutePreview()
    @State private var nearest: NearestRoom?
    @State private var nearestTask: Task<Void, Never>?
    @AppStorage("mghDevelopmentServer") private var endpoint = ""

    private var room: String? { DestinationVoice.room(in: destination) }
    private var serverMissing: Bool { endpoint.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }

    var body: some View {
        ZStack {
            ARCameraView(session: session, content: preview.floorPath)
                .ignoresSafeArea()
                .accessibilityLabel("Live hallway camera")
            LinearGradient(colors: [.black.opacity(0.65), .clear, .clear, .black.opacity(0.7)],
                           startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea()
                .allowsHitTesting(false)
            VStack(spacing: 16) {
                topBar
                statusCard
                Spacer()
                routeArea
                bottomBar
            }
            .padding(20)
            .foregroundStyle(.white)
        }
        .onAppear { start() }
        .onDisappear { stop() }
        .onChange(of: scenePhase) { _, phase in if phase == .active { start() } else { stop() } }
        .onChange(of: model.candidate) { _, candidate in found(candidate) }
    }

    // MARK: Pieces

    private var topBar: some View {
        HStack {
            Button { dismiss() } label: {
                Image(systemName: "xmark").font(.headline).padding(12)
                    .background(.ultraThinMaterial, in: Circle())
            }
            .accessibilityLabel("Close")
            Spacer()
            Text("Floor \(floor)").font(.headline)
                .padding(.horizontal, 14).padding(.vertical, 8)
                .background(.ultraThinMaterial, in: Capsule())
            Spacer()
            if let url = model.exportURL {
                ShareLink(item: url) {
                    Image(systemName: "square.and.arrow.up").font(.headline).padding(12)
                        .background(.ultraThinMaterial, in: Circle())
                }
                .accessibilityLabel("Share camera test")
            } else {
                Color.clear.frame(width: 44, height: 44)
            }
        }
    }

    private var statusCard: some View {
        VStack(spacing: 8) {
            HStack(spacing: 10) {
                if model.busy || preview.state == .requesting { ProgressView().tint(.white) }
                if model.locationState == .candidate { Image(systemName: "checkmark.circle.fill").foregroundStyle(Color.fugaGreen) }
                Text(headline).font(.title2.bold())
            }
            Text(detail).font(.subheadline).foregroundStyle(.white.opacity(0.8)).multilineTextAlignment(.center)
            if !model.busy && floor == 4 && model.locationState != .candidate {
                Button("Try again") { start() }
                    .buttonStyle(.borderedProminent).tint(.fugaGreen).padding(.top, 4)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(18)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 22))
        .accessibilityElement(children: .combine)
    }

    @ViewBuilder private var routeArea: some View {
        if let room, model.locationState == .candidate {
            VStack(spacing: 10) {
                switch preview.state {
                case .showing where preview.offRoute:
                    Text("Move back toward the hallway, then tap Try again.").font(.headline)
                case .showing:
                    ExitArrowView(relativeBearing: preview.relativeBearing, distanceMeters: preview.distanceRemaining)
                    Text("To room \(room)").font(.title3.weight(.semibold))
                    if !preview.floorFound {
                        Text("Tilt toward the floor to see the path").font(.footnote).foregroundStyle(.white.opacity(0.8))
                    }
                case .requesting:
                    Text("Getting the route to room \(room)…").font(.headline)
                case .unavailable(let reason):
                    Text(reason).font(.subheadline).multilineTextAlignment(.center)
                case .off:
                    EmptyView()
                }
            }
            .padding(.bottom, 4)
        }
    }

    private var bottomBar: some View {
        Text(preview.state == .showing
             ? "Draft route preview from a scan of the building. Not turn-by-turn guidance yet."
             : "Hold the phone upright and point it down the hallway.")
            .font(.caption).foregroundStyle(.white.opacity(0.7))
            .multilineTextAlignment(.center)
    }

    private var headline: String {
        switch model.locationState {
        case .checking: return "Finding you…"
        case .candidate: return nearest.map { "You're near room \($0.room)" } ?? "Found you"
        case .mapUnavailable: return "Floor \(floor) isn't mapped yet"
        case .unconfirmed:
            if model.busy { return "Finding you…" }
            return serverMissing ? "Location server not connected" : "Couldn't place you yet"
        }
    }

    private var detail: String {
        switch model.locationState {
        case .checking: return "Hold the phone up toward the hallway."
        case .candidate:
            if let n = nearest { return "About \(Int(n.meters.rounded())) m from its sign · approximate, not verified" }
            return "Approximate location, not verified"
        case .mapUnavailable: return "Only floor 4 has a recognition map so far."
        case .unconfirmed:
            if model.busy { return "Hold the phone up toward the hallway." }
            return serverMissing
                ? "A camera test was saved. Add the server address in the gear menu to find your location."
                : "Point at doors, corners or signs, then try again."
        }
    }

    // MARK: Actions (same calls as the original screen)

    private func start() {
        nearestTask?.cancel(); nearest = nil
        preview.clear()
        model.autoLocate(session: session, floor: floor, destination: destination, endpoint: endpoint)
    }

    private func stop() {
        nearestTask?.cancel(); nearestTask = nil
        preview.clear()
        model.cancel()
    }

    private func found(_ candidate: QuickLookModel.Candidate?) {
        guard let candidate else { nearest = nil; preview.clear(); return }
        if let room { preview.start(session: session, candidate: candidate, room: room) }
        nearestTask?.cancel()
        nearestTask = Task {
            nearest = await Self.nearestRoom(session: session, candidate: candidate)
        }
    }

    /// The known room whose sign viewpoint is the shortest walk away, asked from the same
    /// draft /route the preview uses. A label for the demo, not a verified room position.
    static func nearestRoom(session: ARSession, candidate: QuickLookModel.Candidate) async -> NearestRoom? {
        guard let frame = session.currentFrame, case .normal = frame.camera.trackingState else { return nil }
        let pose = RoutePreviewMath.scanPose(arCamera: frame.camera.transform, scanFromAR: candidate.scanFromAR)
        var best: NearestRoom?
        for room in knownRooms {
            if Task.isCancelled { return nil }
            let body: [String: Any] = [
                "destination_room": room, "building_id": "MGH", "selected_floor": candidate.floor,
                "coordinate_frame_id": candidate.coordinateFrameID,
                "map_manifest_sha256": candidate.mapManifestSHA256,
                "position_scan_m": [pose.position.x, pose.position.y, pose.position.z].map { Double($0) },
                "forward_scan": [pose.forward.x, pose.forward.y, pose.forward.z].map { Double($0) }]
            var request = URLRequest(url: candidate.server.appendingPathComponent("route"), timeoutInterval: 15)
            request.httpMethod = "POST"; request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            guard let data = try? JSONSerialization.data(withJSONObject: body) else { continue }
            request.httpBody = data
            guard let exchange = try? await URLSession.shared.data(for: request),
                  (exchange.1 as? HTTPURLResponse)?.statusCode == 200,
                  let result = try? JSONSerialization.jsonObject(with: exchange.0) as? [String: Any],
                  result["ok"] as? Bool == true,
                  result["coordinate_frame_id"] as? String == candidate.coordinateFrameID,
                  result["map_manifest_sha256"] as? String == candidate.mapManifestSHA256,
                  let meters = result["meters"] as? Double else { continue }
            if best == nil || meters < best!.meters { best = NearestRoom(room: room, meters: meters) }
        }
        return best
    }
}
