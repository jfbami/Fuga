import ARKit
import AVFoundation
import Combine
import UIKit

/// Tracks the phone with ARKit, places it on the floor plan, and turns a Route into
/// arrow directions, spoken steps and vibration.
///
/// Calibration: when the person taps Start they are at the route's first point, facing
/// `StartPoint.facingDegrees`. From then on ARKit's motion tracking moves them on the plan.
final class RouteNavigator: NSObject, ObservableObject, ARSessionDelegate {
    enum Phase: Equatable {
        case idle          // camera running, waiting for Start
        case navigating
        case arrived
    }

    // MARK: Published state for the UI

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

    let session = ARSession()

    // MARK: Private state

    private var tracker: RouteTracker?
    private var startPoint: StartPoint?
    /// AR -> plan: plan = origin + rotate(arPoint - arOrigin, by: rotation)
    private var arOrigin = Vec2(x: 0, y: 0)
    private var rotation: Double = 0
    private var planOrigin = Vec2(x: 0, y: 0)
    private var pendingStart = false
    private var lastUpdate: TimeInterval = 0
    private var lastFrame: (position: Vec2, heading: Double)?

    /// Recent ARKit positions (top-down), newest last, for the hallway heading correction.
    private var arHistory: [Vec2] = []

    private var announcedSoon = Set<Int>()
    private var announcedNow = Set<Int>()
    private var offRouteSince: TimeInterval?

    private let speech = AVSpeechSynthesizer()
    private let haptic = UIImpactFeedbackGenerator(style: .heavy)
    private let notify = UINotificationFeedbackGenerator()

    /// How far ahead on the route the arrow aims, in meters.
    private let lookAhead = 2.5
    /// Within this distance of the destination we call it arrived.
    private let arrivalRadius = 1.5

    override init() {
        super.init()
        session.delegate = self
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .spokenAudio, options: [.duckOthers])
    }

    // MARK: Session

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

    func pauseCamera() {
        session.pause()
    }

    // MARK: Navigation

    /// Call when the person is standing at the start, facing the start direction.
    func start(route: Route, from start: StartPoint) {
        self.route = route
        self.startPoint = start
        tracker = RouteTracker(points: route.points.map { Vec2(x: $0.x, y: $0.y) })
        announcedSoon.removeAll()
        announcedNow.removeAll()
        offRouteSince = nil
        isOffRoute = false
        if let frame = lastFrame, trackingReady {
            calibrate(arPosition: frame.position, arHeading: frame.heading)
        } else {
            pendingStart = true
        }
        phase = .navigating
        try? AVAudioSession.sharedInstance().setActive(true)
        UIApplication.shared.isIdleTimerDisabled = true
        haptic.prepare()

        let meters = Int(route.lengthMeters.rounded())
        var opening = "Going to \(route.to.name), \(meters) meters."
        if let first = route.steps.first(where: { $0.action == "walk" }) {
            opening += " \(first.say)."
        }
        say(opening)
        instruction = route.steps.first?.say ?? ""
    }

    func stop() {
        phase = .idle
        route = nil
        tracker = nil
        pendingStart = false
        speech.stopSpeaking(at: .immediate)
        UIApplication.shared.isIdleTimerDisabled = false
    }

    /// Re-pin the person to the start point (if they walked back to the elevator to try again).
    func recalibrateAtStart() {
        guard let route, let startPoint else { return }
        start(route: route, from: startPoint)
    }

    private func calibrate(arPosition: Vec2, arHeading: Double) {
        guard let route, let startPoint else { return }
        arOrigin = arPosition
        planOrigin = Vec2(x: route.points[0].x, y: route.points[0].y)
        rotation = startPoint.facingDegrees - arHeading
        arHistory.removeAll()
        pendingStart = false
    }

    /// If the last 3+ m of walking was a straight line next to a long route segment, nudge the
    /// heading toward that segment and pull the position gently onto it. This fixes the error from
    /// not facing exactly down the hallway at Start (checked by replaying the MGH scan: start errors
    /// of ±28° settle to within ~4°).
    private func corridorCorrection(arPosition: Vec2, planPosition: Vec2, tracker: RouteTracker) -> (delta: Double, closest: Vec2)? {
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
        // Straight enough? No recent point more than 0.4 m off the line.
        for p in arHistory[oldIndex...] {
            let offLine = abs(chord.x * (p.y - old.y) - chord.y * (p.x - old.x)) / n
            if offLine > 0.4 { return nil }
        }
        return tracker.bestParallelSegment(near: planPosition, walkingDegrees: chord.angleDegrees + rotation)
    }

    // MARK: ARSessionDelegate

    func session(_ session: ARSession, didUpdate frame: ARFrame) {
        // ~10 updates a second is plenty for walking.
        guard frame.timestamp - lastUpdate > 0.1 else { return }
        lastUpdate = frame.timestamp

        updateTrackingState(frame.camera.trackingState)
        guard let pose = Self.topDownPose(frame.camera.transform) else { return }
        lastFrame = pose

        if pendingStart, trackingReady {
            calibrate(arPosition: pose.position, arHeading: pose.heading)
        }
        // Keep updating after arrival so the arrow keeps pointing at the door.
        guard phase != .idle, !pendingStart, var tracker else { return }

        var position = planOrigin + (pose.position - arOrigin).rotated(byDegrees: rotation)
        var heading = pose.heading + rotation

        arHistory.append(pose.position)
        if arHistory.count > 60 { arHistory.removeFirst(arHistory.count - 60) }
        if let fix = corridorCorrection(arPosition: pose.position, planPosition: position, tracker: tracker) {
            let pulled = position + (fix.closest - position) * 0.2
            rotation += 0.3 * fix.delta
            // Re-anchor so the corrected position is where we are now.
            arOrigin = pose.position
            planOrigin = pulled
            position = pulled
            heading = pose.heading + rotation
        }
        planPosition = position
        planHeading = heading

        let (along, off) = tracker.project(position)
        self.tracker = tracker
        let remaining = max(0, tracker.total - along)
        distanceRemaining = remaining + (off > 1.5 ? off : 0)

        // Arrow: aim a little ahead along the route (or back onto it if we've wandered off).
        let target = tracker.point(at: along + (off > 3 ? 1 : lookAhead))
        relativeBearing = remaining < arrivalRadius
            ? RouteTracker.relativeBearing(from: position, headingDegrees: heading, to: tracker.points.last ?? target)
            : RouteTracker.relativeBearing(from: position, headingDegrees: heading, to: target)

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

    private func announceTurns(tracker: RouteTracker, along: Double, remaining: Double) {
        guard let turn = tracker.nextTurn(after: along) else {
            instruction = "\(Int(remaining.rounded())) meters to \(route?.to.name ?? "your destination")"
            return
        }
        let toTurn = turn.distanceAlong - along
        if toTurn <= 1.2, !announcedNow.contains(turn.vertex) {
            announcedNow.insert(turn.vertex)
            announcedSoon.insert(turn.vertex)
            let then = Int(turn.nextStretchMeters.rounded())
            say("\(turn.spokenTurn.capitalizedFirst) now, then walk \(then) meters.")
            buzz(turn.degrees > 0 ? 2 : 3)
        } else if toTurn <= 4, !announcedSoon.contains(turn.vertex) {
            announcedSoon.insert(turn.vertex)
            say("In \(max(1, Int(toTurn.rounded()))) meters, \(turn.spokenTurn).")
        }
        instruction = toTurn > 1.2
            ? "In \(max(1, Int(toTurn.rounded()))) m, \(turn.spokenTurn)"
            : "\(turn.spokenTurn.capitalizedFirst)"
    }

    private func handleOffRoute(_ off: Double, time: TimeInterval) {
        if off > 3 {
            if offRouteSince == nil { offRouteSince = time }
            if !isOffRoute, let since = offRouteSince, time - since > 2 {
                isOffRoute = true
                say("You're off the route. Turn until the phone vibrates, then walk.")
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
        guard phase != .arrived else { return }
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
        // Held upright, the camera looks along -z. Held flat, use the top edge of the phone,
        // which is ARKit's -x in portrait.
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
