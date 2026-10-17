import Foundation

/// A route produced by tools/mapping/route.py. Coordinates are plan meters:
/// origin at the plan's bottom-left, x to the right, y up the page.
struct Route: Codable, Identifiable {
    struct Place: Codable {
        let id: String
        let name: String
    }

    struct Point: Codable {
        let x: Double
        let y: Double
    }

    struct Step: Codable {
        let action: String      // "walk", "turn" or "arrive"
        let meters: Double?
        let direction: String?  // "left" / "right" for turns
        let degrees: Double?
        let name: String?
        let side: String?       // where the destination is on arrival: "left", "right", "ahead"
        let say: String
    }

    let from: Place
    let to: Place
    let lengthMeters: Double
    let points: [Point]
    let steps: [Step]

    var id: String { to.id }

    /// The sentence spoken on arrival, e.g. "Computer Classroom is on your right".
    var arrivalSentence: String {
        steps.last(where: { $0.action == "arrive" })?.say ?? "You've arrived at \(to.name)"
    }

    static func load(resource: String) -> Route? {
        guard let url = Bundle.main.url(forResource: resource, withExtension: "json"),
              let data = try? Data(contentsOf: url) else { return nil }
        return try? JSONDecoder().decode(Route.self, from: data)
    }
}

/// A place you can be guided to, and where guidance starts from.
struct Destination: Identifiable, Hashable {
    let id: String
    let title: String
    let subtitle: String
    let routeResource: String
}

/// Where a route starts and which way the person faces when they tap Start.
struct StartPoint {
    let building: String
    let floorLabel: String
    let instruction: String
    /// Facing direction at the start, in plan degrees (0 = right along the page, 90 = up the page).
    let facingDegrees: Double
}

enum MaryGatesHall4 {
    static let start = StartPoint(
        building: "Mary Gates Hall",
        floorLabel: "4th Floor",
        instruction: "Step out of the elevator and face straight down the hallway. Hold your phone upright, then tap Start.",
        // Out of the elevator is straight down the page on the MGH plan (checked against the LiDAR scan: -77°).
        facingDegrees: -90
    )

    static let destinations = [
        Destination(id: "430", title: "430", subtitle: "Computer Classroom", routeResource: "route_elevator_430"),
        Destination(id: "416", title: "416", subtitle: "iLounge", routeResource: "route_elevator_416"),
    ]
}
