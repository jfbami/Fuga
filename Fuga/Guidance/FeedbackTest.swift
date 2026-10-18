import Combine
import Foundation

/// Exercises the same Juno player and off-course haptics as navigation.
@MainActor
final class FeedbackTest: ObservableObject {
    @Published private(set) var running = false
    @Published private(set) var step = ""
    private let voice: VoiceGuidance
    private let haptics: OffCourseHapticPlayer
    private var task: Task<Void, Never>?
    private var generation = UUID()

    init(voice: VoiceGuidance, haptics: OffCourseHapticPlayer) {
        self.voice = voice
        self.haptics = haptics
    }

    func toggle() { running ? stop() : start() }

    func stop() {
        generation = UUID()
        task?.cancel()
        task = nil
        voice.stop()
        haptics.stop()
        running = false
        step = ""
    }

    private func start() {
        stop()
        running = true
        let token = generation
        task = Task { [weak self] in
            guard let self else { return }
            do {
                voice.setEnabled(true)
                for cue in [VoiceCue.test, .left, .right] {
                    step = "Juno: \(cue.text)"
                    voice.announce(cue)
                    guard voice.isSpeaking else { step = voice.status; running = false; return }
                    while voice.isSpeaking {
                        try await Task.sleep(for: .milliseconds(100))
                    }
                }
                // Off-course nudges, same timing as navigation.
                for strength in [OffCourseHaptics.Strength.subtle, .strong] {
                    for _ in 0..<3 {
                        haptics.play(strength)
                        step = haptics.status
                        try await Task.sleep(for: .milliseconds(Int(strength.interval * 1000)))
                    }
                }
                // Facing the right way: the snap, then taps speeding up as if walking closer.
                haptics.play(.snap)
                step = haptics.status
                try await Task.sleep(for: .milliseconds(800))
                for meters in [20.0, 10, 5, 2] {
                    for _ in 0..<3 {
                        haptics.play(.tap(intensity: AlignedHaptics.intensity(for: meters)))
                        step = "\(haptics.status) · as if \(Int(meters)) m away"
                        try await Task.sleep(for: .seconds(max(0.25, AlignedHaptics.interval(for: meters))))
                    }
                }
                haptics.playArrival()
                step = haptics.status
                try await Task.sleep(for: .milliseconds(1500))
                // Last: a plain UIKit tap that skips Core Haptics. Tells the tester where the problem is.
                haptics.playSystemCheck()
                try await Task.sleep(for: .milliseconds(500))
                step = "Test complete. \(voice.status). Felt only the last tap? Core Haptics is the problem. "
                    + "Felt nothing at all? Check Settings › Accessibility › Touch › Vibration "
                    + "and Settings › Sounds & Haptics."
            } catch {}
            guard generation == token else { return }
            haptics.stop()
            running = false
            task = nil
        }
    }
}
