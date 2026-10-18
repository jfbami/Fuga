import SwiftUI

/// Screens over the live camera:
/// 1. Start: find the starting location from the camera; destination input is independent.
/// 2. Guidance: Find My–style arrow, distance, next instruction, spoken turns and vibration.
///    Find where I am looks again from the camera. Juno narration and direction
///    cues and off-course nudges (pulses when you face well away from the route).
struct ContentView: View {
    @StateObject private var nav: RouteNavigator
    @State private var showMap = true
    @State private var showQuickLook = false
    @StateObject private var voice: VoiceGuidance
    @StateObject private var feedbackTest: FeedbackTest
    @StateObject private var haptics: OffCourseHapticPlayer
    @State private var showManualTest = false
    @State private var offCourseHaptics = OffCourseHaptics()
    @Environment(\.scenePhase) private var scenePhase

    init() {
        guard let graph = HallwayGraph.load(resource: "mgh4_graph") else {
            fatalError("mgh4_graph.json is missing from the app bundle (Fuga/Maps).")
        }
        let navigator = RouteNavigator(graph: graph)
        _nav = StateObject(wrappedValue: navigator)
        _voice = StateObject(wrappedValue: navigator.narration)
        let hapticPlayer = OffCourseHapticPlayer()
        _haptics = StateObject(wrappedValue: hapticPlayer)
        _feedbackTest = StateObject(wrappedValue: FeedbackTest(voice: navigator.narration, haptics: hapticPlayer))
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
        }
        .onDisappear { nav.pauseCamera() }
        .sheet(isPresented: $showQuickLook) {
            QuickLookView(session: nav.session, onCameraWork: { feedbackTest.stop() })
        }
        #if DEBUG
        .sheet(isPresented: $showManualTest) {
            ManualNavigationTestView(nav: nav) { landmark, destination, doorDistance in
                feedbackTest.stop()
                nav.start(at: landmark, to: destination, manualTest: true, doorDistance: doorDistance)
            }
        }
        #endif
        .task(id: scenePhase) { await runCues() }
        .onDisappear {
            feedbackTest.stop()
            voice.stop()
            offCourseHaptics.reset()
            haptics.stop()
        }
        .onChange(of: showQuickLook) { _, shown in
            if shown { voice.stop(); haptics.stop() }
        }
    }

    /// Samples the navigator 4 times a second for the ElevenLabs direction cues and the
    /// off-course nudges. Only while walking a route: arrival is announced by the navigator
    /// with a bundled Juno cue, so these never get an arrival distance.
    private func runCues() async {
        offCourseHaptics.reset()
        guard scenePhase == .active else {
            if nav.phase != .idle { nav.suspendGuidance("App paused. Recalibrate at a known doorway.") }
            feedbackTest.stop()
            voice.stop()
            haptics.stop()
            return
        }
        while !Task.isCancelled {
            nav.checkTrackingFreshness()
            if feedbackTest.running {
                // The idle-screen feedback test owns the shared voice player.
                // Silencing it every 250 ms would cut off its preview clips.
                offCourseHaptics.reset()
            } else if nav.phase == .navigating, nav.trackingReady, nav.guidanceReady, !showQuickLook, nav.distanceRemaining >= 1.5 {
                // Don't talk over a spoken turn instruction.
                // Turn announcements and direction reminders share one Juno player;
                // update() waits while an announcement is playing.
                voice.update(bearing: nav.relativeBearing, distance: nav.distanceRemaining)
                if let strength = offCourseHaptics.update(bearing: nav.relativeBearing,
                                                          distance: nav.distanceRemaining,
                                                          now: ProcessInfo.processInfo.systemUptime) {
                    haptics.play(strength)
                }
            } else {
                if nav.phase == .navigating { voice.silence() }
                offCourseHaptics.reset()
                if nav.phase != .idle { haptics.stop() }
            }
            do { try await Task.sleep(for: .milliseconds(250)) } catch { break }
        }
        voice.stop()
        offCourseHaptics.reset()
        haptics.stop()
    }

    // MARK: Automatic starting-location entry

    private var startScreen: some View {
        QuickLookView(session: nav.session, showsCloseButton: false,
                      onCameraWork: { feedbackTest.stop() },
                      feedbackAction: { feedbackTest.toggle() },
                      feedbackRunning: feedbackTest.running, feedbackStep: feedbackTest.step,
                      manualTestAction: manualTestAction)
    }

    private var manualTestAction: (() -> Void)? {
        #if DEBUG
        return { feedbackTest.stop(); showManualTest = true }
        #else
        return nil
        #endif
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
                .accessibilityLabel(voice.isEnabled ? "Juno narration on. Tap to mute" : "Juno narration off. Tap to turn on")
                Button { showMap.toggle() } label: {
                    Image(systemName: showMap ? "map.fill" : "map")
                        .font(.title3)
                        .foregroundStyle(.white)
                        .padding(10)
                        .background(.ultraThinMaterial, in: Circle())
                }
                .accessibilityLabel(showMap ? "Hide map" : "Show map")
            }

            if nav.isManualTest {
                Text("MANUAL TEST · UNVERIFIED MAP").font(.caption.bold()).foregroundStyle(.yellow)
            }
            Text(nav.instruction)
                .font(.title3.weight(.semibold))
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.top, 10)
            Text("Narration: \(voice.status)")
                .font(.caption)
                .foregroundStyle(.white.opacity(0.6))
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.top, 2)

            if nav.isOffRoute {
                Label("Off route. Stop and check your position.", systemImage: "exclamationmark.triangle.fill")
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

            if let message = nav.alignmentMessage {
                Text(message).foregroundStyle(.yellow).font(.subheadline)
            }
            if nav.guidanceReady {
                ExitArrowView(relativeBearing: nav.relativeBearing, distanceMeters: nav.distanceRemaining,
                              aligned: nav.phase == .arrived ? nil : nav.isAligned)
                    .padding(.bottom, 16)
            } else {
                Label("Guidance paused — recalibration needed", systemImage: "location.slash")
                    .foregroundStyle(.yellow).padding(.bottom, 16)
            }
            #if DEBUG
            Button("Recalibrate at a doorway") {
                feedbackTest.stop()
                nav.suspendGuidance("Recalibrating at a doorway.")
                showManualTest = true
            }
            .buttonStyle(.bordered)
            #endif

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
