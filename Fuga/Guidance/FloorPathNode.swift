import ARKit
import SceneKit

/// The green "GPS line" drawn on the hallway floor in the camera view, from where you are to the
/// destination. A soft green ribbon with chevrons pointing the way, and bright pulses that travel
/// along it from your feet toward the room. It fades out ~15 m ahead so it doesn't show through
/// walls past the next corner.
final class FloorPathNode: SCNNode {
    /// Ribbon width on the floor, meters.
    var width: Float = 0.45

    private let material: SCNMaterial = {
        let m = SCNMaterial()
        m.lightingModel = .constant
        m.isDoubleSided = true
        m.blendMode = .alpha
        m.writesToDepthBuffer = false
        m.readsFromDepthBuffer = false
        m.diffuse.contents = UIColor.white
        m.shaderModifiers = [.fragment: FloorPathNode.shader]
        m.setValue(NSNumber(value: 0), forKey: "startU")
        return m
    }()

    private var smoothedFloorY: Float?

    override init() {
        super.init()
        renderingOrder = 100
        isHidden = true
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    func hide() {
        isHidden = true
        geometry = nil
    }

    /// `path` is the rest of the route in ARKit top-down coordinates (x, -z) with how far along
    /// the route each point is. The first point is where you are.
    func update(path: [(point: Vec2, along: Double)], frame: ARFrame) {
        guard path.count >= 2 else { hide(); return }
        let y = floorHeight(frame) + 0.01

        var positions: [SCNVector3] = []
        var uvs: [CGPoint] = []
        var indices: [UInt16] = []
        let half = Double(width / 2)

        for i in 0..<path.count {
            let p = path[i].point
            // Direction of the line at this point (averaged at corners so the ribbon bends cleanly).
            let inDir = i > 0 ? (p - path[i - 1].point) : (path[1].point - p)
            let outDir = i < path.count - 1 ? (path[i + 1].point - p) : inDir
            let a = inDir * (1 / max(inDir.length, 1e-6)), b = outDir * (1 / max(outDir.length, 1e-6))
            var d = a + b
            if d.length < 1e-3 { d = b }
            d = d * (1 / d.length)
            let normal = Vec2(x: -d.y, y: d.x)
            // Keep the width constant around corners (miter), capped for very sharp turns.
            let miter = min(1 / max(normal.dot(Vec2(x: -b.y, y: b.x)), 0.5), 2)
            let left = p + normal * (half * miter), right = p - normal * (half * miter)

            positions.append(SCNVector3(Float(left.x), y, Float(-left.y)))
            positions.append(SCNVector3(Float(right.x), y, Float(-right.y)))
            let u = CGFloat(path[i].along)
            uvs.append(CGPoint(x: u, y: 0))
            uvs.append(CGPoint(x: u, y: 1))

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

    /// The floor: the lowest horizontal plane ARKit has found well below the phone, or about
    /// 1.35 m below the phone if it hasn't found one yet. Smoothed so the line doesn't jump.
    private func floorHeight(_ frame: ARFrame) -> Float {
        let cameraY = frame.camera.transform.columns.3.y
        let floors = frame.anchors.compactMap { $0 as? ARPlaneAnchor }
            .filter { $0.alignment == .horizontal }
            .map { $0.transform.columns.3.y }
            .filter { $0 < cameraY - 0.7 && $0 > cameraY - 2.2 }
        let target = floors.min() ?? (cameraY - 1.35)
        if let s = smoothedFloorY, abs(s - target) < 0.5 {
            smoothedFloorY = s + (target - s) * 0.2
        } else {
            smoothedFloorY = target
        }
        return smoothedFloorY!
    }

    /// u = meters along the route, v = 0…1 across the ribbon.
    private static let shader = """
    #pragma arguments
    float startU;
    #pragma transparent
    #pragma body
    float u = _surface.diffuseTexcoord.x;
    float v = _surface.diffuseTexcoord.y;
    float ahead = u - startU;
    float across = abs(v * 2.0 - 1.0);

    // Soft edges.
    float edge = 1.0 - smoothstep(0.65, 1.0, across);
    // Chevrons pointing toward the destination, every 0.7 m.
    float c = fract((u - across * 0.25) / 0.7);
    float chevron = smoothstep(0.0, 0.04, c) * (1.0 - smoothstep(0.16, 0.22, c));
    // Pulses travelling from you to the destination: 2 m/s, one every 4 m,
    // bright at the front with a short tail behind.
    float w = fract((ahead - scn_frame.time * 2.0) / 4.0);
    float pulse = smoothstep(0.55, 0.95, w) * (1.0 - smoothstep(0.95, 1.0, w));
    // Gentle breathing of the whole line.
    float breathe = 0.85 + 0.15 * sin(scn_frame.time * 3.0);
    // Start just in front of your feet, fade out ~15 m ahead.
    float fade = smoothstep(-0.1, 0.5, ahead) * (1.0 - smoothstep(10.0, 15.0, ahead));

    float alpha = clamp(edge * fade * (0.25 * breathe + 0.45 * chevron + 0.75 * pulse), 0.0, 1.0);
    float3 green = float3(0.204, 0.780, 0.349);
    float3 color = mix(green, float3(0.75, 1.0, 0.8), pulse * 0.6);
    _output.color = float4(color * alpha, alpha);
    """
}
