import Foundation

/// Heading-based nudges, independent of whether spoken guidance is enabled.
struct OffCourseHaptics {
    enum Strength {
        case subtle, strong

        var interval: TimeInterval { self == .strong ? 0.75 : 2 }
    }

    private var candidate: Strength?
    private var candidateSince: TimeInterval = 0
    private var lastPulse: TimeInterval = -.infinity

    mutating func reset() {
        self = OffCourseHaptics()
    }

    /// Returns the strength of one pulse, or nil when no pulse is due.
    /// Call regularly using a monotonic clock and the next waypoint's bearing.
    mutating func update(bearing: Double, distance: Double, now: TimeInterval) -> Strength? {
        guard bearing.isFinite, distance.isFinite, distance >= 1.5, now.isFinite else {
            reset()
            return nil
        }
        var angle = bearing.truncatingRemainder(dividingBy: 360)
        if angle > 180 { angle -= 360 }
        if angle <= -180 { angle += 360 }
        let deviation = abs(angle)

        // Separate entry/exit thresholds prevent chatter around either boundary.
        let strength: Strength?
        if deviation >= 100 || (candidate == .strong && deviation > 80) {
            strength = .strong
        } else if deviation >= 45 || (candidate != nil && deviation > 30) {
            strength = .subtle
        } else {
            strength = nil
        }
        guard let strength else {
            reset()
            return nil
        }
        if candidate != strength {
            candidate = strength
            candidateSince = now
        }
        // Require a stable heading before starting or changing pulse strength.
        guard now - candidateSince >= 0.75,
              now - lastPulse >= strength.interval else { return nil }
        lastPulse = now
        return strength
    }
}
