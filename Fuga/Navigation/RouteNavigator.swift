import ARKit
import SceneKit
import AVFoundation
import Combine
import UIKit

/// How ARKit's world (top-down x, -z) lines up with the floor plan:
/// plan = planOrigin + rotate(ar - arOrigin, by: rotationDegrees).
struct PlanAlignment {
    var arOrigin: Vec2
    var planOrigin: Vec2
    var rotationDegrees: Double

    func toPlan(_ ar: Vec2) -> Vec2 {
        planOrigin + (ar - arOrigin).rotated(byDegrees: rotationDegrees)
    }

    func toAR(_ plan: Vec2) -> Vec2 {
        arOrigin + (plan - planOrigin).rotated(byDegrees: -rotationDegrees)
    }
}

/// Tracks the phone with ARKit, places it on the floor plan, routes to a destination,
/// and turns the route into arrow directions, spoken steps and vibration.
///
/// Where you start: you tell the app which landmark you're next to (a room door or the
/// elevator) and stand in front of it, facing the door. That pins your position and
/// direction on the plan. ARKit follows every step from there; walking straight down a
/// hallway corrects any error in the starting direction, and you can re-pin at any
/// landmark you pass.
@MainActor
final class RouteNavigator: NSObject, ObservableObject, ARSessionDelegate {
    // Route graph coordinates are not registered to the canonical scan, and no
    // doorway/path anchors are verified. Automatic/release guidance remains blocked;
    // a developer build can explicitly opt into a manual test.
    static let guidanceEnabled = false
    enum Phase: Equatable { case idle, navigating, arrived }

    // MARK: Published state

    @Published private(set) var startError: String?
    @Published private(set) var isManualTest = false
    @Published private(set) var phase: Phase = .idle
    @Published private(set) var trackingReady = false
    @Published private(set) var trackingMessage: String? = "Starting the camera…"
    @Published private(set) var relativeBearing: Double = 0
    @Published private(set) var distanceRemaining: Double = 0
    @Published private(set) var instruction = ""
    @Published private(set) var isOffRoute = false
    /// Facing the way the arrow points (the arrow turns green). Has a little hysteresis so it doesn't flicker.
    @Published private(set) var isAligned = false
    @Published private(set) var planPosition: Vec2?
    @Published private(set) var planHeading: Double = 0
    @Published private(set) var route: Route?
    @Published private(set) var destination: HallwayGraph.Destination?
    /// The rest of the route, from you to the destination, in plan meters (for the 3D view).
    @Published private(set) var remainingPlanPath: [PathPoint] = []

    let session = ARSession()

    /// True while a turn instruction or arrival is being spoken (other voice cues wait).
    var isSpeaking: Bool { narration.isSpeaking }
    /// The pulsing green line on the floor (added to the camera view's 3D scene).
    let floorPath = FloorPathNode()
    let graph: HallwayGraph

    // MARK: Private state

    private var alignment: PlanAlignment?
    private var tracker: RouteTracker?
    private var pendingStart: HallwayGraph.Node?
    private var lastUpdate: TimeInterval = 0
    private var lastFrame: (position: Vec2, heading: Double)?
    private var arHistory: [Vec2] = []

    private var announcedSoon = Set<Int>()
    private var announcedNow = Set<Int>()
    private var offRouteSince: TimeInterval?
    private var arrivalDoor: Vec2?

    let narration = VoiceGuidance()

    private let arrivalRadius = 1.5

    init(graph: HallwayGraph) {
        self.graph = graph
        super.init()
        session.delegate = self
        session.delegateQueue = .main
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .spokenAudio, options: [.duckOthers])
    }

    // MARK: Camera

    func runCamera() {
        guard ARWorldTrackingConfiguration.isSupported else {
            trackingMessage = "This iPhone doesn't support ARKit world tracking."
            return
        }
        let config = ARWorldTrackingConfiguration()
        config.worldAlignment = .gravity
        // Horizontal planes find the floor for the green path; vertical planes (and the LiDAR mesh on
        // Pro iPhones) are walls, which hide the path where it goes around a corner.
        config.planeDetection = [.horizontal, .vertical]
        if ARWorldTrackingConfiguration.supportsSceneReconstruction(.mesh) {
            config.sceneReconstruction = .mesh
            floorPath.fadeEnd = 30   // real walls hide the path, so it can run further
        }
        session.run(config, options: [.resetTracking, .removeExistingAnchors])
    }

    func pauseCamera() { session.pause() }

    // MARK: Navigation

    /// You're standing in front of `landmark`'s door, facing it. Route to `destination`.
    func start(at landmark: HallwayGraph.Node, to destination: HallwayGraph.Destination, manualTest: Bool = false) {
        startError = nil
        guard NavigationAccess.permitsStart(verified: Self.guidanceEnabled, manualTest: manualTest) else {
            startError = "Enable the manual test or wait for map verification."
            return
        }
        guard trackingReady, lastFrame != nil else {
            startError = "Wait for camera tracking, then try Start again."
            return
        }
        guard let route = graph.route(from: landmark.point, to: destination,
                                      fromName: landmark.landmark ?? landmark.id) else {
            startError = "No route connects these locations. Choose another destination."
            return
        }
        isManualTest = !Self.guidanceEnabled && manualTest
        if let frame = lastFrame, trackingReady {
            pin(at: landmark, arPosition: frame.position, arHeading: frame.heading, keepDirection: false)
        } else {
            pendingStart = landmark
        }
        self.route = route
        self.destination = destination
        let t = RouteTracker(points: route.points.map { Vec2(x: $0.x, y: $0.y) })
        tracker = t
        arrivalDoor = Self.door(at: route, in: graph)
        isAligned = false
        announcedSoon.removeAll()
        announcedNow.removeAll()
        offRouteSince = nil
        isOffRoute = false
        phase = .navigating
        try? AVAudioSession.sharedInstance().setActive(true)
        UIApplication.shared.isIdleTimerDisabled = true

        // You start facing the door, so the first instruction is usually to turn around.
        var opening = "Going to \(route.to.name), \(Int(route.lengthMeters.rounded())) meters."
        if let facing = landmark.facingDoorDegrees, route.points.count >= 2 {
            let first = Vec2(x: route.points[1].x - route.points[0].x, y: route.points[1].y - route.points[0].y)
            opening += " " + Self.turnToFace(from: facing, to: first.angleDegrees) + "."
        }
        if let turn = t.turns.first {
            opening += " Walk \(max(1, Int(turn.distanceAlong.rounded()))) meters, then \(turn.spokenTurn)."
        } else {
            opening += " Walk \(max(1, Int(t.total.rounded()))) meters."
        }
        say(.starting)
        instruction = opening
    }

    /// "I'm next to this landmark right now" during a walk: fixes position drift.
    /// Keeps the current direction estimate (you don't need to face the door).
    func repin(at landmark: HallwayGraph.Node) {
        guard NavigationAccess.permitsStart(verified: Self.guidanceEnabled, manualTest: isManualTest) else { return }
        guard let frame = lastFrame, trackingReady else { return }
        pin(at: landmark, arPosition: frame.position, arHeading: frame.heading, keepDirection: true)
        if let destination, let newRoute = graph.route(from: landmark.point, to: destination) {
            route = newRoute
            tracker = RouteTracker(points: newRoute.points.map { Vec2(x: $0.x, y: $0.y) })
            arrivalDoor = Self.door(at: newRoute, in: graph)
            announcedSoon.removeAll()
            announcedNow.removeAll()
            if phase == .arrived {
                phase = .navigating
            }
        }
        say(.repinned)
    }

    func stop() {
        isManualTest = false
        startError = nil
        phase = .idle
        route = nil
        tracker = nil
        destination = nil
        pendingStart = nil
        alignment = nil
        planPosition = nil
        isAligned = false
        floorPath.hide()
        remainingPlanPath = []
        narration.stop()
        UIApplication.shared.isIdleTimerDisabled = false
    }

    private func pin(at landmark: HallwayGraph.Node, arPosition: Vec2, arHeading: Double, keepDirection: Bool) {
        let rotation: Double
        if keepDirection, let current = alignment {
            rotation = current.rotationDegrees
        } else {
            rotation = (landmark.facingDoorDegrees ?? 0) - arHeading
        }
        alignment = PlanAlignment(arOrigin: arPosition, planOrigin: landmark.point, rotationDegrees: rotation)
        arHistory.removeAll()
        pendingStart = nil
    }

    // MARK: ARSessionDelegate

    func session(_ session: ARSession, didUpdate frame: ARFrame) {
        guard frame.timestamp - lastUpdate > 0.1 else { return }
        lastUpdate = frame.timestamp

        updateTrackingState(frame.camera.trackingState)
        guard let pose = Self.topDownPose(frame.camera.transform) else { return }
        lastFrame = pose

        if let landmark = pendingStart, trackingReady {
            pin(at: landmark, arPosition: pose.position, arHeading: pose.heading, keepDirection: false)
        }
        guard phase != .idle, pendingStart == nil, var alignment, var tracker else { return }

        var position = alignment.toPlan(pose.position)
        var heading = pose.heading + alignment.rotationDegrees

        // Hallway heading correction: a straight 3 m walk next to a long route segment tells us
        // which way the hallway really runs (fixes not facing the door squarely at Start).
        arHistory.append(pose.position)
        if arHistory.count > 60 { arHistory.removeFirst(arHistory.count - 60) }
        if let fix = corridorCorrection(arPosition: pose.position, planPosition: position,
                                        rotation: alignment.rotationDegrees, tracker: tracker) {
            let pulled = position + (fix.closest - position) * 0.2
            alignment = PlanAlignment(arOrigin: pose.position, planOrigin: pulled,
                                      rotationDegrees: alignment.rotationDegrees + 0.3 * fix.delta)
            self.alignment = alignment
            position = pulled
            heading = pose.heading + alignment.rotationDegrees
        }
        planPosition = position
        planHeading = heading

        let (along, off) = tracker.project(position)
        self.tracker = tracker
        let remaining = max(0, tracker.total - along)

        if phase == .arrived {
            // You're there: the arrow points at the door itself.
            distanceRemaining = 0
            if let door = arrivalDoor {
                relativeBearing = RouteTracker.relativeBearing(from: position, headingDegrees: heading, to: door)
            }
            return
        }

        // Distance = how far you still have to walk to the destination along the route.
        distanceRemaining = remaining

        // Green line on the floor from you to the destination, in ARKit's coordinates.
        var planPath = tracker.remainingPath(from: along)
        if off > 1 { planPath.insert(PathPoint(point: position, along: along), at: 0) }
        remainingPlanPath = planPath
        floorPath.update(path: planPath.map { PathPoint(point: alignment.toAR($0.point), along: $0.along) },
                         floorY: floorPath.floorHeight(frame) + 0.01)

        // The arrow follows the path drawn on the map. Far off it, point straight back to it.
        if off > 3 {
            relativeBearing = RouteTracker.relativeBearing(from: position, headingDegrees: heading,
                                                           to: tracker.point(at: along + 1))
        } else {
            relativeBearing = RouteTracker.wrap(heading - tracker.pathDirection(at: along, position: position))
        }
        let error = abs(relativeBearing)
        if isAligned ? error > ExitArrowView.alignedTolerance + 8 : error <= ExitArrowView.alignedTolerance {
            isAligned.toggle()
        }

        handleOffRoute(off, time: frame.timestamp)
        if remaining < arrivalRadius {
            arrive()
            return
        }
        announceTurns(tracker: tracker, along: along, remaining: remaining)
    }

    func session(_ session: ARSession, didFailWithError error: Error) {
        trackingMessage = "Camera tracking stopped: \(error.localizedDescription)"
    }

    // MARK: Guidance

    private func corridorCorrection(arPosition: Vec2, planPosition: Vec2, rotation: Double,
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
            say(turn.direction == "left" ? .left : .right)
        } else if toTurn <= 4, !announcedSoon.contains(turn.vertex) {
            announcedSoon.insert(turn.vertex)
            say(turn.direction == "left" ? .leftSoon : .rightSoon)
        }
        instruction = toTurn > 1.2
            ? "In \(max(1, Int(toTurn.rounded()))) m, \(turn.spokenTurn)"
            : turn.spokenTurn.capitalizedFirst
    }

    private func handleOffRoute(_ off: Double, time: TimeInterval) {
        if off > 3 {
            if offRouteSince == nil { offRouteSince = time }
            if !isOffRoute, let since = offRouteSince, time - since > 2 {
                isOffRoute = true
                say(.offRoute)
            }
        } else {
            offRouteSince = nil
            if isOffRoute {
                isOffRoute = false
                say(.backOnRoute)
            }
        }
    }

    private func arrive() {
        guard phase == .navigating else { return }
        phase = .arrived
        isAligned = false
        distanceRemaining = 0
        instruction = route?.arrivalSentence ?? "You've arrived"
        say(.arrived)
        floorPath.hide()
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
            case .initializing, .relocalizing: trackingMessage = "Move the phone slowly from side to side"
            @unknown default: trackingMessage = "Hold the phone steady"
            }
        }
    }

    /// "Turn around", "Turn left", … to go from facing one plan direction to another.
    static func turnToFace(from facing: Double, to direction: Double) -> String {
        let d = RouteTracker.wrap(direction - facing)  // + = counter-clockwise = left
        if abs(d) > 135 { return "Turn around" }
        if abs(d) < 30 { return "Go straight ahead" }
        return d > 0 ? "Turn left" : "Turn right"
    }

    private func say(_ cue: VoiceCue) {
        narration.announce(cue)
    }

    /// The door of the room the route ends at (routes end on the hallway outside it).
    static func door(at route: Route, in graph: HallwayGraph) -> Vec2? {
        guard let end = route.points.last else { return nil }
        let e = Vec2(x: end.x, y: end.y)
        return graph.nodes.filter { $0.door != nil }
            .min { ($0.point - e).length < ($1.point - e).length }
            .flatMap { ($0.point - e).length < 1 ? $0.door : nil }
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
    var capitalizedFirst: String { self.prefix(1).uppercased() + dropFirst() }
}
