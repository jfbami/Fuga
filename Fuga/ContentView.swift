import SwiftUI

/// Screens over the live camera:
/// 1. Start: "Where are you?" (pick the room or landmark you're next to), "Where to?", Start.
/// 2. Guidance: Find My–style arrow, distance, next instruction, spoken turns and vibration.
///    "I'm at a landmark" re-pins your position if it drifts.
struct ContentView: View {
    @StateObject private var nav: RouteNavigator
    @State private var here: String?
    @State private var destination: HallwayGraph.Destination?
    @State private var showMap = true
    @State private var showRepin = false

    init() {
        guard let graph = HallwayGraph.load(resource: "mgh4_graph") else {
            fatalError("mgh4_graph.json is missing from the app bundle (Fuga/Maps).")
        }
        _nav = StateObject(wrappedValue: RouteNavigator(graph: graph))
    }

    private var hereNode: HallwayGraph.Node? { here.flatMap { nav.graph.node($0) } }

    var body: some View {
        ZStack {
            ARCameraView(session: nav.session)
                .ignoresSafeArea()
            LinearGradient(colors: [.black.opacity(0.6), .black.opacity(0.1), .black.opacity(0.65)],
                           startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea()
                .allowsHitTesting(false)

            switch nav.phase {
            case .idle: startScreen
            case .navigating, .arrived: guidanceScreen
            }
        }
        .onAppear { nav.runCamera() }
        .onDisappear { nav.pauseCamera() }
    }

    // MARK: Start

    private var startScreen: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text("\(nav.graph.building.uppercased()) · \(nav.graph.floorLabel.uppercased())")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.white.opacity(0.7))

                sectionTitle("Where are you?", subtitle: "Pick the room or landmark you're closest to.")
                VStack(spacing: 8) {
                    ForEach(nav.graph.landmarks, id: \.id) { node in
                        choice(node.landmark ?? node.id, selected: here == node.id) {
                            here = node.id
                            if let d = destination, d.doors.contains(node.id) { destination = nil }
                        }
                    }
                }

                if let hereNode {
                    HStack(alignment: .top, spacing: 12) {
                        Text("Stand in front of the \(hereNode.landmark ?? "") door, facing it. Hold your phone upright.")
                            .font(.subheadline)
                            .foregroundStyle(.white.opacity(0.9))
                            .fixedSize(horizontal: false, vertical: true)
                        Spacer(minLength: 0)
                        MiniMap(graph: nav.graph, position: hereNode.point,
                                headingDegrees: hereNode.facingDoorDegrees ?? 0)
                            .frame(width: 100, height: 115)
                    }
                    .padding(12)
                    .background(Color.white.opacity(0.12), in: RoundedRectangle(cornerRadius: 14))
                    .accessibilityElement(children: .combine)

                    sectionTitle("Where to?", subtitle: nil)
                    VStack(spacing: 8) {
                        ForEach(nav.graph.destinations.filter { !$0.doors.contains(hereNode.id) }) { d in
                            choice("\(d.title) · \(d.subtitle)", selected: destination == d) { destination = d }
                        }
                    }
                }

                if let message = nav.trackingMessage {
                    Label(message, systemImage: "camera.viewfinder")
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(.yellow)
                }

                Button {
                    if let hereNode, let destination { nav.start(at: hereNode, to: destination) }
                } label: {
                    Text(startLabel).font(.title3.bold()).frame(maxWidth: .infinity).padding(.vertical, 16)
                }
                .buttonStyle(.borderedProminent)
                .tint(.fugaGreen)
                .disabled(hereNode == nil || destination == nil || !nav.trackingReady)
            }
            .padding(20)
        }
    }

    private var startLabel: String {
        if hereNode == nil { return "Pick where you are" }
        if destination == nil { return "Pick where to go" }
        return nav.trackingReady ? "Start" : "Getting ready…"
    }

    private func sectionTitle(_ title: String, subtitle: String?) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.title.bold()).foregroundStyle(.white)
            if let subtitle {
                Text(subtitle).font(.subheadline).foregroundStyle(.white.opacity(0.8))
            }
        }
        .padding(.top, 4)
        .accessibilityAddTraits(.isHeader)
    }

    private func choice(_ text: String, selected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack {
                Text(text).font(.headline).multilineTextAlignment(.leading)
                Spacer()
                if selected { Image(systemName: "checkmark.circle.fill").font(.title3) }
            }
            .foregroundStyle(.white)
            .padding(14)
            .background(selected ? Color.fugaGreen.opacity(0.9) : Color.white.opacity(0.14),
                        in: RoundedRectangle(cornerRadius: 14))
        }
        .accessibilityAddTraits(selected ? .isSelected : [])
    }

    // MARK: Guidance

    private var guidanceScreen: some View {
        VStack(spacing: 0) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("TO · \(nav.graph.floorLabel.uppercased())")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.white.opacity(0.7))
                    Text(nav.route?.to.name ?? "")
                        .font(.title2.bold())
                        .foregroundStyle(.white)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                }
                Spacer()
                Button { showMap.toggle() } label: {
                    Image(systemName: showMap ? "map.fill" : "map")
                        .font(.title3)
                        .foregroundStyle(.white)
                        .padding(10)
                        .background(.ultraThinMaterial, in: Circle())
                }
                .accessibilityLabel(showMap ? "Hide map" : "Show map")
            }

            Text(nav.instruction)
                .font(.title3.weight(.semibold))
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.top, 10)

            if nav.isOffRoute {
                Label("Off route. Turn until it vibrates.", systemImage: "exclamationmark.triangle.fill")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.yellow)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.top, 6)
            }
            if let message = nav.trackingMessage {
                Label(message, systemImage: "camera.viewfinder")
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(.yellow)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.top, 6)
            }

            if showMap {
                MiniMap(graph: nav.graph, route: nav.route, position: nav.planPosition, headingDegrees: nav.planHeading)
                    .frame(width: 150, height: 190)
                    .frame(maxWidth: .infinity, alignment: .trailing)
                    .padding(.top, 12)
            }

            Spacer()

            ExitArrowView(relativeBearing: nav.relativeBearing, distanceMeters: nav.distanceRemaining)
                .padding(.bottom, 16)

            HStack {
                Button("End") { nav.stop() }
                    .buttonStyle(.bordered)
                    .tint(.white)
                Spacer()
                Button { showRepin = true } label: {
                    Label("I'm at a landmark", systemImage: "mappin.and.ellipse")
                }
                .buttonStyle(.bordered)
                .tint(.white)
                .accessibilityHint("Tell Fuga which room you're next to, to fix your position")
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
        .confirmationDialog("Which one are you next to?", isPresented: $showRepin, titleVisibility: .visible) {
            ForEach(nav.graph.landmarks, id: \.id) { node in
                Button(node.landmark ?? node.id) { nav.repin(at: node) }
            }
            Button("Cancel", role: .cancel) {}
        }
    }
}

#Preview {
    ContentView()
}
