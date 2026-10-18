import AVFoundation
import Combine
import Speech

/// Destination input only. It never infers the starting location or starts guidance.
@MainActor
final class DestinationVoice: ObservableObject {
    @Published private(set) var transcript = ""
    @Published private(set) var listening = false
    @Published private(set) var message: String?
    private let audio = AVAudioEngine()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var recognition: SFSpeechRecognitionTask?
    private var tapInstalled = false
    private var starting = false
    private var generation = UUID()

    func start() async {
        guard !starting && !listening else { return }
        starting = true
        let token = generation
        defer { starting = false }
        let speechAllowed = await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { continuation.resume(returning: $0 == .authorized) }
        }
        let microphoneAllowed = await withCheckedContinuation { continuation in
            AVAudioSession.sharedInstance().requestRecordPermission { continuation.resume(returning: $0) }
        }
        guard generation == token else { return }
        guard speechAllowed && microphoneAllowed else {
            message = "Microphone and speech access are needed for voice input. You can also type the room."
            return
        }
        guard let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US")),
              recognizer.isAvailable, recognizer.supportsOnDeviceRecognition else {
            message = "On-device voice recognition is unavailable. Type the room for this test."
            return
        }
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.record, mode: .measurement, options: [.duckOthers])
            try session.setActive(true)
            let bufferRequest = SFSpeechAudioBufferRecognitionRequest()
            bufferRequest.shouldReportPartialResults = true
            bufferRequest.requiresOnDeviceRecognition = true
            bufferRequest.contextualStrings = ["Take me to room 440", "Room 430", "Room 416", "Room 420"]
            request = bufferRequest
            let input = audio.inputNode
            let format = input.outputFormat(forBus: 0)
            guard format.sampleRate > 0, format.channelCount > 0 else {
                throw QuickLookError.message("The microphone is unavailable.")
            }
            input.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, _ in
                bufferRequest.append(buffer)
            }
            tapInstalled = true; transcript = ""; message = nil; listening = true
            recognition = recognizer.recognitionTask(with: bufferRequest) { [weak self] result, error in
                DispatchQueue.main.async {
                    guard let self, self.generation == token else { return }
                    if let result { self.transcript = result.bestTranscription.formattedString }
                    if error != nil || result?.isFinal == true {
                        self.stop()
                        if let error { self.message = error.localizedDescription }
                    }
                }
            }
            audio.prepare(); try audio.start()
        } catch { stop(); message = error.localizedDescription }
    }

    func stop() {
        generation = UUID()
        audio.stop()
        if tapInstalled { audio.inputNode.removeTap(onBus: 0); tapInstalled = false }
        request?.endAudio(); recognition?.cancel(); recognition = nil; request = nil; listening = false
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .spokenAudio, options: [.duckOthers])
    }

    static func room(in text: String) -> String? {
        let normalized = text.lowercased()
        if let range = normalized.range(of: #"\b[234][0-9]{2}[a-z]?\b"#, options: .regularExpression) {
            return normalized[range].uppercased()
        }
        // Common speech renderings. The result is a requested room, not proof it exists.
        let words = normalized.components(separatedBy: CharacterSet.letters.inverted).filter { !$0.isEmpty }
        let digits = ["zero":"0", "one":"1", "two":"2", "three":"3", "four":"4", "five":"5",
                      "six":"6", "seven":"7", "eight":"8", "nine":"9"]
        for i in words.indices {
            if i + 2 < words.count, let a = digits[words[i]], let b = digits[words[i+1]], let c = digits[words[i+2]],
               ["2", "3", "4"].contains(a) { return a + b + c }
            if i + 1 < words.count, let a = digits[words[i]], ["2", "3", "4"].contains(a) {
                let tens = ["ten":"10", "twenty":"20", "thirty":"30", "forty":"40", "fifty":"50", "sixty":"60", "seventy":"70", "eighty":"80", "ninety":"90"]
                if let b = tens[words[i+1]] { return a + b }
            }
        }
        return nil
    }
}
