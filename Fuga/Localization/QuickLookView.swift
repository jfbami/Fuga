import ARKit
import SwiftUI

struct QuickLookView: View {
    let session: ARSession
    var showsCloseButton = true
    var onCameraWork: () -> Void = {}
    var feedbackAction: (() -> Void)? = nil
    var feedbackRunning = false
    var feedbackStep = ""
    var manualTestAction: (() -> Void)? = nil
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var model = QuickLookModel()
    @StateObject private var voice = DestinationVoice()
    @State private var floor = 4
    @State private var destination = ""
    @AppStorage("mghDevelopmentServer") private var endpoint = ""

    private func look() {
        model.autoLocate(session: session, floor: floor, destination: destination, endpoint: endpoint)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    ARCameraView(session: session)
                        .frame(height: 230).clipShape(RoundedRectangle(cornerRadius: 12))
                        .accessibilityLabel("Live hallway camera")
                }
                Section {
                    Text("Just hold the phone up toward the hallway. It finds where you are on its own.")
                    Picker("I'm on floor", selection: $floor) {
                        ForEach([2, 3, 4], id: \.self) { Text("Floor \($0)").tag($0) }
                    }.pickerStyle(.segmented)
                    TextField("Destination room (optional), e.g. 440", text: $destination)
                        .textInputAutocapitalization(.characters).autocorrectionDisabled()
                    Button {
                        onCameraWork()
                        if voice.listening { voice.stop() } else { Task { await voice.start() } }
                    } label: {
                        Label(voice.listening ? "Stop listening" : "Say your destination", systemImage: "mic.fill")
                    }
                    if !voice.transcript.isEmpty { Text("Heard: \(voice.transcript)") }
                    if let text = voice.message { Text(text).foregroundStyle(.secondary) }
                    if let room = DestinationVoice.room(in: destination) {
                        Text("Requested destination: room \(room)").font(.headline)
                    }
                }

                Section {
                    LabeledContent("Starting location", value: model.locationState.rawValue)
                    if model.busy { ProgressView() }
                    Text(model.message).accessibilityLabel(model.message)
                    if !model.busy && floor == 4 {
                        Button("Look again") { look() }
                    }
                }
                if let feedbackAction {
                    Section {
                        Button(action: feedbackAction) {
                            Label(feedbackRunning ? "Stop test" : "Test voice & vibration",
                                  systemImage: feedbackRunning ? "stop.fill" : "waveform")
                        }
                        .disabled(voice.listening)
                        if !feedbackStep.isEmpty { Text(feedbackStep) }
                        Text("Plays sample feedback. It does not mean your location has been found.")
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                }
                if let manualTestAction {
                    Section("Developer navigation test") {
                        Button("Manual navigation test") {
                            model.cancel()
                            voice.stop()
                            onCameraWork()
                            manualTestAction()
                        }
                        Text("Test a route from a manually chosen landmark. Map alignment and paths are not yet verified.")
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                }
                Section {
                    DisclosureGroup("Camera test settings & export") {
                        TextField("Server URL (optional for capture only)", text: $endpoint)
                            .keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
                            .disabled(model.busy)
                        if let url = model.exportURL {
                            ShareLink(item: url) { Label("Share camera test", systemImage: "square.and.arrow.up") }
                            Text("Includes camera images and movement data. Share it privately with the project.")
                        }
                        Text("Without a server this saves a test, not a location. Arrow and buzz guidance stay off until location, entrances and paths are verified.")
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                }
            }
            .navigationTitle("Find where I am")
            .toolbar {
                if showsCloseButton {
                    ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } }
                }
            }
            .onChange(of: voice.transcript) { _, text in
                if let room = DestinationVoice.room(in: text) { destination = room }
            }
            // Looking starts by itself; the floor is search context, the destination is independent.
            .onAppear { look() }
            .onChange(of: floor) { _, _ in look() }
            .onChange(of: scenePhase) { _, phase in
                if phase == .active { look() } else { model.cancel(); voice.stop() }
            }
            .onDisappear { model.cancel(); voice.stop() }
        }
    }
}
