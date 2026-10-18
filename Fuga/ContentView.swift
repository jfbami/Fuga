import SwiftUI

/// Screens over the live camera:
/// 1. Start: find the starting location from the camera; destination input is independent.
/// 2. Guidance: Find My–style arrow, distance, next instruction, spoken turns and vibration.
///    Find where I am looks again from the camera. Optional ElevenLabs direction
///    cues and off-course nudges (pulses when you face well away from the route).
struct ContentView: View {
    @StateObject private var nav: RouteNavigator
    @State private var showMap = true
    @State private var showQuickLook = false
    @StateObject private var voice: VoiceGuidance
    @StateObject private var feedbackTest: FeedbackTest
    @State private var offCourseHaptics = OffCourseHaptics()
    @State private var subtleHapticPulse = 0
    @State private var strongHapticPulse = 0
    @Environment(\.scenePhase) private var scenePhase

    init() {
        guard let graph = HallwayGraph.load(resource: "mgh4_graph") else {
            fatalError("mgh4_graph.json is missing from the app bundle (Fuga/Maps).")
        }
        _nav = StateObject(wrappedValue: RouteNavigator(graph: graph))
        let voice = VoiceGuidance()
        _voice = StateObject(wrappedValue: voice)
        _feedbackTest = StateObject(wrappedValue: FeedbackTest(voice: voice))
    }

    var body: some View {
        ZStack {
            if nav.phase != .idle {
                ARCameraView(session: nav.session, content: nav.floorPath)
                    .ignoresSafeArea()
                LinearGradient(colors: [.black.opacity(0.6), .black.opacity(0.1), .black.opacity(0.65)],
                               startPoint: .top, endPoint: .bottom)
                    .ignoresSafeArea()
                    .allowsHitTesting(false)
            }

            switch nav.phase {
            case .idle: startScreen
            case .navigating, .arrived: guidanceScreen
            }
        }
        .onAppear {
            nav.runCamera()
            nav.playCue = { [weak voice] cue in voice?.playTurn(cue) }
        }
        .onDisappear { nav.pauseCamera() }
        .sheet(isPresented: $showQuickLook) {
            QuickLookView(session: nav.session, onCameraWork: { feedbackTest.stop() })
        }
        // Off-course nudges: light pulses at 45°+ away from the route, heavy at 100°+.
        .sensoryFeedback(.impact(weight: .light, intensity: 0.4), trigger: subtleHapticPulse) { _, _ in
            scenePhase == .active
        }
        .sensoryFeedback(.impact(weight: .heavy, intensity: 1), trigger: strongHapticPulse) { _, _ in
            scenePhase == .active
        }
        .task(id: scenePhase) { await runCues() }
        .onDisappear {
            feedbackTest.stop()
            voice.stop()
            offCourseHaptics.reset()
        }
    }

    /// Samples the navigator 4 times a second for the ElevenLabs direction cues and the
    /// off-course nudges. Only while walking a route: arrival is announced by the navigator
    /// (by room name), so these never get an arrival distance.
    private func runCues() async {
        offCourseHaptics.reset()
        guard scenePhase == .active else {
            feedbackTest.stop()
            voice.stop()
            return
        }
        while !Task.isCancelled {
            if feedbackTest.running {
                // The idle-screen feedback test owns the shared voice player.
                // Silencing it every 250 ms would cut off its preview clips.
                offCourseHaptics.reset()
            } else if nav.phase == .navigating, nav.distanceRemaining >= 1.5, nav.trackingReady {
                // Don't talk over a spoken turn instruction.
                if !nav.isSpeaking {
                    voice.update(bearing: nav.relativeBearing, distance: nav.distanceRemaining)
                } else {
                    voice.silence()
                }
                if let strength = offCourseHaptics.update(bearing: nav.relativeBearing,
                                                          distance: nav.distanceRemaining,
                                                          now: ProcessInfo.processInfo.systemUptime) {
                    switch strength {
                    case .subtle: subtleHapticPulse += 1
                    case .strong: strongHapticPulse += 1
                    }
                }
            } else {
                voice.silence()
                offCourseHaptics.reset()
            }
            do { try await Task.sleep(for: .milliseconds(250)) } catch { break }
        }
        voice.stop()
        offCourseHaptics.reset()
    }

    // MARK: Automatic starting-location entry

    private var startScreen: some View {
        QuickLookView(session: nav.session, showsCloseButton: false,
                      onCameraWork: { feedbackTest.stop() },
                      feedbackAction: { feedbackTest.toggle() },
                      feedbackRunning: feedbackTest.running, feedbackStep: feedbackTest.step)
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
                Button { voice.setEnabled(!voice.isEnabled) } label: {
                    Image(systemName: voice.isEnabled ? "speaker.wave.2.fill" : "speaker.slash.fill")
                        .font(.title3)
                        .foregroundStyle(.white)
                        .padding(10)
                        .background(.ultraThinMaterial, in: Circle())
                }
                .accessibilityLabel(voice.isEnabled ? "Direction cues on. Tap to mute" : "Direction cues off. Tap to turn on")
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
            Text("Direction cues: \(voice.status)")
                .font(.caption)
                .foregroundStyle(.white.opacity(0.6))
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.top, 2)

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

            ExitArrowView(relativeBearing: nav.relativeBearing, distanceMeters: nav.distanceRemaining,
                          aligned: nav.phase == .arrived ? nil : nav.isAligned)
                .padding(.bottom, 16)

            HStack {
                Button("End") { nav.stop() }
                    .buttonStyle(.bordered)
                    .tint(.white)
                Spacer()
                Button { showQuickLook = true } label: {
                    Label("Find where I am", systemImage: "camera.viewfinder")
                }
                .buttonStyle(.bordered)
                .tint(.white)
                .accessibilityHint("Check your location using the camera")
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)

    }
}

#Preview {
    ContentView()
}
