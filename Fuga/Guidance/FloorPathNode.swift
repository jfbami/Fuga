import ARKit
import SceneKit

/// A solid route line on the floor, Apple Maps style: a green band with a darker outline and
/// a soft highlight that sweeps from you toward the destination.
///
/// Used twice: in the camera view (drawn on the real hallway floor, hidden by real walls where it
/// turns a corner) and in the 3D building view. Points are top-down (x, y) with y = -z in the scene,
/// which is both ARKit's top-down frame and the 3D view's plan frame.
final class FloorPathNode: SCNNode {
    /// Line width, meters.
    var width: Float
    /// The line fades out between these distances ahead of you (meters).
    var fadeStart: Float = 12 { didSet { material.setValue(NSNumber(value: fadeStart), forKey: "fadeStart") } }
    var fadeEnd: Float = 18 { didSet { material.setValue(NSNumber(value: fadeEnd), forKey: "fadeEnd") } }

    private let material: SCNMaterial
    private var smoothedFloorY: Float?

    init(width: Float = 0.5) {
        self.width = width
        let m = SCNMaterial()
        m.lightingModel = .constant
        m.isDoubleSided = true
        m.blendMode = .alpha
        m.writesToDepthBuffer = false
        m.readsFromDepthBuffer = true      // walls drawn into the depth buffer hide it
        m.diffuse.contents = UIColor.white
        m.shaderModifiers = [.fragment: FloorPathNode.shader]
        material = m
        super.init()
        material.setValue(NSNumber(value: 0), forKey: "startU")
        material.setValue(NSNumber(value: fadeStart), forKey: "fadeStart")
        material.setValue(NSNumber(value: fadeEnd), forKey: "fadeEnd")
        renderingOrder = 100
        isHidden = true
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    func hide() {
        isHidden = true
        geometry = nil
    }

    /// `path`: the rest of the route, first point where you are; `floorY`: height of the floor.
    func update(path: [PathPoint], floorY: Float) {
        guard path.count >= 2 else { hide(); return }

        var positions: [SCNVector3] = []
        var uvs: [CGPoint] = []
        var indices: [UInt16] = []
        let half = Double(width / 2)

        for i in 0..<path.count {
            let p = path[i].point
            // Direction at this point, averaged at corners so the band bends cleanly.
            let inDir = i > 0 ? (p - path[i - 1].point) : (path[1].point - p)
            let outDir = i < path.count - 1 ? (path[i + 1].point - p) : inDir
            let a = inDir * (1 / max(inDir.length, 1e-6)), b = outDir * (1 / max(outDir.length, 1e-6))
            var d = a + b
            if d.length < 1e-3 { d = b }
            d = d * (1 / d.length)
            let normal = Vec2(x: -d.y, y: d.x)
            // Same width around corners (miter), capped for very sharp turns.
            let miter = min(1 / max(normal.dot(Vec2(x: -b.y, y: b.x)), 0.5), 2)
            let left = p + normal * (half * miter), right = p - normal * (half * miter)

            positions.append(SCNVector3(Float(left.x), floorY, Float(-left.y)))
            positions.append(SCNVector3(Float(right.x), floorY, Float(-right.y)))
            uvs.append(CGPoint(x: path[i].along, y: 0))
            uvs.append(CGPoint(x: path[i].along, y: 1))

            if i < path.count - 1 {
                let l = UInt16(2 * i), r = l + 1, l2 = l + 2, r2 = l + 3
                indices += [l, r, l2, r, r2, l2]
            }
        }

        let g = SCNGeometry(sources: [SCNGeometrySource(vertices: positions),
                                      SCNGeometrySource(textureCoordinates: uvs)],
                            elements: [SCNGeometryElement(indices: indices, primitiveType: .triangles)])
        g.materials = [material]
        geometry = g
        material.setValue(NSNumber(value: Float(path[0].along)), forKey: "startU")
        isHidden = false
    }

    func resetFloor() {
        hide()
        smoothedFloorY = nil
    }

    /// Use an observed local horizontal surface; never invent a floor relative to
    /// the phone's changing height. Prefer ARKit's floor classification when available.
    func floorHeight(_ frame: ARFrame) -> Float? {
        let camera = frame.camera.transform.columns.3
        let candidates = frame.anchors.compactMap { $0 as? ARPlaneAnchor }.filter { plane in
            guard plane.alignment == .horizontal else { return false }
            let local = simd_inverse(plane.transform) * camera
            let nearby = abs(local.x - plane.center.x) <= plane.extent.x / 2 + 0.5
                && abs(local.z - plane.center.z) <= plane.extent.z / 2 + 0.5
            let height = plane.transform.columns.3.y + plane.center.y
            let largeEnough = plane.extent.x * plane.extent.z >= 2
            return nearby && largeEnough && height < camera.y - 0.7 && height > camera.y - 2.2
                && (plane.classification == .floor || plane.classification == .none)
        }
        let floors = candidates.filter { $0.classification == .floor }
        guard let plane = (floors.isEmpty ? candidates : floors).max(by: {
            $0.extent.x * $0.extent.z < $1.extent.x * $1.extent.z
        }) else { return nil }
        let target = plane.transform.columns.3.y + plane.center.y
        if let previous = smoothedFloorY, abs(previous - target) < 0.3 {
            smoothedFloorY = previous + (target - previous) * 0.2
        } else {
            smoothedFloorY = target
        }
        return smoothedFloorY
    }

    /// u = meters along the route, v = 0…1 across the band.
    private static let shader = """
    #pragma arguments
    float startU;
    float fadeStart;
    float fadeEnd;
    #pragma transparent
    #pragma body
    float u = _surface.diffuseTexcoord.x;
    float v = _surface.diffuseTexcoord.y;
    float ahead = u - startU;
    float across = abs(v * 2.0 - 1.0);

    // Solid green band with a darker green outline.
    float3 fill = float3(0.204, 0.780, 0.349);
    float3 rim = float3(0.05, 0.42, 0.16);
    float outline = smoothstep(0.70, 0.78, across);
    float3 color = mix(fill, rim, outline);

    // A soft lighter sweep travelling from you to the destination (2 m/s, every 6 m).
    float w = fract((ahead - scn_frame.time * 2.0) / 6.0);
    float pulse = smoothstep(0.55, 0.92, w) * (1.0 - smoothstep(0.92, 1.0, w)) * (1.0 - outline);
    color = mix(color, float3(0.78, 1.0, 0.84), pulse * 0.5);

    float alpha = 0.92
        * (1.0 - smoothstep(0.93, 1.0, across))
        * smoothstep(-0.1, 0.4, ahead)
        * (1.0 - smoothstep(fadeStart, fadeEnd, ahead));
    _output.color = float4(color * alpha, alpha);
    """
}
