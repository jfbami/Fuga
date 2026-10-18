import AVFoundation
import Combine
import UIKit

/// "Test voice & vibration": plays every Juno clip and vibration the guidance uses, without
/// starting navigation (walking guidance stays switched off until the map is verified).
@MainActor
final class FeedbackTest: ObservableObject {
    @Published private(set) var running = false
    @Published private(set) var step = ""

    private let voice: VoiceGuidance
    private let findMy = FindMyHaptics()
    private let offCourse = OffCourseHapticPlayer()
    private var task: Task<Void, Never>?

    init(voice: VoiceGuidance) { self.voice = voice }

    func toggle() { running ? stop() : start() }

    func stop() {
        task?.cancel(); task = nil
        findMy.stop(); offCourse.stop(); voice.silence()
        running = false; step = ""
    }

    private func start() {
        running = true
        task = Task { [weak self] in
            guard let self else { return }
            do {
                try await self.run()
            } catch {}
            self.findMy.stop()
            self.running = false
        }
    }

    private func pause(_ seconds: Double) async throws {
        try await Task.sleep(for: .milliseconds(Int(seconds * 1000)))
    }

    /// Waits for the current clip to finish (at most 7 s), plus a short gap.
    private func waitForVoice() async throws {
        try await pause(0.3)
        var waited = 0.3
        while voice.isSpeaking && waited < 7 { try await pause(0.1); waited += 0.1 }
        try await pause(0.4)
    }

    private func run() async throws {
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .spokenAudio, options: [.duckOthers])
        try? AVAudioSession.sharedInstance().setActive(true)

        var voiceSource = ""
        for cue in [VoiceCue.starting, .leftSoon, .left, .right, .behind, .ahead] {
            step = "Juno: \(cue.text)"
            voice.preview(cue)
            voiceSource = voice.status
            try await waitForVoice()
        }

        step = "Find My vibration: snap when you face the right way, then taps 20 m away"
        findMy.start()
        findMy.update(aligned: true, distanceMeters: 20)
        try await pause(3)
        step = "Taps speed up as you get closer"
        for meters in stride(from: 20.0, through: 1.5, by: -0.5) {
            findMy.update(aligned: true, distanceMeters: meters)
            try await pause(0.12)
        }
        try await pause(1.5)
        findMy.update(aligned: false, distanceMeters: 1.5)

        step = "Arrival burst"
        findMy.stop()
        findMy.arrived()
        voice.preview(.arrived)
        try await waitForVoice()

        step = "Off-course: light pulses (facing 45° or more away)"
        for _ in 0..<3 { offCourse.play(.subtle); try await pause(1) }
        step = "Off-course: strong pulses (facing 100° or more away)"
        for _ in 0..<4 { offCourse.play(.strong); try await pause(0.75) }

        let clips = voiceSource.hasPrefix("Juno · ElevenLabs")
            ? "Juno clips played"
            : "Juno clips did NOT play (\(voiceSource))"
        step = "Done. \(clips). Find My taps: \(findMy.status). Off-course: \(offCourse.status)."
        try await pause(0.1)
    }
}
