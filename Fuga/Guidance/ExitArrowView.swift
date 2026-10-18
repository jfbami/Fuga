import SwiftUI

/// The bottom-center guidance arrow, styled after Apple Find My's precision-finding arrow:
/// a thick white arrow with rounded ends, a small dot marking the target, a puck that turns
/// green when you're facing the exit, and the distance in large type underneath.
///
/// Feed it a bearing *relative to where the phone is pointing*:
/// 0 = straight ahead, +90 = to the right, -90 = to the left, ±180 = behind.
struct ExitArrowView: View {
    /// Degrees from the phone's forward direction to the next point on the route. Positive is clockwise (right).
    var relativeBearing: Double
    /// Distance along the route to the exit, in meters.
    var distanceMeters: Double
    /// Diameter of the arrow puck in points.
    var size: CGFloat = 168

    /// Within this many degrees of straight ahead, the puck turns green (Find My uses a similar cone).
    static let alignedTolerance: Double = 20

    /// The arrow's on-screen angle. Kept "unwrapped" (it can go past 360) so a turn from 359° to 1°
    /// animates 2° instead of spinning the long way around.
    @State private var displayedAngle: Double = 0

    private var isAligned: Bool {
        abs(Self.normalized(relativeBearing)) <= Self.alignedTolerance
    }

    var body: some View {
        VStack(spacing: 12) {
            puck
            DistanceLabel(meters: distanceMeters, relativeBearing: relativeBearing)
        }
        .animation(.easeInOut(duration: 0.25), value: isAligned)
        .onAppear { displayedAngle = Self.normalized(relativeBearing) }
        .onChange(of: relativeBearing) { _, newBearing in
            let delta = Self.shortestDelta(from: displayedAngle, to: newBearing)
            withAnimation(.interpolatingSpring(stiffness: 170, damping: 22)) {
                displayedAngle += delta
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(DistanceLabel.spokenDescription(meters: distanceMeters, relativeBearing: relativeBearing))
    }

    private var puck: some View {
        ZStack {
            // Frosted dark puck so it reads over a busy camera feed; solid green when aligned.
            Circle()
                .fill(.ultraThinMaterial)
            Circle()
                .fill(isAligned ? Color.fugaGreen : Color.black.opacity(0.35))

            ZStack {
                ArrowGlyph()
                    .stroke(
                        .white,
                        style: StrokeStyle(lineWidth: size * 0.095, lineCap: .round, lineJoin: .round)
                    )
                    .frame(width: size * 0.40, height: size * 0.52)
                    .offset(y: size * 0.04)

                // The target dot sits just beyond the arrow tip, like the item dot in Find My.
                Circle()
                    .fill(.white)
                    .frame(width: size * 0.075, height: size * 0.075)
                    .offset(y: -size * 0.40)
            }
            .rotationEffect(.degrees(displayedAngle))
        }
        .frame(width: size, height: size)
        .shadow(color: .black.opacity(0.35), radius: 12, y: 4)
    }

    // MARK: - Angle helpers

    /// Wraps any angle into (-180, 180].
    static func normalized(_ degrees: Double) -> Double {
        var d = degrees.truncatingRemainder(dividingBy: 360)
        if d > 180 { d -= 360 }
        if d <= -180 { d += 360 }
        return d
    }

    /// Smallest signed rotation that takes `current` to `target`, in (-180, 180].
    static func shortestDelta(from current: Double, to target: Double) -> Double {
        normalized(target - current)
    }
}

/// The arrow itself: a straight shaft with two head strokes, drawn pointing up.
/// Stroke it with round caps and joins to get the Find My look.
struct ArrowGlyph: Shape {
    /// Angle between the shaft and each side of the head.
    var headAngle: Double = 42
    /// Head stroke length as a fraction of the shaft length.
    var headFraction: CGFloat = 0.5

    func path(in rect: CGRect) -> Path {
        let tip = CGPoint(x: rect.midX, y: rect.minY)
        let tail = CGPoint(x: rect.midX, y: rect.maxY)
        let shaftLength = rect.height
        let radians = headAngle * .pi / 180

        // Keep the head inside the frame's width.
        let maxHeadLength = (rect.width / 2) / CGFloat(sin(radians))
        let headLength = min(shaftLength * headFraction, maxHeadLength)
        let dx = headLength * CGFloat(sin(radians))
        let dy = headLength * CGFloat(cos(radians))

        var path = Path()
        path.move(to: tail)
        path.addLine(to: tip)
        path.move(to: CGPoint(x: tip.x - dx, y: tip.y + dy))
        path.addLine(to: tip)
        path.addLine(to: CGPoint(x: tip.x + dx, y: tip.y + dy))
        return path
    }
}

extension Color {
    /// iOS system green (#34C759), the color Find My uses when you're on target.
    static let fugaGreen = Color(red: 0.204, green: 0.780, blue: 0.349)
}

#Preview("Arrow states") {
    ZStack {
        Color(white: 0.12).ignoresSafeArea()
        VStack(spacing: 40) {
            HStack(spacing: 24) {
                ExitArrowView(relativeBearing: 0, distanceMeters: 4, size: 120)
                ExitArrowView(relativeBearing: 35, distanceMeters: 12, size: 120)
            }
            HStack(spacing: 24) {
                ExitArrowView(relativeBearing: -90, distanceMeters: 25, size: 120)
                ExitArrowView(relativeBearing: 170, distanceMeters: 0.8, size: 120)
            }
        }
    }
}
