import SceneKit
import SwiftUI
import UIKit

/// Walls and room labels for the 3D view, in plan meters (tools/mapping/build_walls.py).
/// Built from the UW floor plans, which are NetID-only, so the file isn't in the public repo:
/// add `mgh4_walls.json` to Fuga/Maps locally. Without it the view builds simple hallway walls
/// from the hallway graph.
struct BuildingWalls: Codable {
    struct Room: Codable { let id: String; let x: Double; let y: Double }
    var wallHeight: Double
    /// [x1, y1, x2, y2] in plan meters.
    var walls: [[Double]]
    var rooms: [Room]

    static func load(resource: String) -> BuildingWalls? {
        guard let url = Bundle.main.url(forResource: resource, withExtension: "json"),
              let data = try? Data(contentsOf: url) else { return nil }
        return try? JSONDecoder().decode(BuildingWalls.self, from: data)
    }

    /// Fallback: walls 1.1 m either side of every hallway in the graph.
    static func schematic(from graph: HallwayGraph, halfWidth: Double = 1.1) -> BuildingWalls {
        var walls: [[Double]] = []
        for e in graph.edges where e.count == 2 {
            guard let a = graph.node(e[0])?.point, let b = graph.node(e[1])?.point else { continue }
            let d = b - a
            guard d.length > 0.1 else { continue }
            let n = Vec2(x: -d.y, y: d.x) * (halfWidth / d.length)
            for s in [1.0, -1.0] {
                let p = a + n * s, q = b + n * s
                walls.append([p.x, p.y, q.x, q.y])
            }
        }
        return BuildingWalls(wallHeight: 2.7, walls: walls, rooms: [])
    }
}

/// A small 3D model of the floor, like a game minimap: a cut-away building (solid low walls,
/// glassy upper walls) so you can see into the hallways, the green route on the floor, and
/// you as a blue arrow. The camera follows behind you, turning as you turn.
struct Building3DView: UIViewRepresentable {
    let graph: HallwayGraph
    let walls: BuildingWalls
    var path: [PathPoint]
    var position: Vec2?
    var headingDegrees: Double

    func makeCoordinator() -> Building3DScene { Building3DScene(graph: graph, walls: walls) }

    func makeUIView(context: Context) -> SCNView {
        let view = SCNView(frame: .zero)
        view.scene = context.coordinator.scene
        view.pointOfView = context.coordinator.cameraNode
        view.backgroundColor = UIColor(red: 0.86, green: 0.90, blue: 0.95, alpha: 1)
        view.antialiasingMode = .multisampling4X
        view.preferredFramesPerSecond = 30
        view.isPlaying = true          // keeps the route's sweep animating
        view.allowsCameraControl = false
        return view
    }

    func updateUIView(_ view: SCNView, context: Context) {
        context.coordinator.update(path: path, position: position, headingDegrees: headingDegrees)
    }
}

final class Building3DScene {
    let scene = SCNScene()
    let cameraNode = SCNNode()
    private let puck = SCNNode()
    private let route = FloorPathNode(width: 1.0)
    private var unwrappedHeading: Double?

    /// Low solid walls you can see over; the rest of the wall height is glass.
    private let solidHeight: Float = 1.1

    init(graph: HallwayGraph, walls: BuildingWalls) {
        let root = scene.rootNode

        // Floor slab under everything.
        let xs = walls.walls.flatMap { [$0[0], $0[2]] } + graph.nodes.map(\.x)
        let ys = walls.walls.flatMap { [$0[1], $0[3]] } + graph.nodes.map(\.y)
        if let minX = xs.min(), let maxX = xs.max(), let minY = ys.min(), let maxY = ys.max() {
            let slab = SCNBox(width: CGFloat(maxX - minX + 2), height: 0.1, length: CGFloat(maxY - minY + 2), chamferRadius: 0)
            slab.firstMaterial = Self.lit(UIColor(white: 0.93, alpha: 1))
            let node = SCNNode(geometry: slab)
            node.position = SCNVector3(Float((minX + maxX) / 2), -0.05, Float(-(minY + maxY) / 2))
            root.addChildNode(node)
        }

        // Walls: solid lower part, glass upper part.
        let segments = walls.walls.compactMap { w -> (Vec2, Vec2)? in
            w.count == 4 ? (Vec2(x: w[0], y: w[1]), Vec2(x: w[2], y: w[3])) : nil
        }
        let lower = Self.wallMesh(segments, from: 0, to: solidHeight)
        lower.firstMaterial = Self.lit(UIColor(red: 0.91, green: 0.84, blue: 0.74, alpha: 1))
        root.addChildNode(SCNNode(geometry: lower))

        let upper = Self.wallMesh(segments, from: solidHeight, to: Float(walls.wallHeight))
        let glass = Self.lit(UIColor(white: 1, alpha: 0.18))
        glass.transparencyMode = .dualLayer
        glass.writesToDepthBuffer = false
        upper.firstMaterial = glass
        let upperNode = SCNNode(geometry: upper)
        upperNode.renderingOrder = 50
        root.addChildNode(upperNode)

        // Labels over the rooms you can navigate to.
        for d in graph.destinations {
            let spot: Vec2?
            if let room = walls.rooms.first(where: { $0.id == d.id }) {
                spot = Vec2(x: room.x, y: room.y)
            } else {
                spot = d.doors.compactMap { graph.node($0)?.door }.first
            }
            guard let spot else { continue }
            root.addChildNode(Self.label(d.id == "elevator" ? "Elevator" : d.id, at: spot))
        }

        // The route on the floor.
        route.fadeStart = 1e4
        route.fadeEnd = 2e4
        root.addChildNode(route)

        // You: white puck with a blue arrow, like Apple Maps.
        let disc = SCNCylinder(radius: 0.55, height: 0.08)
        disc.firstMaterial = Self.flat(.white)
        let discNode = SCNNode(geometry: disc)
        discNode.position.y = 0.04
        puck.addChildNode(discNode)

        let arrowPath = UIBezierPath()
        arrowPath.move(to: CGPoint(x: 0.4, y: 0))
        arrowPath.addLine(to: CGPoint(x: -0.28, y: 0.3))
        arrowPath.addLine(to: CGPoint(x: -0.12, y: 0))
        arrowPath.addLine(to: CGPoint(x: -0.28, y: -0.3))
        arrowPath.close()
        let arrow = SCNShape(path: arrowPath, extrusionDepth: 0.03)
        arrow.firstMaterial = Self.flat(UIColor(red: 0.0, green: 0.48, blue: 1.0, alpha: 1))
        let arrowNode = SCNNode(geometry: arrow)
        arrowNode.eulerAngles.x = -.pi / 2      // lay it flat, pointing along +x
        arrowNode.position.y = 0.1
        puck.addChildNode(arrowNode)

        let halo = SCNNode(geometry: SCNCylinder(radius: 0.9, height: 0.01))
        halo.geometry?.firstMaterial = Self.flat(UIColor(red: 0.0, green: 0.48, blue: 1.0, alpha: 0.25))
        halo.position.y = 0.02
        halo.runAction(.repeatForever(.sequence([
            .group([.scale(to: 1.4, duration: 1.0), .fadeOpacity(to: 0, duration: 1.0)]),
            .group([.scale(to: 1.0, duration: 0), .fadeOpacity(to: 1, duration: 0)]),
        ])))
        puck.addChildNode(halo)
        puck.isHidden = true
        root.addChildNode(puck)

        // Camera: behind and above you, looking at you.
        let camera = SCNCamera()
        camera.fieldOfView = 50
        camera.zNear = 0.1
        camera.zFar = 300
        cameraNode.camera = camera
        let look = SCNLookAtConstraint(target: puck)
        look.isGimbalLockEnabled = true
        cameraNode.constraints = [look]
        cameraNode.position = SCNVector3(20, 30, -10)
        root.addChildNode(cameraNode)

        // Light.
        let sun = SCNNode()
        sun.light = SCNLight()
        sun.light?.type = .directional
        sun.light?.intensity = 850
        sun.eulerAngles = SCNVector3(-Float.pi / 3, Float.pi / 5, 0)
        root.addChildNode(sun)
        let ambient = SCNNode()
        ambient.light = SCNLight()
        ambient.light?.type = .ambient
        ambient.light?.intensity = 450
        root.addChildNode(ambient)
    }

    func update(path: [PathPoint], position: Vec2?, headingDegrees: Double) {
        route.update(path: path, floorY: 0.03)
        guard let position else { puck.isHidden = true; return }

        // Turn the short way round (no spinning when the heading wraps past ±180°).
        var h = headingDegrees
        if let prev = unwrappedHeading { h = prev + RouteTracker.wrap(headingDegrees - prev) }
        unwrappedHeading = h
        let r = h * .pi / 180

        let p = SCNVector3(Float(position.x), 0, Float(-position.y))
        let forward = SCNVector3(Float(cos(r)), 0, Float(-sin(r)))
        let back: Float = 7, up: Float = 9

        SCNTransaction.begin()
        SCNTransaction.animationDuration = puck.isHidden ? 0 : 0.3
        puck.isHidden = false
        puck.position = p
        puck.eulerAngles.y = Float(r)
        cameraNode.position = SCNVector3(p.x - forward.x * back, up, p.z - forward.z * back)
        SCNTransaction.commit()
    }

    // MARK: Building blocks

    /// Every wall segment as a thin box between two heights, in one mesh.
    static func wallMesh(_ segments: [(Vec2, Vec2)], from y0: Float, to y1: Float,
                         thickness: Double = 0.14) -> SCNGeometry {
        var v: [SCNVector3] = [], n: [SCNVector3] = [], idx: [UInt32] = []
        func quad(_ a: SCNVector3, _ b: SCNVector3, _ c: SCNVector3, _ d: SCNVector3, _ normal: SCNVector3) {
            let base = UInt32(v.count)
            v += [a, b, c, d]
            n += [normal, normal, normal, normal]
            idx += [base, base + 1, base + 2, base, base + 2, base + 3]
        }
        for (a, b) in segments {
            let d = b - a
            guard d.length > 0.01 else { continue }
            let dir = d * (1 / d.length)
            let side = Vec2(x: -dir.y, y: dir.x) * (thickness / 2)
            // Extend a little past the ends so corners meet.
            let a2 = a - dir * (thickness / 2), b2 = b + dir * (thickness / 2)
            let c = [a2 + side, b2 + side, b2 - side, a2 - side]
            func P(_ q: Vec2, _ y: Float) -> SCNVector3 { SCNVector3(Float(q.x), y, Float(-q.y)) }
            func N(_ q: Vec2) -> SCNVector3 { SCNVector3(Float(q.x), 0, Float(-q.y)) }
            let s = side * (1 / side.length)
            quad(P(c[0], y0), P(c[1], y0), P(c[1], y1), P(c[0], y1), N(s))          // left face
            quad(P(c[2], y0), P(c[3], y0), P(c[3], y1), P(c[2], y1), N(s * -1))     // right face
            quad(P(c[1], y0), P(c[2], y0), P(c[2], y1), P(c[1], y1), N(dir))        // end
            quad(P(c[3], y0), P(c[0], y0), P(c[0], y1), P(c[3], y1), N(dir * -1))   // start
            quad(P(c[0], y1), P(c[1], y1), P(c[2], y1), P(c[3], y1), SCNVector3(0, 1, 0)) // top
        }
        return SCNGeometry(sources: [SCNGeometrySource(vertices: v), SCNGeometrySource(normals: n)],
                           elements: [SCNGeometryElement(indices: idx, primitiveType: .triangles)])
    }

    static func label(_ text: String, at p: Vec2) -> SCNNode {
        let t = SCNText(string: text, extrusionDepth: 0.05)
        t.font = UIFont.systemFont(ofSize: 1.0, weight: .bold)
        t.flatness = 0.05
        t.firstMaterial = flat(UIColor(white: 0.2, alpha: 1))
        let node = SCNNode(geometry: t)
        let (lo, hi) = t.boundingBox
        node.pivot = SCNMatrix4MakeTranslation((lo.x + hi.x) / 2, lo.y, 0)
        node.position = SCNVector3(Float(p.x), 3.0, Float(-p.y))
        node.constraints = [SCNBillboardConstraint()]
        return node
    }

    static func lit(_ color: UIColor) -> SCNMaterial {
        let m = SCNMaterial()
        m.lightingModel = .lambert
        m.diffuse.contents = color
        m.isDoubleSided = true
        return m
    }

    static func flat(_ color: UIColor) -> SCNMaterial {
        let m = SCNMaterial()
        m.lightingModel = .constant
        m.diffuse.contents = color
        return m
    }
}
