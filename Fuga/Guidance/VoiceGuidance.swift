import AVFoundation
import Combine
import Foundation

/// Plays ElevenLabs clips generated before shipping; never needs network or an API key.
@MainActor
final class VoiceGuidance: ObservableObject {
    @Published private(set) var isEnabled = true
    @Published private(set) var status = "Juno voice on"
    private var player: AVAudioPlayer?
    private var scheduler = VoiceCueScheduler()
    var isSpeaking: Bool { player?.isPlaying == true }
    private var priorityPlayback = false

    /// Route events preempt directional reminders; both use the same Juno player.
    func announce(_ cue: VoiceCue) {
        guard isEnabled else { return }
        priorityPlayback = true
        speak(cue)
    }

    func testVoice() {
        setEnabled(true)
        announce(.test)
    }

    func setEnabled(_ enabled: Bool) {
        stop()
        isEnabled = enabled
        status = enabled ? "Juno voice on" : "Voice off"
    }

    func stop() {
        silence()
        // The navigator's spoken turns share the audio session, so it isn't deactivated here.
    }

    /// Stops any cue that is playing and forgets the last one, without touching the audio session.
    func silence() {
        if player != nil { player?.stop(); player = nil }
        scheduler = VoiceCueScheduler()
        priorityPlayback = false
    }

    func update(bearing: Double, distance: Double) {
        guard isEnabled else { return }
        if priorityPlayback && isSpeaking { return }
        priorityPlayback = false
        guard let cue = VoiceCue.resolve(bearing: bearing, distance: distance) else {
            stop()
            return
        }
        guard let next = scheduler.update(cue, now: ProcessInfo.processInfo.systemUptime) else { return }
        speak(next)
    }

    private func speak(_ cue: VoiceCue) {
        player?.stop()
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
                status = "Juno · ElevenLabs"
                return
            }
        }
        status = "Juno audio unavailable for \(cue.rawValue). Rebuild the app with its voice clips."
    }
}
