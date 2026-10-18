import SwiftUI

/// Small top-down map: the floor's hallways (gray), the route (green), the path walked while
/// mapping (blue), checkpoints, and you (blue dot + facing cone).
struct MiniMap: View {
    let graph: HallwayGraph
    var route: Route?
    var trail: [Vec2] = []
    var position: Vec2?
    var headingDegrees: Double = 0
    var highlight: [String] = []

    var body: some View {
        Canvas { context, size in
            let nodes = graph.nodes.map(\.point)
            var all = nodes + trail
            if let position { all.append(position) }
            guard let minX = all.map(\.x).min(), let maxX = all.map(\.x).max(),
                  let minY = all.map(\.y).min(), let maxY = all.map(\.y).max() else { return }
            let pad: CGFloat = 14
            let spanX = CGFloat(max(maxX - minX, 1)), spanY = CGFloat(max(maxY - minY, 1))
            let scale: CGFloat = min((size.width - 2 * pad) / spanX, (size.height - 2 * pad) / spanY)
            let offX = (size.width - spanX * scale) / 2, offY = (size.height - spanY * scale) / 2
            func screen(_ p: Vec2) -> CGPoint {
                // Plan y is up; screen y is down.
                CGPoint(x: offX + CGFloat(p.x - minX) * scale,
                        y: size.height - offY - CGFloat(p.y - minY) * scale)
            }

            // Hallways
            var halls = Path()
            for e in graph.edges where e.count == 2 {
                guard let a = graph.node(e[0]), let b = graph.node(e[1]) else { continue }
                halls.move(to: screen(a.point))
                halls.addLine(to: screen(b.point))
            }
            context.stroke(halls, with: .color(.white.opacity(0.3)), style: StrokeStyle(lineWidth: 6, lineCap: .round, lineJoin: .round))

            // Walked path (mapping)
            if trail.count > 1 {
                var t = Path()
                t.addLines(trail.map(screen))
                context.stroke(t, with: .color(.blue.opacity(0.8)), style: StrokeStyle(lineWidth: 2, lineCap: .round, lineJoin: .round))
            }

            // Route
            if let route, route.points.count > 1 {
                var line = Path()
                line.addLines(route.points.map { screen(Vec2(x: $0.x, y: $0.y)) })
                context.stroke(line, with: .color(.fugaGreen), style: StrokeStyle(lineWidth: 4, lineCap: .round, lineJoin: .round))
                if let end = route.points.last {
                    let e = screen(Vec2(x: end.x, y: end.y))
                    context.fill(Path(CGRect(x: e.x - 5, y: e.y - 5, width: 10, height: 10)), with: .color(.white))
                }
            }

            // Checkpoints already marked
            for id in highlight {
                guard let n = graph.node(id) else { continue }
                let c = screen(n.point)
                context.fill(Path(ellipseIn: CGRect(x: c.x - 5, y: c.y - 5, width: 10, height: 10)), with: .color(.yellow))
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
                let dot = CGRect(x: p.x - 6, y: p.y - 6, width: 12, height: 12)
                context.fill(Path(ellipseIn: dot), with: .color(.blue))
                context.stroke(Path(ellipseIn: dot), with: .color(.white), lineWidth: 2)
            }
        }
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 14))
        .accessibilityHidden(true)
    }
}
