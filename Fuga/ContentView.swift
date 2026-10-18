import SwiftUI

/// Screens over the live camera:
/// 1. Start: finds you on the saved map (or falls back to the elevator), pick a room, Start.
/// 2. Guidance: Find My–style arrow, distance, next instruction, spoken turns and vibration.
/// 3. Mapping Mode: record the floor's 3D map once and tie it to the floor plan.
struct ContentView: View {
    @StateObject private var nav: RouteNavigator
    @State private var destination: HallwayGraph.Destination
    @State private var showMap = true

    init() {
        guard let graph = HallwayGraph.load(resource: "mgh4_graph") else {
            fatalError("mgh4_graph.json is missing from the app bundle (Fuga/Maps).")
        }
        _nav = StateObject(wrappedValue: RouteNavigator(graph: graph))
        _destination = State(initialValue: graph.destinations[0])
    }

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
            case .mapping: mappingScreen
            }
        }
        .onAppear { nav.runCamera() }
        .onDisappear { nav.pauseCamera() }
    }

    // MARK: Start

    private var startScreen: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("\(nav.graph.building.uppercased()) · \(nav.graph.floorLabel.uppercased())")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.white.opacity(0.7))
                    Text("Where to?")
                        .font(.largeTitle.bold())
                        .foregroundStyle(.white)
                }

                locationCard

                VStack(spacing: 10) {
                    ForEach(nav.graph.destinations) { d in
                        Button { destination = d } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(d.title).font(.title2.bold())
                                    Text(d.subtitle).font(.subheadline)
                                }
                                Spacer()
                                if destination == d {
                                    Image(systemName: "checkmark.circle.fill").font(.title2)
                                }
                            }
                            .foregroundStyle(.white)
                            .padding(14)
                            .background(destination == d ? Color.fugaGreen.opacity(0.9) : Color.white.opacity(0.14),
                                        in: RoundedRectangle(cornerRadius: 16))
                        }
                        .accessibilityLabel("\(d.title), \(d.subtitle)")
                        .accessibilityAddTraits(destination == d ? .isSelected : [])
                    }
                }

                if let message = nav.trackingMessage {
                    Label(message, systemImage: "camera.viewfinder")
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(.yellow)
                }

                if nav.localization == .located {
                    Button { nav.startHere(to: destination) } label: {
                        Text("Start from here").font(.title3.bold()).frame(maxWidth: .infinity).padding(.vertical, 16)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.fugaGreen)
                    .accessibilityHint("Guides you from where you are now to \(destination.subtitle)")

                    Button("I'm at the elevator instead") { nav.startAtElevator(to: destination) }
                        .buttonStyle(.bordered)
                        .tint(.white)
                } else {
                    Text("Or start from the elevator: step out, face straight down the hallway, hold your phone upright, then tap below.")
                        .font(.subheadline)
                        .foregroundStyle(.white.opacity(0.85))
                        .fixedSize(horizontal: false, vertical: true)
                    Button { nav.startAtElevator(to: destination) } label: {
                        Text(nav.trackingReady ? "Start at the elevator" : "Getting ready…")
                            .font(.title3.bold()).frame(maxWidth: .infinity).padding(.vertical, 16)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.fugaGreen)
                    .disabled(!nav.trackingReady)
                }

                Button {
                    nav.startMapping()
                } label: {
                    Label("Mapping Mode", systemImage: "map")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .tint(.white)
                .padding(.top, 4)
            }
            .padding(20)
        }
    }

    @ViewBuilder
    private var locationCard: some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                switch nav.localization {
                case .located:
                    Label("Found you", systemImage: "location.fill")
                        .font(.headline).foregroundStyle(Color.fugaGreen)
                    Text(nav.whereYouAre ?? "On the map").font(.subheadline).foregroundStyle(.white)
                case .searching:
                    Label("Finding where you are…", systemImage: "location.magnifyingglass")
                        .font(.headline).foregroundStyle(.white)
                    Text("Look around the hallway slowly so the camera can recognize it.")
                        .font(.subheadline).foregroundStyle(.white.opacity(0.85))
                case .noMap:
                    Label("No map of this floor yet", systemImage: "map")
                        .font(.headline).foregroundStyle(.white)
                    Text("Record one in Mapping Mode to start from anywhere.")
                        .font(.subheadline).foregroundStyle(.white.opacity(0.85))
                }
                if let source = nav.mapSource {
                    Text("Map \(source)").font(.caption).foregroundStyle(.white.opacity(0.6))
                }
            }
            .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
            if nav.localization == .located {
                MiniMap(graph: nav.graph, position: nav.planPosition, headingDegrees: nav.planHeading)
                    .frame(width: 110, height: 120)
            }
        }
        .padding(14)
        .background(Color.white.opacity(0.12), in: RoundedRectangle(cornerRadius: 16))
        .accessibilityElement(children: .combine)
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

            Button("End") { nav.stop() }
                .buttonStyle(.bordered)
                .tint(.white)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
    }

    // MARK: Mapping Mode

    private var mappingScreen: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text("Mapping Mode").font(.largeTitle.bold()).foregroundStyle(.white)
                Text("1. Start just outside the elevator, facing down the hallway, and tap **Elevator** below.\n2. Walk every hallway slowly, in both directions, phone upright.\n3. At each place below, stand there and tap it. At least 2, far apart.\n4. Tap **Save map**.")
                    .font(.subheadline)
                    .foregroundStyle(.white.opacity(0.9))
                    .fixedSize(horizontal: false, vertical: true)

                HStack(alignment: .top, spacing: 12) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(nav.mappingStatus).font(.headline).foregroundStyle(.white)
                        if let message = nav.trackingMessage {
                            Text(message).font(.subheadline).foregroundStyle(.yellow)
                        }
                        if let message = nav.mapMessage {
                            Text(message).font(.subheadline).foregroundStyle(Color.fugaGreen)
                        }
                    }
                    Spacer(minLength: 0)
                    MiniMap(graph: nav.graph, trail: nav.mappingPath, position: nav.planPosition,
                            headingDegrees: nav.planHeading, highlight: nav.checkpointsTaken)
                        .frame(width: 140, height: 170)
                }

                VStack(spacing: 8) {
                    ForEach(nav.graph.checkpoints, id: \.id) { cp in
                        Button { nav.markCheckpoint(cp.id) } label: {
                            HStack {
                                Text(cp.checkpoint ?? cp.id).multilineTextAlignment(.leading)
                                Spacer()
                                if nav.checkpointsTaken.contains(cp.id) {
                                    Image(systemName: "checkmark.circle.fill")
                                }
                            }
                            .foregroundStyle(.white)
                            .padding(12)
                            .background(Color.white.opacity(0.14), in: RoundedRectangle(cornerRadius: 12))
                        }
                        .disabled(!nav.trackingReady)
                    }
                }

                Button { nav.saveMap() } label: {
                    Text("Save map").font(.title3.bold()).frame(maxWidth: .infinity).padding(.vertical, 14)
                }
                .buttonStyle(.borderedProminent)
                .tint(.fugaGreen)
                .disabled(!nav.canSaveMap)

                if !nav.savedMapFiles.isEmpty {
                    ShareLink(items: nav.savedMapFiles) {
                        Label("Share map files (AirDrop to your Mac)", systemImage: "square.and.arrow.up")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                    .tint(.white)
                }

                HStack {
                    Button("Done") { nav.endMapping() }
                        .buttonStyle(.bordered)
                        .tint(.white)
                    Spacer()
                    Button("Delete saved map", role: .destructive) { nav.deleteSavedMap() }
                        .buttonStyle(.bordered)
                }
            }
            .padding(20)
        }
    }
}

#Preview {
    ContentView()
}
