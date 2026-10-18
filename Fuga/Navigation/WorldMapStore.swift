import ARKit
import Foundation

/// How ARKit's world (top-down x, -z) lines up with the floor plan:
/// plan = planOrigin + rotate(ar - arOrigin, by: rotationDegrees).
struct MapAlignment: Codable {
    var arOrigin: [Double]
    var planOrigin: [Double]
    var rotationDegrees: Double
    var checkpoints: [String]
    var createdAt: Date

    func toPlan(_ ar: Vec2) -> Vec2 {
        Vec2(x: planOrigin[0], y: planOrigin[1]) + (ar - Vec2(x: arOrigin[0], y: arOrigin[1])).rotated(byDegrees: rotationDegrees)
    }
}

enum MapAligner {
    /// Best rotation + translation taking AR points onto plan points (2D Kabsch, no scale:
    /// both are meters). Needs 2+ pairs. Checked offline on the MGH scan: 2 checkpoints
    /// (elevator + 430 door) land within 0.4 m of the full-walk alignment.
    static func fitRigid(ar: [Vec2], plan: [Vec2]) -> (arOrigin: Vec2, planOrigin: Vec2, rotationDegrees: Double)? {
        guard ar.count >= 2, ar.count == plan.count else { return nil }
        let n = Double(ar.count)
        let ca = ar.reduce(Vec2(x: 0, y: 0), +) * (1 / n)
        let cp = plan.reduce(Vec2(x: 0, y: 0), +) * (1 / n)
        var sinSum = 0.0, cosSum = 0.0
        for (a, p) in zip(ar, plan) {
            let u = a - ca, v = p - cp
            sinSum += u.x * v.y - u.y * v.x
            cosSum += u.dot(v)
        }
        return (ca, cp, atan2(sinSum, cosSum) * 180 / .pi)
    }
}

/// Saves and loads the ARKit map of a floor plus its alignment to the plan.
/// Looks in the app's Documents first (a map recorded on this phone), then the app bundle
/// (a map recorded on another phone and added to Fuga/Maps).
enum WorldMapStore {
    static let mapExtension = "arworldmap"

    static var documents: URL {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
    }

    static func mapURL(_ name: String) -> URL { documents.appendingPathComponent("\(name).\(mapExtension)") }
    static func alignmentURL(_ name: String) -> URL { documents.appendingPathComponent("\(name).alignment.json") }

    static func save(map: ARWorldMap, alignment: MapAlignment, name: String) throws {
        let data = try NSKeyedArchiver.archivedData(withRootObject: map, requiringSecureCoding: true)
        try data.write(to: mapURL(name), options: .atomic)
        let encoder = JSONEncoder()
        encoder.outputFormatting = .prettyPrinted
        encoder.dateEncodingStrategy = .iso8601
        try encoder.encode(alignment).write(to: alignmentURL(name), options: .atomic)
    }

    static func load(name: String) -> (map: ARWorldMap, alignment: MapAlignment, source: String)? {
        let candidates: [(URL?, URL?, String)] = [
            (mapURL(name), alignmentURL(name), "recorded on this phone"),
            (Bundle.main.url(forResource: name, withExtension: mapExtension),
             Bundle.main.url(forResource: "\(name).alignment", withExtension: "json"), "built into the app"),
        ]
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        for (m, a, source) in candidates {
            guard let m, let a,
                  let mapData = try? Data(contentsOf: m),
                  let alignData = try? Data(contentsOf: a),
                  let map = try? NSKeyedUnarchiver.unarchivedObject(ofClass: ARWorldMap.self, from: mapData),
                  let alignment = try? decoder.decode(MapAlignment.self, from: alignData) else { continue }
            return (map, alignment, source)
        }
        return nil
    }

    static func delete(name: String) {
        try? FileManager.default.removeItem(at: mapURL(name))
        try? FileManager.default.removeItem(at: alignmentURL(name))
    }
}
