import ARKit
import SceneKit
import SwiftUI

/// Full-screen camera feed driven by the navigator's ARSession.
struct ARCameraView: UIViewRepresentable {
    let session: ARSession
    /// 3D content drawn into the camera view, e.g. the green floor path.
    var content: SCNNode? = nil

    func makeUIView(context: Context) -> ARSCNView {
        let view = ARSCNView(frame: .zero)
        view.session = session
        view.automaticallyUpdatesLighting = false
        view.rendersCameraGrain = false
        view.scene = SCNScene()
        if let content { view.scene.rootNode.addChildNode(content) }
        return view
    }

    func updateUIView(_ uiView: ARSCNView, context: Context) {}
}
