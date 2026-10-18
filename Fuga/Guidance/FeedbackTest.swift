import AVFoundation
import Combine
import UIKit

/// "Test voice & vibration": plays every sound and vibration the guidance uses, without
/// starting navigation (walking guidance stays switched off until the map is verified).
@MainActor
final class FeedbackTest: ObservableObject {
    @Published private(set) var running = false
    @Published private(set) var step = ""

    private let voice: VoiceGuidance
    private let findMy = FindMyHaptics()
    private let speech = AVSpeechSynthesizer()
    private let light = UIImpactFeedbackGenerator(style: .light)
    private let heavy = UIImpactFeedbackGenerator(style: .heavy)
    private var task: Task<Void, Never>?

    init(voice: VoiceGuidance) { self.voice = voice }

    func toggle() { running ? stop() : start() }

    func stop() {
        task?.cancel(); task = nil
        findMy.stop(); voice.silence(); speech.stopSpeaking(at: .immediate)
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

    private func run() async throws {
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .spokenAudio, options: [.duckOthers])
        try? AVAudioSession.sharedInstance().setActive(true)

        step = "iPhone voice (used for turns with distances and room names)"
        speech.speak(AVSpeechUtterance(string: "In 4 meters, turn left."))
        try await pause(2.5)

        var voiceSource = ""
        for cue in [VoiceCue.ahead, .left, .right, .behind] {
            step = "ElevenLabs cue: \(cue.text)"
            voice.preview(cue)
            voiceSource = voice.status
            try await pause(2.2)
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
        speech.speak(AVSpeechUtterance(string: "430 Computer Classroom is on your right."))  // iPhone voice: room names
        try await pause(3)

        step = "Off-course: light pulses (facing 45° or more away)"
        light.prepare()
        for _ in 0..<3 { light.impactOccurred(intensity: 0.4); try await pause(1) }
        step = "Off-course: heavy pulses (facing 100° or more away)"
        heavy.prepare()
        for _ in 0..<4 { heavy.impactOccurred(intensity: 1); try await pause(0.75) }

        let clips = voiceSource == "ElevenLabs voice"
            ? "ElevenLabs clips played"
            : "ElevenLabs clips did NOT play (\(voiceSource))"
        step = "Done. \(clips). Vibration: \(findMy.status)."
        try await pause(0.1)
    }
}
