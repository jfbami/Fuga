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

/// Find My-style feedback while you face the way the arrow points (the green arrow):
/// one firm snap when you line up, then taps that come faster and stronger as you get
/// closer. Silent as soon as you turn away; the off-course nudges cover that range.
/// Plain logic like OffCourseHaptics, so tests/main.swift can check it without an iPhone.
/// (This replaces FindMyHaptics, which was disconnected from navigation in 5ceb948.)
struct AlignedHaptics {
    enum Pulse: Equatable {
        case snap
        case tap(intensity: Double)
    }

    private var aligned = false
    private var lastPulse: TimeInterval = -.infinity

    mutating func reset() {
        self = AlignedHaptics()
    }

    /// Returns the pulse to play now, or nil. Pass the navigator's `isAligned`
    /// (it already has hysteresis), the remaining distance and a monotonic clock.
    mutating func update(aligned nowAligned: Bool, distance: Double, now: TimeInterval) -> Pulse? {
        guard nowAligned, distance.isFinite, distance >= 0, now.isFinite else {
            reset()
            return nil
        }
        if !aligned {
            aligned = true
            lastPulse = now
            return .snap
        }
        guard now - lastPulse >= Self.interval(for: distance) else { return nil }
        lastPulse = now
        return .tap(intensity: Self.intensity(for: distance))
    }

    /// Seconds between taps: ~1.1 s at 25 m or more, down to 0.12 s at 1.5 m.
    /// ContentView samples every 0.25 s, so in practice the fastest rate is 4 taps a second.
    static func interval(for meters: Double) -> Double {
        let t = min(1, max(0, (meters - 1.5) / (25 - 1.5)))
        return 0.12 + (1.1 - 0.12) * pow(t, 0.8)
    }

    /// Taps get stronger as you get closer (0.45 far away, 1.0 at the door).
    static func intensity(for meters: Double) -> Double {
        let t = min(1, max(0, (meters - 1.5) / (25 - 1.5)))
        return 1.0 - 0.55 * t
    }
}
