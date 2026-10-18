import AVFoundation
import Combine
import CoreHaptics
import UIKit

/// Direct playback with visible hardware/error diagnostics for on-phone testing.
@MainActor
final class OffCourseHapticPlayer: ObservableObject {
    @Published private(set) var status = "Vibration ready"
    private var engine: CHHapticEngine?
    private var player: CHHapticPatternPlayer?

    func play(_ strength: OffCourseHaptics.Strength) {
        guard UIApplication.shared.applicationState == .active else { return }
        guard CHHapticEngine.capabilitiesForHardware().supportsHaptics else {
            status = "Vibration unavailable on this device (use a physical iPhone)"
            return
        }
        do {
            // Microphone-based destination entry can otherwise suppress haptics.
            try AVAudioSession.sharedInstance().setAllowHapticsAndSystemSoundsDuringRecording(true)
            if engine == nil {
                let created = try CHHapticEngine()
                created.playsHapticsOnly = true
                created.isAutoShutdownEnabled = true
                created.resetHandler = { [weak self] in
                    Task { @MainActor in self?.engine = nil; self?.player = nil }
                }
                engine = created
            }
            guard let engine else { return }
            try engine.start()
            try player?.stop(atTime: CHHapticTimeImmediate)
            let strong = strength == .strong
            let event = CHHapticEvent(eventType: .hapticContinuous,
                parameters: [
                    .init(parameterID: .hapticIntensity, value: strong ? 1 : 0.35),
                    .init(parameterID: .hapticSharpness, value: strong ? 0.8 : 0.25)
                ], relativeTime: 0, duration: strong ? 0.3 : 0.08)
            let pattern = try CHHapticPattern(events: [event], parameters: [])
            let next = try engine.makePlayer(with: pattern)
            player = next
            try next.start(atTime: CHHapticTimeImmediate)
            status = strong ? "Strong vibration sent" : "Subtle vibration sent"
        } catch {
            engine = nil
            player = nil
            let fallback = UIImpactFeedbackGenerator(style: strength == .strong ? .heavy : .light)
            fallback.prepare()
            fallback.impactOccurred(intensity: strength == .strong ? 1 : 0.4)
            status = "Basic vibration fallback: \(error.localizedDescription)"
        }
    }

    func stop() {
        try? player?.stop(atTime: CHHapticTimeImmediate)
        player = nil
        engine?.stop()
    }
}
