import ARKit
import SceneKit
import AVFoundation
import Combine
import UIKit

/// Tracks the phone with ARKit, places it on the floor plan, routes to a destination,
/// and turns the route into arrow directions, spoken steps and vibration.
///
/// Where you start: you tell the app which landmark you're next to (a room door or the
/// elevator) and stand in front of it, facing the door. That pins your position and
/// direction on the plan using a measured doorway offset. ARKit follows relative
/// movement without snapping to an assumed corridor. Tracking loss requires recalibration.
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
    @Published private(set) var guidanceReady = false
    @Published private(set) var alignmentMessage: String?
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
    private var lastUpdate: TimeInterval = 0
    private var lastFrame: (position: Vec2, heading: Double)?
    private var lastPoseTime: TimeInterval = 0
    private var cameraStarted = false

    private var announcedSoon = Set<Int>()
    private var announcedNow = Set<Int>()
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
        if cameraStarted {
            // Keep the same world frame when returning from another screen.
            session.run(config)
        } else {
            cameraStarted = true
            lastFrame = nil
            lastUpdate = 0
            floorPath.resetFloor()
            session.run(config, options: [.resetTracking, .removeExistingAnchors])
        }
    }

    func pauseCamera() {
        suspendGuidance("Camera paused. Recalibrate at a known doorway.")
        session.pause()
    }

    func suspendGuidance(_ message: String) {
        guidanceReady = false
        alignmentMessage = message
        alignment = nil
        lastFrame = nil
        isAligned = false
        planPosition = nil
        remainingPlanPath = []
        floorPath.resetFloor()
        narration.stop()
    }

    func checkTrackingFreshness() {
        if phase != .idle, guidanceReady,
           ProcessInfo.processInfo.systemUptime - lastPoseTime > 0.75 {
            trackingReady = false
            suspendGuidance("Camera updates stopped. Recalibrate after tracking recovers.")
        }
    }

    // MARK: Navigation

    /// You're standing in front of `landmark`'s door, facing it. Route to `destination`.
    func start(at landmark: HallwayGraph.Node, to destination: HallwayGraph.Destination, manualTest: Bool = false, doorDistance: Double = 0.5) {
        startError = nil
        guard NavigationAccess.permitsStart(verified: Self.guidanceEnabled, manualTest: manualTest) else {
            startError = "Enable the manual test or wait for map verification."
            return
        }
        guard trackingReady, let frame = lastFrame,
              ProcessInfo.processInfo.systemUptime - lastPoseTime < 0.75 else {
            startError = "Wait for camera tracking, then try Start again."
            return
        }
        guard let standingPoint = landmark.standingPoint(distanceFromDoor: doorDistance),
              let facing = landmark.facingDoorDegrees else {
            startError = "Choose a mapped doorway and enter your measured distance from it."
            return
        }
        guard let route = graph.route(from: standingPoint, to: destination,
                                      fromName: landmark.landmark ?? landmark.id) else {
            startError = "No route connects these locations. Choose another destination."
            return
        }
        isManualTest = !Self.guidanceEnabled && manualTest
        alignment = PlanAlignment(arOrigin: frame.position, planOrigin: standingPoint,
                                  rotationDegrees: facing - frame.heading)
        guidanceReady = true
        alignmentMessage = "Doorway calibration set; map remains unverified."
        self.route = route
        self.destination = destination
        let t = RouteTracker(points: route.points.map { Vec2(x: $0.x, y: $0.y) })
        tracker = t
        arrivalDoor = Self.door(at: route, in: graph)
        isAligned = false
        announcedSoon.removeAll()
        announcedNow.removeAll()
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

    func stop() {
        guidanceReady = false
        alignmentMessage = nil
        isManualTest = false
        startError = nil
        phase = .idle
        route = nil
        tracker = nil
        destination = nil
        alignment = nil
        planPosition = nil
        isAligned = false
        floorPath.hide()
        remainingPlanPath = []
        narration.stop()
        UIApplication.shared.isIdleTimerDisabled = false
    }

    // MARK: ARSessionDelegate

    func session(_ session: ARSession, didUpdate frame: ARFrame) {
        guard frame.timestamp - lastUpdate > 0.1 else { return }
        lastUpdate = frame.timestamp

        updateTrackingState(frame.camera.trackingState)
        guard trackingReady else {
            if phase != .idle { suspendGuidance("Tracking lost. Recalibrate at a known doorway.") }
            lastFrame = nil
            return
        }
        guard let pose = Self.topDownPose(frame.camera.transform) else {
            lastFrame = nil
            guidanceReady = false
            alignmentMessage = "Hold the phone upright, facing the hallway."
            floorPath.hide()
            narration.stop()
            return
        }
        lastFrame = pose
        lastPoseTime = ProcessInfo.processInfo.systemUptime
        guard phase != .idle, let alignment, var tracker else { return }
        guidanceReady = true
        alignmentMessage = "Doorway calibration set; map remains unverified."
        let position = alignment.toPlan(pose.position)
        let heading = pose.heading + alignment.rotationDegrees

        // Do not snap the measured pose toward the intended route. That hides genuine
        // lateral errors and can rotate the overlay into an adjacent hallway.
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
        let planPath = tracker.remainingPath(from: along)
        remainingPlanPath = planPath
        if off <= 2, let floorY = floorPath.floorHeight(frame) {
            floorPath.update(path: planPath.map { PathPoint(point: alignment.toAR($0.point), along: $0.along) },
                             floorY: floorY + 0.01)
        } else {
            floorPath.hide()
            alignmentMessage = off > 2
                ? "Position is away from the mapped corridor. Stop and recalibrate."
                : "Look toward the floor to place the path."
        }
        if off > 2 {
            isOffRoute = true
            suspendGuidance("Position is away from the mapped corridor. Recalibrate at a doorway.")
            return
        }

        relativeBearing = RouteTracker.wrap(heading - tracker.pathDirection(at: along, position: position))
        let error = abs(relativeBearing)
        if isAligned ? error > ExitArrowView.alignedTolerance + 8 : error <= ExitArrowView.alignedTolerance {
            isAligned.toggle()
        }

        if remaining < arrivalRadius, off < arrivalRadius,
           let endpoint = tracker.points.last, (position - endpoint).length < arrivalRadius {
            arrive()
            return
        }
        announceTurns(tracker: tracker, along: along, remaining: remaining)
    }

    func session(_ session: ARSession, didFailWithError error: Error) {
        trackingReady = false
        suspendGuidance("Camera tracking failed. Recalibrate after tracking recovers.")
        trackingMessage = "Camera tracking stopped: \(error.localizedDescription)"
    }

    func sessionWasInterrupted(_ session: ARSession) {
        trackingReady = false
        suspendGuidance("Camera interrupted. Recalibrate at a known doorway.")
    }

    func sessionInterruptionEnded(_ session: ARSession) {
        trackingReady = false
        lastFrame = nil
        trackingMessage = "Recovering camera tracking…"
    }

    // MARK: Guidance

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
        // Camera optical forward stays the same axis at every tilt. A nearly vertical
        // camera has no reliable horizontal heading; do not substitute a different axis.
        let back = t.columns.2
        let forward = Vec2(x: Double(-back.x), y: Double(back.z))
        guard let heading = PlanAlignment.cameraHeading(forward: forward) else { return nil }
        return (position, heading)
    }
}

private extension String {
    var capitalizedFirst: String { self.prefix(1).uppercased() + dropFirst() }
}
