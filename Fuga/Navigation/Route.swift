import Foundation

/// A route to follow, in plan meters (origin at the plan's bottom-left, x right, y up the page).
/// Built on the phone by HallwayGraph.route(from:to:), or loaded from tools/mapping/route.py output.
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

    /// The sentence spoken on arrival, e.g. "430 Computer Classroom is on your right".
    var arrivalSentence: String {
        steps.last(where: { $0.action == "arrive" })?.say ?? "You've arrived at \(to.name)"
    }
}
