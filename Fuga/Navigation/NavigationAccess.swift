import Foundation

/// Unverified routes may only be exercised through an explicit developer-build demo.
enum NavigationAccess {
    static func permitsStart(verified: Bool, manualTest: Bool) -> Bool {
        if verified { return true }
        #if DEBUG
        return manualTest
        #else
        return false
        #endif
    }
}
