import ARKit
import CoreImage
import CryptoKit
import ImageIO
import UIKit

enum QuickLookError: LocalizedError {
    case message(String)
    var errorDescription: String? { if case .message(let text) = self { return text }; return nil }
}

/// The image, intrinsics and pose always come from the same ARFrame.
/// No screen capture, display crop, estimated photo calibration or query depth is used.
enum QuickLookCapture {
    static func rows(_ matrix: simd_float4x4) -> [[Double]] {
        (0..<4).map { r in (0..<4).map { c in Double(matrix[c][r]) } }
    }

    static func encode(frame: ARFrame, floor: Int, sessionID: String) throws -> [String: Any] {
        guard case .normal = frame.camera.trackingState else {
            throw QuickLookError.message("Hold the phone steady and point it at the hallway.")
        }
        let buffer = frame.capturedImage
        let width = CVPixelBufferGetWidth(buffer), height = CVPixelBufferGetHeight(buffer)
        let size = frame.camera.imageResolution
        guard width == Int(size.width), height == Int(size.height) else {
            throw QuickLookError.message("Camera image and calibration sizes disagree.")
        }
        let k = frame.camera.intrinsics
        // Native sensor pixels -> portrait pixels, 90 degrees clockwise:
        // u' = height - 1 - v, v' = u. Intrinsics AND camera axes change together.
        let portrait = CIImage(cvPixelBuffer: buffer).oriented(.right)
        guard let cg = CIContext().createCGImage(portrait, from: portrait.extent),
              cg.width == height, cg.height == width,
              let jpeg = UIImage(cgImage: cg).jpegData(compressionQuality: 0.92) else {
            throw QuickLookError.message("Could not encode the camera frame.")
        }
        // ARKit camera <- portrait OpenCV camera. ARKit uses +Y up/-Z forward;
        // submitted image uses +X right/+Y down/+Z forward, with the pixel rotation above.
        let arCameraFromPortraitCV = simd_float4x4(columns: (
            SIMD4<Float>(0, 1, 0, 0), SIMD4<Float>(1, 0, 0, 0),
            SIMD4<Float>(0, 0, -1, 0), SIMD4<Float>(0, 0, 0, 1)))
        return [
            "request_id": UUID().uuidString, "capture_timestamp": frame.timestamp,
            "building_id": "MGH", "selected_floor": floor, "session_id": sessionID,
            "image_base64": jpeg.base64EncodedString(), "calibration_status": "verified",
            "intrinsics": ["width": height, "height": width,
                "fx": Double(k[1][1]), "fy": Double(k[0][0]),
                "cx": Double(height - 1) - Double(k[2][1]), "cy": Double(k[2][0]),
                "distortion": [Double]()] as [String: Any],
            "capture_metadata": [
                "calibration_source": "Same ARFrame ARCamera.intrinsics; device-provided, not surveyed validation",
                "pixel_transform": "native_sensor_to_portrait_clockwise_90_no_crop_no_resize",
                "native_width": width, "native_height": height,
                "tracking_state": "normal", "arkit_world_from_camera": rows(frame.camera.transform),
                "arkit_world_from_image_camera_cv": rows(frame.camera.transform * arCameraFromPortraitCV),
                "matrix_layout": "rows", "query_depth_used": false
            ] as [String: Any]
        ]
    }
}

/// Diagnostic only: a scan/ARKit alignment does not register the route graph.
enum QuickLookGeometry {
    static func rigid(_ rows: [[Double]]) -> simd_float4x4? {
        guard rows.count == 4, rows.allSatisfy({ $0.count == 4 && $0.allSatisfy(\.isFinite) }),
              zip(rows[3], [0.0, 0, 0, 1]).allSatisfy({ abs($0.0 - $0.1) < 1e-4 }) else { return nil }
        var t = matrix_identity_float4x4
        for r in 0..<4 { for c in 0..<4 { t[c][r] = Float(rows[r][c]) } }
        let rotation = simd_float3x3(columns: (SIMD3(t.columns.0.x, t.columns.0.y, t.columns.0.z),
            SIMD3(t.columns.1.x, t.columns.1.y, t.columns.1.z), SIMD3(t.columns.2.x, t.columns.2.y, t.columns.2.z)))
        guard abs(simd_determinant(rotation) - 1) < 0.01 else { return nil }
        let check = rotation.transpose * rotation
        for r in 0..<3 { for c in 0..<3 {
            if abs(check[c][r] - (r == c ? 1 : 0)) > 0.01 { return nil }
        } }
        return t
    }

    static func alignment(request: [String: Any], response: [String: Any]) -> simd_float4x4? {
        guard response["accepted"] as? Bool == true, response["pose_usable_for_app"] as? Bool == true,
              response["coordinate_frame_id"] as? String == "scan:b9dca4993d",
              response["building_id"] as? String == "MGH",
              response["selected_floor"] as? Int == request["selected_floor"] as? Int,
              let mapHash = response["map_manifest_sha256"] as? String, mapHash.count == 64,
              mapHash.allSatisfy({ $0.isHexDigit }),
              let encoded = request["image_base64"] as? String, let jpeg = Data(base64Encoded: encoded),
              response["query_image_sha256"] as? String == SHA256.hash(data: jpeg).map({ String(format: "%02x", $0) }).joined(),
              response["request_id"] as? String == request["request_id"] as? String,
              let capture = request["capture_timestamp"] as? Double,
              let echoed = response["capture_timestamp"] as? Double, abs(echoed - capture) < 1e-6,
              response["calibration_status"] as? String == "verified",
              let p = response["position_scan_m"] as? [Double], p.count == 3,
              let r = response["rotation_world_camera"] as? [[Double]], r.count == 3,
              r.allSatisfy({ $0.count == 3 }),
              let metadata = request["capture_metadata"] as? [String: Any],
              let arRows = metadata["arkit_world_from_image_camera_cv"] as? [[Double]],
              let arFromImage = rigid(arRows) else { return nil }
        var scanRows = (0..<3).map { r[$0] + [p[$0]] }; scanRows.append([0, 0, 0, 1])
        guard let scanFromImage = rigid(scanRows) else { return nil }
        return scanFromImage * simd_inverse(arFromImage)
    }

    static func agree(_ a: simd_float4x4, _ b: simd_float4x4) -> Bool {
        let delta = simd_inverse(a) * b
        let distance = simd_length(SIMD3(delta.columns.3.x, delta.columns.3.y, delta.columns.3.z))
        let trace = delta[0][0] + delta[1][1] + delta[2][2]
        let degrees = acos(min(1, max(-1, (trace - 1) / 2))) * 180 / .pi
        return distance < 0.75 && degrees < 10
    }
}
