import Foundation

/// Hallway graph for one floor (tools/mapping/build_graph.py). Nodes sit on corridor
/// centerlines in plan meters; door nodes carry where the door itself is.
struct HallwayGraph: Codable {
    struct Node: Codable {
        let id: String
        let x: Double
        let y: Double
        let doorX: Double?
        let doorY: Double?
        /// If set, a person can stand here, facing the door, to tell the app where they are.
        let landmark: String?

        var point: Vec2 { Vec2(x: x, y: y) }
        var door: Vec2? {
            guard let doorX, let doorY else { return nil }
            return Vec2(x: doorX, y: doorY)
        }

        /// Measured phone position, directly in front of the door toward the corridor.
        /// The graph node is the centerline projection, not where the user stands.
        func standingPoint(distanceFromDoor meters: Double) -> Vec2? {
            guard meters.isFinite, meters >= 0.2, meters <= 3,
                  let door, (point - door).length > 0.05 else { return nil }
            return door + (point - door) * (meters / (point - door).length)
        }

        /// Plan direction you face when standing here looking at the door.
        var facingDoorDegrees: Double? {
            guard let door else { return nil }
            return (door - point).angleDegrees
        }
    }

    struct Destination: Codable, Identifiable, Hashable {
        let id: String
        let title: String
        let subtitle: String
        let doors: [String]
    }

    let building: String
    let floorLabel: String
    let startNode: String
    let startFacingDegrees: Double
    let nodes: [Node]
    let edges: [[String]]
    let destinations: [Destination]

    static func load(resource: String) -> HallwayGraph? {
        guard let url = Bundle.main.url(forResource: resource, withExtension: "json"),
              let data = try? Data(contentsOf: url) else { return nil }
        return try? JSONDecoder().decode(HallwayGraph.self, from: data)
    }

    func node(_ id: String) -> Node? { nodes.first { $0.id == id } }

    /// Places you can say you're next to.
    var landmarks: [Node] { nodes.filter { $0.landmark != nil && $0.door != nil } }

    /// Closest point on any hallway edge, and how far away it is.
    func nearestOnGraph(_ p: Vec2) -> (a: String, b: String, point: Vec2, distance: Double)? {
        var best: (a: String, b: String, point: Vec2, distance: Double)?
        for e in edges where e.count == 2 {
            guard let na = node(e[0]), let nb = node(e[1]) else { continue }
            let a = na.point, ab = nb.point - a
            let l2 = max(ab.dot(ab), 1e-9)
            let t = min(1, max(0, (p - a).dot(ab) / l2))
            let q = a + ab * t
            let d = (p - q).length
            if best == nil || d < best!.distance { best = (e[0], e[1], q, d) }
        }
        return best
    }

    /// Shortest route from a position to the nearest door of a destination.
    /// Returns a Route the navigator can follow (points + arrival sentence).
    func route(from p: Vec2, to destination: Destination, fromName: String = "your location") -> Route? {
        guard let start = nearestOnGraph(p) else { return nil }

        // Adjacency with edge lengths.
        var adj: [String: [(String, Double)]] = [:]
        for e in edges where e.count == 2 {
            guard let na = node(e[0]), let nb = node(e[1]) else { continue }
            let d = (na.point - nb.point).length
            adj[e[0], default: []].append((e[1], d))
            adj[e[1], default: []].append((e[0], d))
        }

        // Dijkstra from the projected point, entering the graph at both ends of its edge.
        var dist: [String: Double] = [:]
        var prev: [String: String] = [:]
        if let na = node(start.a) { dist[start.a] = (start.point - na.point).length }
        if let nb = node(start.b) { dist[start.b] = min(dist[start.b] ?? .infinity, (start.point - nb.point).length) }
        var open = Set(dist.keys)
        var done = Set<String>()
        while let u = open.min(by: { (dist[$0] ?? .infinity) < (dist[$1] ?? .infinity) }) {
            open.remove(u)
            done.insert(u)
            let du = dist[u] ?? .infinity
            for (v, w) in adj[u] ?? [] where !done.contains(v) {
                if du + w < (dist[v] ?? .infinity) {
                    dist[v] = du + w
                    prev[v] = u
                    open.insert(v)
                }
            }
        }

        guard let door = destination.doors.min(by: { (dist[$0] ?? .infinity) < (dist[$1] ?? .infinity) }),
              dist[door] != nil, let doorNode = node(door) else { return nil }
        var chain = [door]
        while let before = prev[chain.last!] { chain.append(before) }
        chain.reverse()

        // Points: where you are (if you're off the centerline), onto the hallway, then along it.
        var raw: [Vec2] = []
        if start.distance > 0.5 { raw.append(p) }
        raw.append(start.point)
        raw += chain.compactMap { node($0)?.point }
        let points = HallwayGraph.simplify(raw)

        let length = zip(points, points.dropFirst()).reduce(0) { $0 + ($1.1 - $1.0).length }
        let side = HallwayGraph.side(of: doorNode.door, after: points) ?? ""
        let name = destination.id == "elevator"
            ? destination.title : "\(destination.title) \(destination.subtitle)"
        let say: String
        switch side {
        case "left", "right": say = "\(name) is on your \(side)"
        case "ahead": say = "\(name) is ahead"
        default: say = "You've arrived at \(name)"
        }

        return Route(
            from: .init(id: "here", name: fromName),
            to: .init(id: destination.id, name: name),
            lengthMeters: length,
            points: points.map { .init(x: $0.x, y: $0.y) },
            steps: [.init(action: "arrive", meters: nil, direction: nil, degrees: nil,
                          name: name, side: side, say: say)]
        )
    }

    /// Drops duplicate points and points the path goes straight through.
    static func simplify(_ pts: [Vec2]) -> [Vec2] {
        var out: [Vec2] = []
        for p in pts where out.last.map({ ($0 - p).length > 0.3 }) ?? true { out.append(p) }
        guard out.count > 2 else { return out }
        var kept = [out[0]]
        for i in 1..<(out.count - 1) {
            let a1 = (out[i] - kept[kept.count - 1]).angleDegrees
            let a2 = (out[i + 1] - out[i]).angleDegrees
            if abs(RouteTracker.wrap(a2 - a1)) > 10 { kept.append(out[i]) }
        }
        kept.append(out[out.count - 1])
        return kept
    }

    /// Which side the door is on, judged against the last stretch of the walk.
    static func side(of door: Vec2?, after points: [Vec2]) -> String? {
        guard let door, points.count >= 2 else { return nil }
        let a = points[points.count - 2], b = points[points.count - 1]
        let ab = b - a
        let cross = ab.x * (door.y - a.y) - ab.y * (door.x - a.x)
        if abs(cross) < 0.3 * ab.length { return "ahead" }
        return cross > 0 ? "left" : "right"
    }
}
