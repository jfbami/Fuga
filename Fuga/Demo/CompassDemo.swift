import CoreLocation
import Foundation

/// Temporary driver for the arrow until routing and localization exist.
///
/// On a real iPhone it reads the compass: tap "Exit is this way" while facing somewhere,
/// then turn around and the arrow keeps pointing there. In the Simulator (no compass)
/// it sweeps the heading back and forth so the animation and green state can be checked.
final class CompassDemo: NSObject, ObservableObject, CLLocationManagerDelegate {
    /// Which way the phone's top edge points, degrees clockwise from north.
    @Published private(set) var heading: Double = 0
    /// Compass bearing of the pretend exit.
    @Published var targetBearing: Double = 0
    /// Pretend distance to the exit.
    @Published var distanceMeters: Double = 4

    let isSimulated: Bool

    private let manager = CLLocationManager()
    private var sweepTimer: Timer?
    private var sweepTime: Double = 0

    override init() {
        isSimulated = !CLLocationManager.headingAvailable()
        super.init()
        if isSimulated {
            startSweep()
        } else {
            manager.delegate = self
            manager.headingFilter = 1
            manager.startUpdatingHeading()
        }
    }

    deinit {
        sweepTimer?.invalidate()
        manager.stopUpdatingHeading()
    }

    /// What the arrow needs: where the exit is relative to the way the phone faces.
    var relativeBearing: Double {
        targetBearing - heading
    }

    /// Put the pretend exit straight ahead of wherever the phone faces now.
    func setExitAhead() {
        targetBearing = heading
    }

    func locationManager(_ manager: CLLocationManager, didUpdateHeading newHeading: CLHeading) {
        // trueHeading is -1 until location is known; magnetic is fine for a demo.
        heading = newHeading.trueHeading >= 0 ? newHeading.trueHeading : newHeading.magneticHeading
    }

    func locationManagerShouldDisplayHeadingCalibration(_ manager: CLLocationManager) -> Bool {
        true
    }

    private func startSweep() {
        sweepTimer = Timer.scheduledTimer(withTimeInterval: 1.0 / 30.0, repeats: true) { [weak self] _ in
            guard let self else { return }
            self.sweepTime += 1.0 / 30.0
            // Swing ±110° so it passes through "ahead", "to your left/right" and back.
            self.heading = 110 * sin(self.sweepTime * 0.6)
        }
    }
}
