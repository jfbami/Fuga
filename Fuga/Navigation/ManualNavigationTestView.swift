import SwiftUI

#if DEBUG
/// Explicit manual test path; never supplies a claimed automatic localization result.
struct ManualNavigationTestView: View {
    @ObservedObject var nav: RouteNavigator
    let onStart: (HallwayGraph.Node, HallwayGraph.Destination, Double) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var landmarkID = ""
    @State private var destinationID = ""
    @State private var doorDistanceText = ""

    private var doorDistance: Double? {
        guard let value = Double(doorDistanceText.replacingOccurrences(of: ",", with: ".")),
              value.isFinite, (0.2...3).contains(value) else { return nil }
        return value
    }

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
                    Text("Stand directly in front of the chosen door, facing it with the phone upright. Enter the measured distance from the phone to the door; do not stand at an arbitrary point in the hallway.")
                }
                Section("Starting point") {
                    Picker("Landmark", selection: $landmarkID) {
                        Text("Choose a landmark").tag("")
                        ForEach(nav.graph.landmarks, id: \.id) { node in
                            Text(node.landmark ?? node.id).tag(node.id)
                        }
                    }
                }
                Section("Doorway calibration") {
                    TextField("Phone-to-door distance in meters (0.2–3)", text: $doorDistanceText)
                        .keyboardType(.decimalPad)
                    Text("Measure this distance. The corridor centerline is not your starting position.")
                        .font(.footnote)
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
                        guard let landmark, let destination, let doorDistance else { return }
                        onStart(landmark, destination, doorDistance)
                        if nav.phase == .navigating { dismiss() }
                    }
                    .disabled(landmark == nil || destination == nil || doorDistance == nil || !nav.trackingReady)
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
