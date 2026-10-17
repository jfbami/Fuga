import SwiftUI

/// The main guidance screen. For now: a placeholder where the camera/AR view will go,
/// the floor label, and the Find My–style arrow at the bottom center.
struct ContentView: View {
    @StateObject private var demo = CompassDemo()

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
                Spacer()
                ExitArrowView(
                    relativeBearing: demo.relativeBearing,
                    distanceMeters: demo.distanceMeters
                )
                .padding(.bottom, 24)
            }
            .padding(.horizontal, 20)
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
