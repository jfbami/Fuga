import ARKit
import SwiftUI

struct QuickLookView: View {
    let session: ARSession
    @Environment(\.dismiss) private var dismiss
    @StateObject private var model = QuickLookModel()
    @StateObject private var voice = DestinationVoice()
    @State private var floor = 4
    @State private var destination = ""
    @AppStorage("mghDevelopmentServer") private var endpoint = ""

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    ARCameraView(session: session)
                        .frame(height: 230).clipShape(RoundedRectangle(cornerRadius: 12))
                        .accessibilityLabel("Live hallway camera")
                }
                Section {
                    Text("Select your floor, say where you want to go, and give the camera a quick look at the hallway.")
                    Picker("I'm on floor", selection: $floor) {
                        ForEach([2, 3, 4], id: \.self) { Text("Floor \($0)").tag($0) }
                    }.pickerStyle(.segmented)
                    TextField("Destination room, e.g. 440", text: $destination)
                        .textInputAutocapitalization(.characters).autocorrectionDisabled()
                    Button {
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
                .disabled(model.busy)

                Section {
                    if floor != 4 {
                        Text("Floor \(floor) can be captured for testing. Automatic recognition is currently available for floor 4 only.")
                    }
                    Button("Find my starting location") {
                        voice.stop()
                        model.find(session: session, floor: floor, destination: destination, endpoint: endpoint)
                    }
                    .disabled(model.busy || DestinationVoice.room(in: destination) == nil)
                    if model.busy { ProgressView() }
                    Text(model.message).accessibilityLabel(model.message)
                    if let url = model.exportURL {
                        ShareLink(item: url) { Label("Share camera test", systemImage: "square.and.arrow.up") }
                        Text("Includes camera images and movement data. Share it with the project for analysis.")
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                }
                Section("Development test") {
                    TextField("Server URL (optional for capture only)", text: $endpoint)
                        .keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
                        .disabled(model.busy)
                    Text("Frames go to this server only when you tap Find. Recognition is still being tested. Arrow and buzz guidance stay off until location, entrances and paths are verified.")
                        .font(.footnote).foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Find my location")
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
            .onChange(of: voice.transcript) { _, text in
                if let room = DestinationVoice.room(in: text) { destination = room }
            }
            .onChange(of: floor) { _, _ in model.cancel() }
            .onChange(of: destination) { _, _ in if model.busy { model.cancel() } }
            .onDisappear { model.cancel(); voice.stop() }
        }
    }
}
