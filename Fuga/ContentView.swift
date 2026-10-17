import SwiftUI

/// Two screens over the live camera:
/// 1. At the elevator: pick a room, face down the hallway, tap Start.
/// 2. Guidance: Find My–style arrow, distance, next instruction, spoken turns and vibration.
struct ContentView: View {
    @StateObject private var nav = RouteNavigator()
    @State private var destination = MaryGatesHall4.destinations[0]
    @State private var showMap = true
    @State private var loadError: String?

    private let start = MaryGatesHall4.start

    var body: some View {
        ZStack {
            ARCameraView(session: nav.session)
                .ignoresSafeArea()
            // Darken the camera a little so white text stays readable.
            LinearGradient(colors: [.black.opacity(0.55), .clear, .black.opacity(0.6)],
                           startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea()
                .allowsHitTesting(false)

            if nav.phase == .idle {
                startScreen
            } else {
                guidanceScreen
            }
        }
        .onAppear { nav.runCamera() }
        .onDisappear { nav.pauseCamera() }
    }

    // MARK: Start

    private var startScreen: some View {
        VStack(alignment: .leading, spacing: 18) {
            VStack(alignment: .leading, spacing: 2) {
                Text("\(start.building.uppercased()) · \(start.floorLabel.uppercased())")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.white.opacity(0.7))
                Text("Where to?")
                    .font(.largeTitle.bold())
                    .foregroundStyle(.white)
            }

            VStack(spacing: 10) {
                ForEach(MaryGatesHall4.destinations) { d in
                    Button {
                        destination = d
                    } label: {
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
                        .padding(16)
                        .background(destination == d ? Color.fugaGreen.opacity(0.9) : Color.white.opacity(0.14),
                                    in: RoundedRectangle(cornerRadius: 16))
                    }
                    .accessibilityLabel("\(d.title), \(d.subtitle)")
                    .accessibilityAddTraits(destination == d ? .isSelected : [])
                }
            }

            Spacer()

            Text(start.instruction)
                .font(.body)
                .foregroundStyle(.white)
                .fixedSize(horizontal: false, vertical: true)

            if let message = nav.trackingMessage {
                Label(message, systemImage: "camera.viewfinder")
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(.yellow)
            }
            if let loadError {
                Text(loadError).font(.subheadline).foregroundStyle(.red)
            }

            Button(action: begin) {
                Text(nav.trackingReady ? "Start" : "Getting ready…")
                    .font(.title3.bold())
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
            }
            .buttonStyle(.borderedProminent)
            .tint(.fugaGreen)
            .disabled(!nav.trackingReady)
            .accessibilityHint("Starts guidance from the elevator to \(destination.subtitle)")
        }
        .padding(20)
    }

    private func begin() {
        guard let route = Route.load(resource: destination.routeResource) else {
            loadError = "Couldn't load the route for \(destination.title)."
            return
        }
        loadError = nil
        nav.start(route: route, from: start)
    }

    // MARK: Guidance

    private var guidanceScreen: some View {
        VStack(spacing: 0) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("TO \(start.floorLabel.uppercased())")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.white.opacity(0.7))
                    Text("\(destination.title) \(destination.subtitle)")
                        .font(.title2.bold())
                        .foregroundStyle(.white)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                }
                Spacer()
                Button {
                    showMap.toggle()
                } label: {
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
                Label("Off route — turn until it vibrates", systemImage: "exclamationmark.triangle.fill")
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

            if showMap, let route = nav.route {
                MiniMap(route: route, position: nav.planPosition, headingDegrees: nav.planHeading)
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
                Button("I'm at the elevator") { nav.recalibrateAtStart() }
                    .buttonStyle(.bordered)
                    .tint(.white)
                    .accessibilityHint("Restarts guidance from the elevator, facing down the hallway")
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
    }
}

#Preview {
    ContentView()
}
