import SwiftUI

/// Small top-down map of the route with your position and facing direction.
/// Mainly for testing: if the dot drifts off the line, calibration or tracking is off.
struct MiniMap: View {
    let route: Route
    let position: Vec2?
    let headingDegrees: Double

    var body: some View {
        Canvas { context, size in
            let pts = route.points.map { Vec2(x: $0.x, y: $0.y) }
            var all = pts
            if let position { all.append(position) }
            guard let minX = all.map(\.x).min(), let maxX = all.map(\.x).max(),
                  let minY = all.map(\.y).min(), let maxY = all.map(\.y).max() else { return }
            let pad: CGFloat = 14
            let span = CGFloat(max(maxX - minX, maxY - minY, 1))
            let scale: CGFloat = (min(size.width, size.height) - 2 * pad) / span
            func screen(_ p: Vec2) -> CGPoint {
                // Plan y is up; screen y is down.
                CGPoint(x: pad + CGFloat(p.x - minX) * scale,
                        y: size.height - pad - CGFloat(p.y - minY) * scale)
            }

            var line = Path()
            line.addLines(pts.map(screen))
            context.stroke(line, with: .color(.fugaGreen), style: StrokeStyle(lineWidth: 4, lineCap: .round, lineJoin: .round))
            if let end = pts.last {
                let e = screen(end)
                context.fill(Path(CGRect(x: e.x - 5, y: e.y - 5, width: 10, height: 10)), with: .color(.white))
            }

            if let position {
                let p = screen(position)
                let h = headingDegrees * .pi / 180
                var cone = Path()
                cone.move(to: p)
                for a in stride(from: -0.45, through: 0.45, by: 0.15) {
                    let dx = CGFloat(22 * cos(h + a)), dy = CGFloat(22 * sin(h + a))
                    cone.addLine(to: CGPoint(x: p.x + dx, y: p.y - dy))
                }
                cone.closeSubpath()
                context.fill(cone, with: .color(.blue.opacity(0.35)))
                context.fill(Path(ellipseIn: CGRect(x: p.x - 6, y: p.y - 6, width: 12, height: 12)), with: .color(.blue))
                context.stroke(Path(ellipseIn: CGRect(x: p.x - 6, y: p.y - 6, width: 12, height: 12)), with: .color(.white), lineWidth: 2)
            }
        }
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 14))
        .accessibilityHidden(true)
    }
}
