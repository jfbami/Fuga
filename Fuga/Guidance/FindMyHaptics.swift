import CoreHaptics
import UIKit

/// Vibration that behaves like Apple Find My's precision finding:
///
/// - Facing the wrong way: no vibration.
/// - Turn to face the way the arrow points: one firm "snap" as it turns green.
/// - While you keep facing the right way: steady taps that speed up and get stronger
///   as you get closer (about one a second when far, a fast flutter in the last few meters).
/// - Arrival: a short rising "found it" burst.
///
/// The arrow follows the route, so at a corner it swings, the taps stop, and they come
/// back (with a snap) once you've turned to face the new hallway.
final class FindMyHaptics {
    private var engine: CHHapticEngine?
    private let fallback = UIImpactFeedbackGenerator(style: .heavy)
    private var timer: Timer?

    private var aligned = false
    private var distance: Double = .infinity
    private var lastTap: TimeInterval = 0
    private var running = false
    /// What the vibration hardware is doing, for the feedback test.
    private(set) var status = "Ready"

    init() {
        guard CHHapticEngine.capabilitiesForHardware().supportsHaptics else {
            status = "This iPhone reports no Core Haptics support (using basic taps)"
            return
        }
        do { engine = try CHHapticEngine() } catch { status = "Haptic engine unavailable: \(error.localizedDescription)" }
        engine?.isAutoShutdownEnabled = false
        engine?.playsHapticsOnly = true
        engine?.resetHandler = { [weak self] in try? self?.engine?.start() }
        engine?.stoppedHandler = { _ in }
    }

    func start() {
        guard !running else { return }
        running = true
        do { try engine?.start() } catch { status = "Haptic engine didn't start: \(error.localizedDescription)" }
        fallback.prepare()
        lastTap = 0
        timer = Timer.scheduledTimer(withTimeInterval: 0.03, repeats: true) { [weak self] _ in self?.tick() }
    }

    func stop() {
        running = false
        timer?.invalidate()
        timer = nil
        aligned = false
        engine?.stop()
    }

    /// Call on every guidance update.
    func update(aligned nowAligned: Bool, distanceMeters: Double) {
        distance = distanceMeters
        if nowAligned && !aligned {
            play(intensity: 1.0, sharpness: 0.9)   // the snap when the arrow turns green
            lastTap = CACurrentMediaTime()
        }
        aligned = nowAligned
    }

    /// Short rising triple tap, like Find My when you reach the item.
    func arrived() {
        aligned = false
        let events = [0.0, 0.12, 0.24].enumerated().map { i, t in
            CHHapticEvent(eventType: .hapticTransient,
                          parameters: [.init(parameterID: .hapticIntensity, value: Float(0.6 + 0.2 * Double(i))),
                                       .init(parameterID: .hapticSharpness, value: 0.6)],
                          relativeTime: t)
        } + [CHHapticEvent(eventType: .hapticContinuous,
                           parameters: [.init(parameterID: .hapticIntensity, value: 1.0),
                                        .init(parameterID: .hapticSharpness, value: 0.3)],
                           relativeTime: 0.36, duration: 0.25)]
        if !playPattern(events) {
            UINotificationFeedbackGenerator().notificationOccurred(.success)
        }
    }

    // MARK: Private

    private func tick() {
        guard running, aligned, distance.isFinite else { return }
        let now = CACurrentMediaTime()
        if now - lastTap >= Self.interval(for: distance) {
            lastTap = now
            play(intensity: Float(Self.intensity(for: distance)), sharpness: 0.5)
        }
    }

    /// Seconds between taps: ~1.1 s at 25 m or more, down to 0.12 s at 1.5 m.
    static func interval(for meters: Double) -> Double {
        let t = min(1, max(0, (meters - 1.5) / (25 - 1.5)))
        return 0.12 + (1.1 - 0.12) * pow(t, 0.8)
    }

    /// Taps get stronger as you get closer.
    static func intensity(for meters: Double) -> Double {
        let t = min(1, max(0, (meters - 1.5) / (25 - 1.5)))
        return 1.0 - 0.55 * t
    }

    private func play(intensity: Float, sharpness: Float) {
        let event = CHHapticEvent(eventType: .hapticTransient,
                                  parameters: [.init(parameterID: .hapticIntensity, value: intensity),
                                               .init(parameterID: .hapticSharpness, value: sharpness)],
                                  relativeTime: 0)
        if !playPattern([event]) {
            fallback.impactOccurred(intensity: CGFloat(intensity))
        }
    }

    @discardableResult
    private func playPattern(_ events: [CHHapticEvent]) -> Bool {
        guard let engine,
              let pattern = try? CHHapticPattern(events: events, parameters: []),
              let player = try? engine.makePlayer(with: pattern) else { return false }
        do {
            try player.start(atTime: CHHapticTimeImmediate)
            return true
        } catch {
            try? engine.start()
            return (try? player.start(atTime: CHHapticTimeImmediate)) != nil
        }
    }
}
