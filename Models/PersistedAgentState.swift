import Foundation

struct PersistedAgentState: Codable, Sendable {
    var origin: String
    var destination: String
    var departDate: Date
    var returnDate: Date
    var budget: Double
    var constraints: String
    var rememberPreferences: Bool
    var mood: TripMood
    var savedTrips: [TripOption]
    var memory: [MemoryNote]
    var activeTripID: UUID?
}
