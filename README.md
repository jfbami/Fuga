
[View our DubHacks 2026 submission on Devpost](https://devpost.com/software/juno-s4y19m)

## Overview

Fuga combines LiDAR-based 3D reconstruction with a pretrained transformer-based matcher to estimate a phone camera’s position and orientation inside a building. 

Built at DubHacks 2026, it helps students and visitors at UW with indoor directions!

The reconstruction pipeline uses **Open3D’s volumetric TSDF fusion** to combine iPhone LiDAR scans into 3D hallway models. The localization pipeline uses **DISK**, a convolutional neural network, to extract visual features and **LightGlue**, a transformer-based matcher, to match those features against depth-backed reference views. **OpenCV’s PnP/RANSAC solver** then estimates the camera’s position and orientation.

The **SwiftUI** app uses **ARKit** to track movement, **SceneKit** to display routes, and **Dijkstra’s algorithm** to find paths through a hallway graph. Bundled **ElevenLabs** voice clips and **Core Haptics** provide spoken directions and vibration feedback.

## Highlights

- Reconstruct hallway geometry from Stray Scanner recordings containing RGB images, LiDAR depth, camera calibration, and camera poses.
- Estimate camera pose with pretrained DISK and LightGlue models running locally in PyTorch, followed by geometric verification in OpenCV.
- Explore an arrow interface, an AR floor path, spoken turns, and directional vibration.
- Test voice and vibration on an iPhone without starting navigation, or explore the interface through browser demos.

