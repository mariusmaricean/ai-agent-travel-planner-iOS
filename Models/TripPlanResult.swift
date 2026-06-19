import Foundation

struct TripPlanResult: Sendable {
    var trips: [TripOption]
    var memory: [MemoryNote]?
}
