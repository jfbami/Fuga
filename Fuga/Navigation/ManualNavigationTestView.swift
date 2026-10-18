import SwiftUI

#if DEBUG
/// Explicit manual test path; never supplies a claimed automatic localization result.
struct ManualNavigationTestView: View {
    @ObservedObject var nav: RouteNavigator
    let onStart: (HallwayGraph.Node, HallwayGraph.Destination) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var landmarkID = ""
    @State private var destinationID = ""

    private var landmark: HallwayGraph.Node? { nav.graph.node(landmarkID) }
    private var destination: HallwayGraph.Destination? {
        nav.graph.destinations.first { $0.id == destinationID }
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text("Unverified map — testing only. This does not verify a safe evacuation route.")
                        .foregroundStyle(.orange)
                    Text("Stand at a known landmark, face its door, and select your destination.")
                }
                Section("Starting point") {
                    Picker("Landmark", selection: $landmarkID) {
                        Text("Choose a landmark").tag("")
                        ForEach(nav.graph.landmarks, id: \.id) { node in
                            Text(node.landmark ?? node.id).tag(node.id)
                        }
                    }
                }
                Section("Destination") {
                    Picker("Room", selection: $destinationID) {
                        Text("Choose a destination").tag("")
                        ForEach(nav.graph.destinations.filter { !$0.doors.contains(landmarkID) }, id: \.id) { item in
                            Text(item.title).tag(item.id)
                        }
                    }
                }
                Section {
                    if let message = nav.trackingMessage { Text(message) }
                    Button(nav.trackingReady ? "Start manual test" : "Waiting for camera tracking…") {
                        guard let landmark, let destination else { return }
                        onStart(landmark, destination)
                        if nav.phase == .navigating { dismiss() }
                    }
                    .disabled(landmark == nil || destination == nil || !nav.trackingReady)
                    if let error = nav.startError { Text(error).foregroundStyle(.orange) }
                }
            }
            .navigationTitle("Manual navigation test")
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } } }
            .onChange(of: landmarkID) { _, _ in destinationID = "" }
        }
    }
}
#endif
