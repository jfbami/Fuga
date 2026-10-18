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
    /// Direction updates wait until a navigator corner clip has finished.
    private var turnClipUntil: TimeInterval = 0

    func setEnabled(_ enabled: Bool) {
        stop()
        isEnabled = enabled
        status = enabled ? "Voice on" : "Voice off"
    }

    func stop() {
        silence()
        // The navigator's spoken turns share the audio session, so it isn't deactivated here.
    }

    /// Stops any cue that is playing and forgets the last one, without touching the audio session.
    func silence() {
        if player != nil { player?.stop(); player = nil }
        if synthesizer.isSpeaking { synthesizer.stopSpeaking(at: .immediate) }
        scheduler = VoiceCueScheduler()
        turnClipUntil = 0
    }

    func update(bearing: Double, distance: Double) {
        guard isEnabled else { return }
        guard ProcessInfo.processInfo.systemUptime >= turnClipUntil else { return }
        guard let cue = VoiceCue.resolve(bearing: bearing, distance: distance) else {
            stop()
            return
        }
        guard let next = scheduler.update(cue, now: ProcessInfo.processInfo.systemUptime) else { return }
        speak(next)
    }

    /// Plays one cue right away, even when cues are turned off (used by the feedback test).
    func preview(_ cue: VoiceCue) { speak(cue) }

    /// Plays the navigator's corner clip; the 4-per-second direction updates don't cut it off.
    func playTurn(_ cue: VoiceCue) {
        speak(cue)
        turnClipUntil = ProcessInfo.processInfo.systemUptime + (player?.duration ?? 2)
    }

    private func speak(_ cue: VoiceCue) {
        player?.stop()
        synthesizer.stopSpeaking(at: .immediate)
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playback, mode: .spokenAudio, options: [.duckOthers])
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
