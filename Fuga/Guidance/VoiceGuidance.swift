import AVFoundation
import Combine
import Foundation

/// Plays ElevenLabs clips generated before shipping; never needs network or an API key.
@MainActor
final class VoiceGuidance: ObservableObject {
    @Published private(set) var isEnabled = false
    @Published private(set) var status = "Voice off"
    private let synthesizer = AVSpeechSynthesizer()
    private var player: AVAudioPlayer?
    private var scheduler = VoiceCueScheduler()

    func setEnabled(_ enabled: Bool) {
        stop()
        isEnabled = enabled
        status = enabled ? "Voice on" : "Voice off"
    }

    func stop() {
        player?.stop()
        player = nil
        synthesizer.stopSpeaking(at: .immediate)
        scheduler = VoiceCueScheduler()
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }

    func update(bearing: Double, distance: Double) {
        guard isEnabled else { return }
        guard let cue = VoiceCue.resolve(bearing: bearing, distance: distance) else {
            stop()
            return
        }
        guard let next = scheduler.update(cue, now: ProcessInfo.processInfo.systemUptime) else { return }
        speak(next)
    }

    private func speak(_ cue: VoiceCue) {
        player?.stop()
        synthesizer.stopSpeaking(at: .immediate)
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playback, mode: .spokenAudio, options: [.mixWithOthers])
            try session.setActive(true)
        } catch {
            status = "Audio unavailable — try enabling voice again"
            return
        }
        // Synced Xcode groups normally flatten resources; also support preserved folders.
        let name = "fuga_\(cue.rawValue)"
        let url = Bundle.main.url(forResource: name, withExtension: "mp3")
            ?? Bundle.main.url(forResource: name, withExtension: "mp3", subdirectory: "VoiceAudio")
        if let url, let audio = try? AVAudioPlayer(contentsOf: url) {
            player = audio
            if audio.play() {
                status = "ElevenLabs voice"
                return
            }
        }
        let utterance = AVSpeechUtterance(string: cue.text)
        utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
        utterance.rate = AVSpeechUtteranceDefaultSpeechRate
        synthesizer.speak(utterance)
        status = "Device voice — ElevenLabs clips not installed"
    }
}
