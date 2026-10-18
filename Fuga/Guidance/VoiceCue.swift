import Foundation

/// Stable, finite vocabulary so every instruction can be bundled for offline use.
enum VoiceCue: String, CaseIterable {
    case ahead, left, right, behind, arrived
    case starting, leftSoon, rightSoon, offRoute, backOnRoute, repinned, test

    var text: String {
        switch self {
        case .ahead: return "Continue straight ahead."
        case .left: return "Turn to your left."
        case .right: return "Turn to your right."
        case .behind: return "Turn around."
        case .arrived: return "You've reached your destination."
        case .starting: return "Your route is ready. Turn to follow the arrow, then continue ahead."
        case .leftSoon: return "Prepare to turn left."
        case .rightSoon: return "Prepare to turn right."
        case .offRoute: return "You're off the route. Stop and check your location before continuing."
        case .backOnRoute: return "You're back on the route."
        case .repinned: return "Your starting position has been updated."
        case .test: return "Hi, I'm Juno. I'll guide you with spoken directions. Vibration means you're pointing away from the route."
        }
    }

    static func resolve(bearing: Double, distance: Double) -> VoiceCue? {
        guard bearing.isFinite, distance.isFinite, distance >= 0 else { return nil }
        if distance < 1.5 { return .arrived }
        var angle = bearing.truncatingRemainder(dividingBy: 360)
        if angle > 180 { angle -= 360 }
        if angle <= -180 { angle += 360 }
        if abs(angle) <= 20 { return .ahead }
        if abs(angle) >= 135 { return .behind }
        return angle > 0 ? .right : .left
    }
}

/// Debounce compass noise, limit interruptions, and periodically repeat guidance.
struct VoiceCueScheduler {
    private var candidate: VoiceCue?
    private var candidateSince: TimeInterval = 0
    private var lastCue: VoiceCue?
    private var lastSpoken: TimeInterval = -.infinity

    mutating func update(_ cue: VoiceCue?, now: TimeInterval) -> VoiceCue? {
        guard let cue else {
            self = VoiceCueScheduler()
            return nil
        }
        if candidate != cue {
            candidate = cue
            candidateSince = now
        }
        let arrived = cue == .arrived && lastCue != .arrived
        let stable = now - candidateSince >= 0.75
        let changed = cue != lastCue && now - lastSpoken >= 3
        let repeatDue = cue != .arrived && now - lastSpoken >= 12
        guard arrived || (stable && (changed || repeatDue)) else { return nil }
        lastCue = cue
        lastSpoken = now
        return cue
    }
}
