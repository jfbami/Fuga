import ARKit
import AVFoundation
import Combine
import UIKit

/// Tracks the phone with ARKit, places it on the floor plan, routes to a destination,
/// and turns the route into arrow directions, spoken steps and vibration.
///
/// Where you are on the plan comes from one of two places:
/// - A saved ARKit map of the floor (recorded once in Mapping Mode). When the camera
///   recognizes the hallway, ARKit snaps back into the map's coordinates and the saved
///   alignment turns that into plan meters. Works from anywhere in the mapped area.
/// - Fallback: start at the elevator, facing down the hallway (no map needed).
final class RouteNavigator: NSObject, ObservableObject, ARSessionDelegate {
    enum Phase: Equatable { case idle, navigating, arrived, mapping }
    enum Localization: Equatable {
        case noMap          // no saved map: use the elevator start
        case searching      // map loaded, waiting for the camera to recognize the hallway
        case located        // recognized: we know where you are
    }

    // MARK: Published state

    @Published private(set) var phase: Phase = .idle
    @Published private(set) var localization: Localization = .noMap
    @Published private(set) var mapSource: String?
    @Published private(set) var whereYouAre: String?
    @Published private(set) var trackingReady = false
    @Published private(set) var trackingMessage: String? = "Starting the camera…"
    @Published private(set) var relativeBearing: Double = 0
    @Published private(set) var distanceRemaining: Double = 0
    @Published private(set) var instruction = ""
    @Published private(set) var isOffRoute = false
    @Published private(set) var planPosition: Vec2?
    @Published private(set) var planHeading: Double = 0
    @Published private(set) var route: Route?
    @Published private(set) var destination: HallwayGraph.Destination?

    // Mapping Mode
    @Published private(set) var mappingStatus = ""
    @Published private(set) var mappingPath: [Vec2] = []
    @Published private(set) var checkpointsTaken: [String] = []
    @Published private(set) var canSaveMap = false
    @Published private(set) var mapMessage: String?

    let session = ARSession()
    let graph: HallwayGraph
    let mapName = "mgh4"

    // MARK: Private state

    private var alignment: MapAlignment?
    private var useCorridorCorrection = false
    private var tracker: RouteTracker?
    private var pendingElevatorStart = false
    private var lastUpdate: TimeInterval = 0
    private var lastFrame: (position: Vec2, heading: Double)?
    private var arHistory: [Vec2] = []
    private var sawRelocalizing = false
    private var searchingSince: TimeInterval?

    private var announcedSoon = Set<Int>()
    private var announcedNow = Set<Int>()
    private var offRouteSince: TimeInterval?

    private var mappingRaw: [Vec2] = []
    private var checkpointAR: [Vec2] = []
    private var checkpointPlan: [Vec2] = []

    private let speech = AVSpeechSynthesizer()
    private let haptic = UIImpactFeedbackGenerator(style: .heavy)
    private let notify = UINotificationFeedbackGenerator()

    private let lookAhead = 2.5
    private let arrivalRadius = 1.5
    static let originAnchorName = "fuga-origin"

    init(graph: HallwayGraph) {
        self.graph = graph
        super.init()
        session.delegate = self
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .spokenAudio, options: [.duckOthers])
    }

    // MARK: Camera / map

    /// Starts tracking. If a map of this floor exists, ARKit tries to recognize it.
    func runCamera() {
        guard ARWorldTrackingConfiguration.isSupported else {
            trackingMessage = "This iPhone doesn't support ARKit world tracking."
            return
        }
        let config = ARWorldTrackingConfiguration()
        config.worldAlignment = .gravity
        config.planeDetection = [.horizontal]
        alignment = nil
        sawRelocalizing = false
        searchingSince = nil
        if let saved = WorldMapStore.load(name: mapName) {
            config.initialWorldMap = saved.map
            alignment = saved.alignment
            mapSource = saved.source
            localization = .searching
        } else {
            mapSource = nil
            localization = .noMap
        }
        session.run(config, options: [.resetTracking, .removeExistingAnchors])
    }

    func pauseCamera() { session.pause() }

    // MARK: Navigation

    /// Route from wherever the map says you are.
    func startHere(to destination: HallwayGraph.Destination) {
        guard localization == .located, let p = planPosition,
              let route = graph.route(from: p, to: destination) else { return }
        useCorridorCorrection = false
        begin(route: route, destination: destination)
    }

    /// Fallback: you're just outside the elevator, facing down the hallway.
    func startAtElevator(to destination: HallwayGraph.Destination) {
        guard let start = graph.node(graph.startNode),
              let route = graph.route(from: start.point, to: destination, fromName: "the elevator") else { return }
        useCorridorCorrection = true
        localization = .noMap
        if let frame = lastFrame, trackingReady {
            calibrateAtElevator(arPosition: frame.position, arHeading: frame.heading)
        } else {
            pendingElevatorStart = true
        }
        begin(route: route, destination: destination)
    }

    private func begin(route: Route, destination: HallwayGraph.Destination) {
        self.route = route
        self.destination = destination
        let t = RouteTracker(points: route.points.map { Vec2(x: $0.x, y: $0.y) })
        tracker = t
        announcedSoon.removeAll()
        announcedNow.removeAll()
        offRouteSince = nil
        isOffRoute = false
        phase = .navigating
        try? AVAudioSession.sharedInstance().setActive(true)
        UIApplication.shared.isIdleTimerDisabled = true
        haptic.prepare()
        let firstLeg: String
        if let turn = t.turns.first {
            firstLeg = "Walk \(max(1, Int(turn.distanceAlong.rounded()))) meters, then \(turn.spokenTurn)."
        } else {
            firstLeg = "Walk \(max(1, Int(t.total.rounded()))) meters."
        }
        say("Going to \(route.to.name), \(Int(route.lengthMeters.rounded())) meters. \(firstLeg)")
        instruction = firstLeg
    }

    func stop() {
        phase = .idle
        route = nil
        tracker = nil
        destination = nil
        pendingElevatorStart = false
        speech.stopSpeaking(at: .immediate)
        UIApplication.shared.isIdleTimerDisabled = false
        // After an elevator start, go back to recognizing the saved map (if there is one).
        if localization == .noMap, mapSource != nil { runCamera() }
    }

    private func calibrateAtElevator(arPosition: Vec2, arHeading: Double) {
        guard let start = graph.node(graph.startNode) else { return }
        alignment = MapAlignment(arOrigin: [arPosition.x, arPosition.y], planOrigin: [start.x, start.y],
                                 rotationDegrees: graph.startFacingDegrees - arHeading,
                                 checkpoints: [start.id], createdAt: Date())
        arHistory.removeAll()
        pendingElevatorStart = false
    }

    private func reroute(from position: Vec2) {
        guard let destination, let newRoute = graph.route(from: position, to: destination) else { return }
        route = newRoute
        tracker = RouteTracker(points: newRoute.points.map { Vec2(x: $0.x, y: $0.y) })
        announcedSoon.removeAll()
        announcedNow.removeAll()
        isOffRoute = false
        offRouteSince = nil
        say("New route. \(Int(newRoute.lengthMeters.rounded())) meters to \(newRoute.to.name).")
    }

    // MARK: Mapping Mode

    /// Start recording a new map. Begin at the elevator, facing down the hallway.
    func startMapping() {
        let config = ARWorldTrackingConfiguration()
        config.worldAlignment = .gravity
        config.planeDetection = [.horizontal, .vertical]
        session.run(config, options: [.resetTracking, .removeExistingAnchors])
        phase = .mapping
        alignment = nil
        mappingRaw = []
        mappingPath = []
        checkpointAR = []
        checkpointPlan = []
        checkpointsTaken = []
        canSaveMap = false
        mapMessage = nil
        UIApplication.shared.isIdleTimerDisabled = true
    }

    /// "I'm standing at this checkpoint now."
    func markCheckpoint(_ nodeID: String) {
        guard phase == .mapping, trackingReady, let pose = lastFrame, let node = graph.node(nodeID) else {
            mapMessage = "Wait until tracking is ready, then try again."
            return
        }
        checkpointAR.append(pose.position)
        checkpointPlan.append(node.point)
        checkpointsTaken.append(nodeID)
        if checkpointAR.count == 1 {
            // One point: assume the elevator start direction until a second checkpoint fixes rotation.
            let facing = nodeID == graph.startNode ? graph.startFacingDegrees - pose.heading : 0
            alignment = MapAlignment(arOrigin: [pose.position.x, pose.position.y], planOrigin: [node.x, node.y],
                                     rotationDegrees: facing, checkpoints: checkpointsTaken, createdAt: Date())
        } else if let fit = MapAligner.fitRigid(ar: checkpointAR, plan: checkpointPlan) {
            alignment = MapAlignment(arOrigin: [fit.arOrigin.x, fit.arOrigin.y], planOrigin: [fit.planOrigin.x, fit.planOrigin.y],
                                     rotationDegrees: fit.rotationDegrees, checkpoints: checkpointsTaken, createdAt: Date())
        }
        if let alignment { mappingPath = mappingRaw.map(alignment.toPlan) }
        notify.notificationOccurred(.success)
        mapMessage = "Checkpoint saved: \(node.checkpoint ?? node.id)"
    }

    func saveMap() {
        guard var alignment, checkpointsTaken.count >= 2 else {
            mapMessage = "Mark at least 2 checkpoints far apart (for example the elevator and a 430 door)."
            return
        }
        alignment.checkpoints = checkpointsTaken
        if let frame = session.currentFrame {
            session.add(anchor: ARAnchor(name: Self.originAnchorName, transform: frame.camera.transform))
        }
        mapMessage = "Saving the map…"
        session.getCurrentWorldMap { [weak self] map, error in
            DispatchQueue.main.async {
                guard let self else { return }
                guard let map else {
                    self.mapMessage = "Couldn't save the map: \(error?.localizedDescription ?? "unknown error"). Walk a bit more and try again."
                    return
                }
                do {
                    try WorldMapStore.save(map: map, alignment: alignment, name: self.mapName)
                    let size = (try? Data(contentsOf: WorldMapStore.mapURL(self.mapName)).count) ?? 0
                    self.mapMessage = "Map saved (\(size / 1_000_000) MB, \(map.rawFeaturePoints.points.count) points)."
                    self.mapSource = "recorded on this phone"
                } catch {
                    self.mapMessage = "Couldn't save the map: \(error.localizedDescription)"
                }
            }
        }
    }

    /// Leave Mapping Mode and restart tracking with the saved map.
    func endMapping() {
        phase = .idle
        UIApplication.shared.isIdleTimerDisabled = false
        runCamera()
    }

    func deleteSavedMap() {
        WorldMapStore.delete(name: mapName)
        mapMessage = "Saved map deleted."
        if phase == .idle { runCamera() }
    }

    var savedMapFiles: [URL] {
        [WorldMapStore.mapURL(mapName), WorldMapStore.alignmentURL(mapName)]
            .filter { FileManager.default.fileExists(atPath: $0.path) }
    }

    // MARK: ARSessionDelegate

    func session(_ session: ARSession, didUpdate frame: ARFrame) {
        guard frame.timestamp - lastUpdate > 0.1 else { return }
        lastUpdate = frame.timestamp

        updateTrackingState(frame.camera.trackingState)
        guard let pose = Self.topDownPose(frame.camera.transform) else { return }
        lastFrame = pose

        if phase == .mapping {
            updateMapping(frame: frame, pose: pose)
            return
        }

        if localization == .searching {
            detectRelocalization(frame: frame)
        }
        if pendingElevatorStart, trackingReady {
            calibrateAtElevator(arPosition: pose.position, arHeading: pose.heading)
        }

        // Only trust positions once we're located (map) or calibrated (elevator).
        let trusted = localization == .located || (localization == .noMap && phase != .idle && !pendingElevatorStart)
        guard trusted, var alignment else {
            planPosition = nil
            whereYouAre = nil
            return
        }

        var position = alignment.toPlan(pose.position)
        var heading = pose.heading + alignment.rotationDegrees

        if phase == .idle {
            planPosition = position
            planHeading = heading
            whereYouAre = describe(position)
            return
        }
        guard var tracker else { return }

        if useCorridorCorrection {
            arHistory.append(pose.position)
            if arHistory.count > 60 { arHistory.removeFirst(arHistory.count - 60) }
            if let fix = corridorCorrection(arPosition: pose.position, planPosition: position,
                                            heading: alignment.rotationDegrees, tracker: tracker) {
                let pulled = position + (fix.closest - position) * 0.2
                alignment.rotationDegrees += 0.3 * fix.delta
                alignment.arOrigin = [pose.position.x, pose.position.y]
                alignment.planOrigin = [pulled.x, pulled.y]
                self.alignment = alignment
                position = pulled
                heading = pose.heading + alignment.rotationDegrees
            }
        }
        planPosition = position
        planHeading = heading

        let (along, off) = tracker.project(position)
        self.tracker = tracker
        let remaining = max(0, tracker.total - along)
        distanceRemaining = remaining + (off > 1.5 ? off : 0)

        let target = remaining < arrivalRadius
            ? (tracker.points.last ?? position)
            : tracker.point(at: along + (off > 3 ? 1 : lookAhead))
        relativeBearing = RouteTracker.relativeBearing(from: position, headingDegrees: heading, to: target)

        if handleOffRoute(off, position: position, time: frame.timestamp) { return }
        if remaining < arrivalRadius {
            arrive()
            return
        }
        if phase == .navigating {
            announceTurns(tracker: tracker, along: along, remaining: remaining)
        }
    }

    func session(_ session: ARSession, didFailWithError error: Error) {
        trackingMessage = "Camera tracking stopped: \(error.localizedDescription)"
    }

    // MARK: Relocalization

    private func detectRelocalization(frame: ARFrame) {
        if searchingSince == nil { searchingSince = frame.timestamp }
        if case .limited(.relocalizing) = frame.camera.trackingState { sawRelocalizing = true }
        let anchorBack = frame.anchors.contains { $0.name == Self.originAnchorName }
        if case .normal = frame.camera.trackingState, anchorBack || sawRelocalizing {
            localization = .located
            notify.notificationOccurred(.success)
            say("Found you on the map.")
            return
        }
        if let since = searchingSince, frame.timestamp - since > 20 {
            trackingMessage = "Still looking. Point the camera down the hallway, or start at the elevator."
        }
    }

    private func describe(_ p: Vec2) -> String {
        var best: (String, Double)?
        for d in graph.destinations {
            for id in d.doors {
                guard let n = graph.node(id) else { continue }
                let dist = (n.point - p).length
                if best == nil || dist < best!.1 {
                    best = (d.id == "elevator" ? "the elevator" : "\(d.title) \(d.subtitle)", dist)
                }
            }
        }
        guard let best else { return "On the map" }
        return best.1 < 6 ? "Near \(best.0)" : "In the hallway, \(Int(best.1.rounded())) m from \(best.0)"
    }

    // MARK: Mapping updates

    private func updateMapping(frame: ARFrame, pose: (position: Vec2, heading: Double)) {
        if mappingRaw.last.map({ (pose.position - $0).length > 0.3 }) ?? true {
            mappingRaw.append(pose.position)
            if let alignment { mappingPath = mappingRaw.map(alignment.toPlan) }
        }
        if let alignment {
            planPosition = alignment.toPlan(pose.position)
            planHeading = pose.heading + alignment.rotationDegrees
        }
        switch frame.worldMappingStatus {
        case .notAvailable: mappingStatus = "Not enough seen yet. Move slowly."
        case .limited: mappingStatus = "Keep walking slowly and look around."
        case .extending: mappingStatus = "Mapping new area."
        case .mapped: mappingStatus = "This area is well mapped."
        @unknown default: mappingStatus = ""
        }
        let goodEnough = frame.worldMappingStatus == .mapped || frame.worldMappingStatus == .extending
        canSaveMap = goodEnough && checkpointsTaken.count >= 2
    }

    // MARK: Guidance

    private func corridorCorrection(arPosition: Vec2, planPosition: Vec2, heading rotation: Double,
                                    tracker: RouteTracker) -> (delta: Double, closest: Vec2)? {
        guard arHistory.count >= 2 else { return nil }
        var oldIndex: Int?
        for i in stride(from: arHistory.count - 2, through: 0, by: -1)
        where (arPosition - arHistory[i]).length >= 3 {
            oldIndex = i
            break
        }
        guard let oldIndex else { return nil }
        let old = arHistory[oldIndex]
        let chord = arPosition - old
        let n = chord.length
        for p in arHistory[oldIndex...] {
            if abs(chord.x * (p.y - old.y) - chord.y * (p.x - old.x)) / n > 0.4 { return nil }
        }
        return tracker.bestParallelSegment(near: planPosition, walkingDegrees: chord.angleDegrees + rotation)
    }

    private func announceTurns(tracker: RouteTracker, along: Double, remaining: Double) {
        guard let turn = tracker.nextTurn(after: along) else {
            instruction = "\(Int(remaining.rounded())) meters to \(route?.to.name ?? "your destination")"
            return
        }
        let toTurn = turn.distanceAlong - along
        if toTurn <= 1.2, !announcedNow.contains(turn.vertex) {
            announcedNow.insert(turn.vertex)
            announcedSoon.insert(turn.vertex)
            say("\(turn.spokenTurn.capitalizedFirst) now, then walk \(Int(turn.nextStretchMeters.rounded())) meters.")
            buzz(turn.degrees > 0 ? 2 : 3)
        } else if toTurn <= 4, !announcedSoon.contains(turn.vertex) {
            announcedSoon.insert(turn.vertex)
            say("In \(max(1, Int(toTurn.rounded()))) meters, \(turn.spokenTurn).")
        }
        instruction = toTurn > 1.2
            ? "In \(max(1, Int(toTurn.rounded()))) m, \(turn.spokenTurn)"
            : turn.spokenTurn.capitalizedFirst
    }

    /// Returns true if it rerouted.
    private func handleOffRoute(_ off: Double, position: Vec2, time: TimeInterval) -> Bool {
        if off > 3 {
            if offRouteSince == nil { offRouteSince = time }
            if let since = offRouteSince, time - since > 3 {
                if localization == .located, phase == .navigating {
                    // We trust the map position, so plan a new route from here.
                    reroute(from: position)
                    return true
                }
                if !isOffRoute {
                    isOffRoute = true
                    say("You're off the route. Turn until the phone vibrates, then walk.")
                }
            }
        } else {
            offRouteSince = nil
            if isOffRoute {
                isOffRoute = false
                say("Back on the route.")
            }
        }
        return false
    }

    private func arrive() {
        guard phase == .navigating else { return }
        phase = .arrived
        instruction = route?.arrivalSentence ?? "You've arrived"
        say(instruction)
        notify.notificationOccurred(.success)
        UIApplication.shared.isIdleTimerDisabled = false
    }

    private func updateTrackingState(_ state: ARCamera.TrackingState) {
        switch state {
        case .normal:
            trackingReady = true
            trackingMessage = nil
        case .notAvailable:
            trackingReady = false
            trackingMessage = "Starting the camera…"
        case .limited(let reason):
            trackingReady = false
            switch reason {
            case .excessiveMotion: trackingMessage = "Slow down a little"
            case .insufficientFeatures: trackingMessage = "Point the camera at the hallway, not a blank wall"
            case .relocalizing: trackingMessage = "Look around slowly so the app can recognize where you are"
            case .initializing: trackingMessage = "Move the phone slowly from side to side"
            @unknown default: trackingMessage = "Hold the phone steady"
            }
        }
    }

    private func say(_ text: String) {
        let utterance = AVSpeechUtterance(string: text)
        utterance.rate = AVSpeechUtteranceDefaultSpeechRate
        speech.stopSpeaking(at: .word)
        speech.speak(utterance)
    }

    /// Two pulses = turn left, three = turn right.
    private func buzz(_ count: Int) {
        for i in 0..<count {
            DispatchQueue.main.asyncAfter(deadline: .now() + Double(i) * 0.22) { [haptic] in
                haptic.impactOccurred(intensity: 1.0)
            }
        }
    }

    // MARK: Pose helpers

    /// Phone position and facing direction seen from above, in ARKit's world.
    /// Top-down coordinates are (x, -z) so the view isn't mirrored (ARKit's y is up).
    static func topDownPose(_ t: simd_float4x4) -> (position: Vec2, heading: Double)? {
        let position = Vec2(x: Double(t.columns.3.x), y: Double(-t.columns.3.z))
        // Held upright, the camera looks along -z. Held flat, use the top edge of the phone (ARKit's -x in portrait).
        let back = t.columns.2
        var forward = Vec2(x: Double(-back.x), y: Double(back.z))
        if forward.length < 0.5 {
            let side = t.columns.0
            forward = Vec2(x: Double(-side.x), y: Double(side.z))
        }
        guard forward.length > 0.1 else { return nil }
        return (position, forward.angleDegrees)
    }
}

private extension String {
    var capitalizedFirst: String { prefix(1).uppercased() + dropFirst() }
}
