import Foundation

func check(_ condition: Bool, _ message: String) { precondition(condition, message) }
func near(_ a: Vec2, _ b: Vec2) -> Bool { (a - b).length < 1e-8 }

// Rigid-transform round trips across all quadrants, arbitrary origins, and turns.
for angle in stride(from: -180.0, through: 180, by: 15) {
    let alignment = PlanAlignment(arOrigin: Vec2(x: 3, y: -7), planOrigin: Vec2(x: 19, y: 23), rotationDegrees: angle)
    for point in [Vec2(x: 0, y: 0), Vec2(x: -5, y: 17), Vec2(x: 100, y: -31)] {
        check(near(alignment.toAR(alignment.toPlan(point)), point), "AR/plan transform round trip")
    }
}
let quarterTurn = PlanAlignment(arOrigin: Vec2(x: 0, y: 0), planOrigin: Vec2(x: 10, y: 20), rotationDegrees: 90)
check(near(quarterTurn.toPlan(Vec2(x: 2, y: 0)), Vec2(x: 10, y: 22)), "Right-handed 90 degree transform")
check(PlanAlignment.cameraHeading(forward: Vec2(x: 0, y: 0.01)) == nil, "Reject near-vertical optical axis without substituting side axis")
check(PlanAlignment.cameraHeading(forward: Vec2(x: 1, y: 0)) == 0, "Camera east")
check(PlanAlignment.cameraHeading(forward: Vec2(x: 0, y: 1)) == 90, "Camera north")
check(PlanAlignment.cameraHeading(forward: Vec2(x: .nan, y: 1)) == nil, "Reject invalid heading")
check(RouteTracker.relativeBearing(from: Vec2(x: 0, y: 0), headingDegrees: 90, to: Vec2(x: 1, y: 0)) == 90, "Clockwise arrow bearing")
let node = HallwayGraph.Node(id: "door", x: 10, y: 20, doorX: 12, doorY: 20, landmark: "Test")
check(near(node.standingPoint(distanceFromDoor: 0.5)!, Vec2(x: 11.5, y: 20)), "Door offset does not pin user to corridor centerline")
check(node.standingPoint(distanceFromDoor: .nan) == nil, "Reject unmeasured offset")
check(node.standingPoint(distanceFromDoor: -1) == nil, "Reject negative offset")
var route = RouteTracker(points: [Vec2(x: 0, y: 0), Vec2(x: 10, y: 0), Vec2(x: 10, y: 1), Vec2(x: 0, y: 1)])
let first = route.project(Vec2(x: 2, y: 1))
check(route.segment == 0 && abs(first.along - 2) < 1e-8, "Parallel return corridor cannot steal progress")
_ = route.project(Vec2(x: 10, y: 0.5))
check(route.segment == 1, "Advance at actual corner")
_ = route.project(Vec2(x: 9.5, y: 1))
check(route.segment == 2, "Advance to return corridor at its corner")
var empty = RouteTracker(points: [])
check(empty.project(Vec2(x: 0, y: 0)).offRoute.isInfinite, "Empty route is invalid, not a crash")
var single = RouteTracker(points: [Vec2(x: 3, y: 4)])
check(single.project(Vec2(x: 0, y: 0)).offRoute == 5, "Single point route is safe")
print("Alignment regression tests passed: transforms, heading, doorway offset, parallel corridors, degenerate routes")
