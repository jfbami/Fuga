import ARKit
import SceneKit
import SwiftUI

/// Full-screen camera feed driven by the navigator's ARSession, plus any 3D content (the green
/// floor path). Walls the phone detects are drawn invisibly into the depth buffer, so the path
/// is hidden behind them, like a real line painted on the floor going around a corner:
/// - Pro iPhones (LiDAR): the live 3D mesh of the room, keeping only wall-like (vertical) faces.
/// - Other iPhones: flat vertical planes ARKit finds on walls.
struct ARCameraView: UIViewRepresentable {
    let session: ARSession
    /// 3D content drawn into the camera view, e.g. the green floor path.
    var content: SCNNode? = nil

    func makeCoordinator() -> WallOccluder { WallOccluder() }

    func makeUIView(context: Context) -> ARSCNView {
        let view = ARSCNView(frame: .zero)
        view.session = session
        view.delegate = context.coordinator
        view.automaticallyUpdatesLighting = false
        view.rendersCameraGrain = false
        view.scene = SCNScene()
        if let content { view.scene.rootNode.addChildNode(content) }
        return view
    }

    func updateUIView(_ uiView: ARSCNView, context: Context) {}
}

/// Turns detected walls into invisible depth-only geometry.
final class WallOccluder: NSObject, ARSCNViewDelegate {
    private let material: SCNMaterial = {
        let m = SCNMaterial()
        m.colorBufferWriteMask = []        // draws nothing visible...
        m.writesToDepthBuffer = true       // ...but hides what's behind it
        m.isDoubleSided = true
        return m
    }()

    private let hasLiDARMesh = ARWorldTrackingConfiguration.supportsSceneReconstruction(.mesh)

    func renderer(_ renderer: SCNSceneRenderer, didAdd node: SCNNode, for anchor: ARAnchor) {
        refresh(node, for: anchor, renderer: renderer)
    }

    func renderer(_ renderer: SCNSceneRenderer, didUpdate node: SCNNode, for anchor: ARAnchor) {
        refresh(node, for: anchor, renderer: renderer)
    }

    private func refresh(_ node: SCNNode, for anchor: ARAnchor, renderer: SCNSceneRenderer) {
        if let mesh = anchor as? ARMeshAnchor {
            node.geometry = wallGeometry(mesh)
            node.geometry?.materials = [material]
            node.renderingOrder = -10
        } else if !hasLiDARMesh, let plane = anchor as? ARPlaneAnchor, plane.alignment == .vertical,
                  let device = renderer.device {
            // No LiDAR mesh: use the wall planes ARKit finds.
            let g = (node.geometry as? ARSCNPlaneGeometry) ?? ARSCNPlaneGeometry(device: device)
            g?.update(from: plane.geometry)
            g?.materials = [material]
            node.geometry = g
            node.renderingOrder = -10
        }
    }

    /// The faces of a LiDAR mesh chunk that are roughly vertical (walls, doors, cabinets),
    /// leaving out the floor so the path drawn on it isn't hidden.
    private func wallGeometry(_ anchor: ARMeshAnchor) -> SCNGeometry? {
        let mesh = anchor.geometry
        let vs = mesh.vertices, faces = mesh.faces
        guard vs.count > 0, faces.count > 0, faces.indexCountPerPrimitive == 3 else { return nil }

        var vertices = [SCNVector3](repeating: SCNVector3Zero, count: vs.count)
        let vbase = vs.buffer.contents().advanced(by: vs.offset)
        for i in 0..<vs.count {
            let p = vbase.advanced(by: vs.stride * i).assumingMemoryBound(to: Float.self)
            vertices[i] = SCNVector3(p[0], p[1], p[2])
        }

        let t = anchor.transform
        let fbase = faces.buffer.contents()
        var kept: [UInt32] = []
        kept.reserveCapacity(faces.count * 3)
        for f in 0..<faces.count {
            var idx = [UInt32](repeating: 0, count: 3)
            for k in 0..<3 {
                let at = fbase.advanced(by: (f * 3 + k) * faces.bytesPerIndex)
                idx[k] = faces.bytesPerIndex == 4
                    ? at.assumingMemoryBound(to: UInt32.self).pointee
                    : UInt32(at.assumingMemoryBound(to: UInt16.self).pointee)
            }
            let a = vertices[Int(idx[0])], b = vertices[Int(idx[1])], c = vertices[Int(idx[2])]
            let e1 = SIMD3<Float>(b.x - a.x, b.y - a.y, b.z - a.z)
            let e2 = SIMD3<Float>(c.x - a.x, c.y - a.y, c.z - a.z)
            var n = simd_cross(e1, e2)
            let len = simd_length(n)
            guard len > 1e-8 else { continue }
            n /= len
            // Normal in world space; keep faces that aren't floor/ceiling/tabletop.
            let worldUp = t.columns.0.y * n.x + t.columns.1.y * n.y + t.columns.2.y * n.z
            if abs(worldUp) < 0.6 { kept += idx }
        }
        guard !kept.isEmpty else { return nil }
        return SCNGeometry(sources: [SCNGeometrySource(vertices: vertices)],
                           elements: [SCNGeometryElement(indices: kept, primitiveType: .triangles)])
    }
}
