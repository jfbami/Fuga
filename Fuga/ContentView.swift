import SwiftUI

/// The main guidance screen. For now: a placeholder where the camera/AR view will go,
/// the floor label, and the Find My–style arrow at the bottom center.
struct ContentView: View {
    @StateObject private var demo = CompassDemo()
    @StateObject private var voice = VoiceGuidance()
    @State private var offCourseHaptics = OffCourseHaptics()
    @State private var subtleHapticPulse = 0
    @State private var strongHapticPulse = 0
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        ZStack {
            // Placeholder for the AR camera view (role 1 replaces this with ARView).
            LinearGradient(
                colors: [Color(white: 0.16), Color(white: 0.06)],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()

            VStack {
                topBar
                HStack {
                    Button {
                        voice.setEnabled(!voice.isEnabled)
                    } label: {
                        Label(voice.isEnabled ? "Mute guidance" : "Enable voice",
                              systemImage: voice.isEnabled ? "speaker.wave.2.fill" : "speaker.slash.fill")
                    }
                    .buttonStyle(.bordered)
                    Spacer()
                }
                Text(voice.status)
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.6))
                    .frame(maxWidth: .infinity, alignment: .leading)
                Spacer()
                ExitArrowView(
                    relativeBearing: demo.relativeBearing,
                    distanceMeters: demo.distanceMeters
                )
                .padding(.bottom, 24)
            }
            .padding(.horizontal, 20)
        }
        .sensoryFeedback(.impact(weight: .light, intensity: 0.4), trigger: subtleHapticPulse) { _, _ in
            scenePhase == .active
        }
        .sensoryFeedback(.impact(weight: .heavy, intensity: 1), trigger: strongHapticPulse) { _, _ in
            scenePhase == .active
        }
        .task(id: scenePhase) {
            offCourseHaptics.reset()
            guard scenePhase == .active else {
                voice.stop()
                return
            }
            // Sampling also permits stable cues/repeats when the compass is stationary.
            while !Task.isCancelled {
                voice.update(bearing: demo.relativeBearing, distance: demo.distanceMeters)
                if let strength = offCourseHaptics.update(
                    bearing: demo.relativeBearing,
                    distance: demo.distanceMeters,
                    now: ProcessInfo.processInfo.systemUptime
                ) {
                    switch strength {
                    case .subtle: subtleHapticPulse += 1
                    case .strong: strongHapticPulse += 1
                    }
                }
                do {
                    try await Task.sleep(for: .milliseconds(250))
                } catch { break }
            }
            voice.stop()
            offCourseHaptics.reset()
        }
        .onDisappear {
            voice.stop()
            offCourseHaptics.reset()
        }
    }

    private var topBar: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 2) {
                Text("FINDING EXIT")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.white.opacity(0.6))
                Text("2nd Floor")
                    .font(.title.bold())
                    .foregroundStyle(.white)
            }
            Spacer()
            #if DEBUG
            demoControls
            #endif
        }
        .padding(.top, 8)
    }

    #if DEBUG
    /// Temporary controls for testing the arrow; removed once real routing drives it.
    private var demoControls: some View {
        VStack(alignment: .trailing, spacing: 8) {
            Button("Exit is this way") { demo.setExitAhead() }
                .buttonStyle(.borderedProminent)
                .tint(.fugaGreen)
                .disabled(demo.isSimulated)
            Stepper(
                "\(Int(demo.distanceMeters.rounded())) m",
                value: $demo.distanceMeters,
                in: 0...60,
                step: 1
            )
            .fixedSize()
            .foregroundStyle(.white)
            if demo.isSimulated {
                Text("Simulator: sweeping heading")
                    .font(.caption2)
                    .foregroundStyle(.white.opacity(0.6))
            }
        }
    }
    #endif
}

#Preview {
    ContentView()
}
