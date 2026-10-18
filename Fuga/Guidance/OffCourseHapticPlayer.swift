import AVFoundation
import Combine
import CoreHaptics
import UIKit

/// The one vibration player for the app: navigation and the feedback test both use it.
///
/// Why this was rewritten (vibration "sent" but not felt on the phone):
/// - The old status said "sent" as soon as iOS accepted the request. That is not proof
///   the motor moved; e.g. Settings › Accessibility › Touch › Vibration off silences
///   everything with no error. The status now says what is actually known.
/// - The old subtle pulse was a 0.08 s, 35%-strength, very soft buzz: easy to miss in a
///   hand while walking. Patterns are now built from sharp "transient" taps.
/// - Auto-shutdown let iOS power the engine down between nudges; now one engine stays
///   on until `stop()`, and if iOS stops it anyway the reason is shown in `status`.
/// - `playSystemCheck()` uses plain UIKit haptics, bypassing Core Haptics, so a tester
///   can tell whether Core Haptics or the phone's settings are the problem.
@MainActor
final class OffCourseHapticPlayer: ObservableObject {
    @Published private(set) var status = "Vibration ready"
    private var engine: CHHapticEngine?
    private var player: CHHapticPatternPlayer?
    private var engineRunning = false

    // MARK: Patterns

    /// Off course: one light tap (subtle) or a double heavy knock plus a short rumble (strong).
    func play(_ strength: OffCourseHaptics.Strength) {
        switch strength {
        case .subtle:
            fire([Self.tap(at: 0, intensity: 0.55, sharpness: 0.4)],
                 label: "Subtle nudge", fallback: .light, fallbackIntensity: 0.6)
        case .strong:
            fire([Self.tap(at: 0, intensity: 1, sharpness: 0.9),
                  Self.tap(at: 0.12, intensity: 1, sharpness: 0.9),
                  Self.buzz(at: 0.24, duration: 0.2, intensity: 0.9, sharpness: 0.5)],
                 label: "Strong nudge", fallback: .heavy, fallbackIntensity: 1)
        }
    }

    /// Facing the right way: a crisp snap when the arrow turns green, then softer taps.
    func play(_ pulse: AlignedHaptics.Pulse) {
        switch pulse {
        case .snap:
            fire([Self.tap(at: 0, intensity: 1, sharpness: 1)],
                 label: "On-target snap", fallback: .rigid, fallbackIntensity: 1)
        case .tap(let intensity):
            fire([Self.tap(at: 0, intensity: Float(intensity), sharpness: 0.5)],
                 label: "On-target tap", fallback: .medium, fallbackIntensity: CGFloat(intensity))
        }
    }

    /// Short rising triple tap and a soft swell, like Find My when you reach the item.
    func playArrival() {
        var events = [0.0, 0.12, 0.24].enumerated().map { i, t in
            Self.tap(at: t, intensity: 0.6 + 0.2 * Float(i), sharpness: 0.6)
        }
        events.append(Self.buzz(at: 0.36, duration: 0.25, intensity: 1, sharpness: 0.3))
        fire(events, label: "Arrival", fallback: .heavy, fallbackIntensity: 1)
    }

    /// A plain UIKit tap that skips Core Haptics entirely (diagnostic for the feedback test).
    func playSystemCheck() {
        playBasic(.heavy, 1)
        status = "Basic iPhone tap requested (UIKit, no Core Haptics)"
    }

    func stop() {
        try? player?.stop(atTime: CHHapticTimeImmediate)
        player = nil
        // ContentView calls this every 0.25 s while guidance is paused; skip if already off.
        guard engineRunning else { return }
        engine?.stop()
        engineRunning = false
    }

    // MARK: Private

    private func fire(_ events: [CHHapticEvent], label: String,
                      fallback: UIImpactFeedbackGenerator.FeedbackStyle, fallbackIntensity: CGFloat) {
        // iOS never plays haptics for an app that isn't in the foreground.
        guard UIApplication.shared.applicationState == .active else {
            status = "\(label) skipped: app is not in the foreground"
            return
        }
        guard CHHapticEngine.capabilitiesForHardware().supportsHaptics else {
            playBasic(fallback, fallbackIntensity)
            status = "\(label): no Core Haptics on this device (Simulator?); tried a basic tap"
            return
        }
        do {
            // Microphone-based destination entry can otherwise suppress haptics.
            try AVAudioSession.sharedInstance().setAllowHapticsAndSystemSoundsDuringRecording(true)
            let engine = try readyEngine()
            try? player?.stop(atTime: CHHapticTimeImmediate)   // a stale player must not block the new one
            let next = try engine.makePlayer(with: CHHapticPattern(events: events, parameters: []))
            player = next
            try next.start(atTime: CHHapticTimeImmediate)
            // iOS accepted it. Still not proof the motor moved, so don't claim more than that.
            status = "\(label) accepted by Core Haptics"
        } catch {
            // Throw the engine away so the next pulse builds a fresh one, and tap anyway.
            engine = nil
            player = nil
            engineRunning = false
            playBasic(fallback, fallbackIntensity)
            status = "\(label): Core Haptics failed (\(error.localizedDescription)); used a basic tap"
        }
    }

    /// Creates the engine once and starts it only when it isn't already running.
    private func readyEngine() throws -> CHHapticEngine {
        let engine = try self.engine ?? makeEngine()
        self.engine = engine
        if !engineRunning {
            try engine.start()
            engineRunning = true
        }
        return engine
    }

    private func makeEngine() throws -> CHHapticEngine {
        let created = try CHHapticEngine()
        created.playsHapticsOnly = true
        // Stay on during guidance (stop() turns it off) so pulses aren't lost to a cold start.
        created.isAutoShutdownEnabled = false
        created.stoppedHandler = { [weak self] reason in
            // Called when something outside the app stops the engine (audio interruption, etc.).
            Task { @MainActor in
                self?.engineRunning = false
                self?.status = "iOS stopped the vibration engine (\(Self.describe(reason)))"
            }
        }
        created.resetHandler = { [weak self] in
            // The haptic server restarted; the old engine and players are no longer valid.
            Task { @MainActor in self?.engine = nil; self?.player = nil; self?.engineRunning = false }
        }
        return created
    }

    private func playBasic(_ style: UIImpactFeedbackGenerator.FeedbackStyle, _ intensity: CGFloat) {
        let generator = UIImpactFeedbackGenerator(style: style)
        generator.prepare()
        generator.impactOccurred(intensity: intensity)
    }

    private static func tap(at time: TimeInterval, intensity: Float, sharpness: Float) -> CHHapticEvent {
        CHHapticEvent(eventType: .hapticTransient,
                      parameters: [.init(parameterID: .hapticIntensity, value: intensity),
                                   .init(parameterID: .hapticSharpness, value: sharpness)],
                      relativeTime: time)
    }

    private static func buzz(at time: TimeInterval, duration: TimeInterval,
                             intensity: Float, sharpness: Float) -> CHHapticEvent {
        CHHapticEvent(eventType: .hapticContinuous,
                      parameters: [.init(parameterID: .hapticIntensity, value: intensity),
                                   .init(parameterID: .hapticSharpness, value: sharpness)],
                      relativeTime: time, duration: duration)
    }

    private static func describe(_ reason: CHHapticEngine.StoppedReason) -> String {
        switch reason {
        case .audioSessionInterrupt: return "audio session interrupted"
        case .applicationSuspended: return "app suspended"
        case .idleTimeout: return "idle timeout"
        case .systemError: return "system error"
        case .notifyWhenFinished: return "finished"
        case .engineDestroyed: return "engine destroyed"
        case .gameControllerDisconnect: return "controller disconnected"
        @unknown default: return "reason \(reason.rawValue)"
        }
    }
}
