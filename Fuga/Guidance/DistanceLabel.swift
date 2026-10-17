import SwiftUI

/// "13 ft / ahead", Find My style: the number in white, the unit dimmed, the direction underneath.
struct DistanceLabel: View {
    var meters: Double
    var relativeBearing: Double

    var body: some View {
        let parts = Self.distanceParts(meters: meters)
        VStack(spacing: 0) {
            if let unit = parts.unit {
                (Text(parts.value).foregroundColor(.white)
                    + Text(" " + unit).foregroundColor(.white.opacity(0.5)))
                    .font(.system(size: 44, weight: .regular))
                    .monospacedDigit()
            } else {
                Text(parts.value)
                    .font(.system(size: 44, weight: .regular))
                    .foregroundColor(.white)
            }
            Text(Self.direction(for: relativeBearing))
                .font(.system(size: 28, weight: .regular))
                .foregroundColor(.white)
        }
        .shadow(color: .black.opacity(0.45), radius: 6, y: 2)
        .contentTransition(.numericText())
        .animation(.default, value: parts.value)
    }

    // MARK: - Formatting

    /// Under this distance we stop counting and just say the exit is here.
    static let arrivalThresholdMeters: Double = 1.5

    static var usesFeet: Bool {
        Locale.current.measurementSystem == .us
    }

    /// Splits a distance into the big number and its unit, e.g. ("13", "ft"). Arrival returns ("Exit", nil).
    static func distanceParts(meters: Double) -> (value: String, unit: String?) {
        if meters < arrivalThresholdMeters {
            return ("Exit", nil)
        }
        if usesFeet {
            let feet = Int((meters * 3.28084).rounded())
            return ("\(feet)", "ft")
        }
        let wholeMeters = Int(meters.rounded())
        return ("\(wholeMeters)", "m")
    }

    /// Plain-language direction for a bearing relative to the phone.
    static func direction(for relativeBearing: Double) -> String {
        let b = ExitArrowView.normalized(relativeBearing)
        let magnitude = abs(b)
        if magnitude <= ExitArrowView.alignedTolerance { return "ahead" }
        if magnitude >= 135 { return "behind you" }
        return b > 0 ? "to your right" : "to your left"
    }

    /// What VoiceOver (and later, the voice guidance) says.
    static func spokenDescription(meters: Double, relativeBearing: Double) -> String {
        let parts = distanceParts(meters: meters)
        guard let unit = parts.unit else { return "You've reached the exit" }
        let spokenUnit = unit == "ft" ? "feet" : "meters"
        return "Exit \(parts.value) \(spokenUnit) \(direction(for: relativeBearing))"
    }
}
