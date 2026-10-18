import ARKit
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
}

/// Tracks the phone with ARKit, places it on the floor plan, routes to a destination,
/// and turns the route into arrow directions, spoken steps and vibration.
///
/// Where you start: you tell the app which landmark you're next to (a room door or the
/// elevator) and stand in front of it, facing the door. That pins your position and
/// direction on the plan. ARKit follows every step from there; walking straight down a
/// hallway corrects any error in the starting direction, and you can re-pin at any
/// landmark you pass.
final class RouteNavigator: NSObject, ObservableObject, ARSessionDelegate {
    enum Phase: Equatable { case idle, navigating, arrived }

    // MARK: Published state

    @Published private(set) var phase: Phase = .idle
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

    let session = ARSession()
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

    private let speech = AVSpeechSynthesizer()
    private let haptic = UIImpactFeedbackGenerator(style: .heavy)
    private let notify = UINotificationFeedbackGenerator()

    private let lookAhead = 2.5
    private let arrivalRadius = 1.5

    init(graph: HallwayGraph) {
        self.graph = graph
        super.init()
        session.delegate = self
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
        config.planeDetection = [.horizontal]
        session.run(config, options: [.resetTracking, .removeExistingAnchors])
    }

    func pauseCamera() { session.pause() }

    // MARK: Navigation

    /// You're standing in front of `landmark`'s door, facing it. Route to `destination`.
    func start(at landmark: HallwayGraph.Node, to destination: HallwayGraph.Destination) {
        guard let route = graph.route(from: landmark.point, to: destination,
                                      fromName: landmark.landmark ?? landmark.id) else { return }
        if let frame = lastFrame, trackingReady {
            pin(at: landmark, arPosition: frame.position, arHeading: frame.heading, keepDirection: false)
        } else {
            pendingStart = landmark
        }
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
        say(opening)
        instruction = "Turn until the arrow is green, then walk"
    }

    /// "I'm next to this landmark right now" during a walk: fixes position drift.
    /// Keeps the current direction estimate (you don't need to face the door).
    func repin(at landmark: HallwayGraph.Node) {
        guard let frame = lastFrame, trackingReady else { return }
        pin(at: landmark, arPosition: frame.position, arHeading: frame.heading, keepDirection: true)
        if let destination, let newRoute = graph.route(from: landmark.point, to: destination) {
            route = newRoute
            tracker = RouteTracker(points: newRoute.points.map { Vec2(x: $0.x, y: $0.y) })
            announcedSoon.removeAll()
            announcedNow.removeAll()
            if phase == .arrived { phase = .navigating }
        }
        notify.notificationOccurred(.success)
        say("Got it, you're at \(landmark.landmark ?? landmark.id).")
    }

    func stop() {
        phase = .idle
        route = nil
        tracker = nil
        destination = nil
        pendingStart = nil
        alignment = nil
        planPosition = nil
        speech.stopSpeaking(at: .immediate)
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
        distanceRemaining = remaining + (off > 1.5 ? off : 0)

        let target = remaining < arrivalRadius
            ? (tracker.points.last ?? position)
            : tracker.point(at: along + (off > 3 ? 1 : lookAhead))
        relativeBearing = RouteTracker.relativeBearing(from: position, headingDegrees: heading, to: target)

        handleOffRoute(off, time: frame.timestamp)
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

    private func handleOffRoute(_ off: Double, time: TimeInterval) {
        if off > 3 {
            if offRouteSince == nil { offRouteSince = time }
            if !isOffRoute, let since = offRouteSince, time - since > 2 {
                isOffRoute = true
                say("You're off the route. Turn until the phone vibrates, then walk. If you're next to a room, tap I'm at a landmark.")
            }
        } else {
            offRouteSince = nil
            if isOffRoute {
                isOffRoute = false
                say("Back on the route.")
            }
        }
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
